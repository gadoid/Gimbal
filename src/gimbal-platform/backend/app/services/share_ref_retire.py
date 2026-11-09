"""S7.4 share_ref 退役:存量引用一次性转被分享人的私有副本。

Q2 裁定(2026-11-09):上线即全部转副本,一次退役。转换在应用层实现
(拷贝依赖 store 逻辑:scenario_store.copy_scenario / suite_copy.
deep_copy_suite,与 POST /shares 的 copy 分支同一复制口径 —— 跨属主
剥离内置凭证与数据集敏感列);随后的迁移 0049 只删表(表非空即拒绝,
防漏跑本转换)。

share_refs 模型已随退役删除;本模块经**裸 SQL**读写该表(转换先于
迁移执行,表仍在)。幂等:转换成功即删行;crash 窗口(副本已 commit、
行未删)由 ``forked_from_id`` 兜底 —— grantee 名下已有该源的 fork 时
复用,不重拷。
"""
from __future__ import annotations

from dataclasses import dataclass
from fastapi import HTTPException
from loguru import logger
from sqlalchemy import select as sa_select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.composer_scenario import ComposerScenario
from ..models.suite import Suite
from ..models.user import User
from . import audit as audit_svc
from . import notifications as notify_svc
from . import scenario_store
from .suite_copy import deep_copy_suite, suite_owner_display


class RefConversionError(Exception):
    """单条转换失败(空套件/上限等);行保留,可修后重跑。"""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class RefRow:
    """share_refs 行的裸投影(模型已删,经 SQL 读写)。"""

    id: int
    grantee_user_id: int
    scenario_id: str | None
    suite_id: int | None


async def list_refs(db: AsyncSession) -> list[RefRow]:
    rows = (await db.execute(text(
        "SELECT id, grantee_user_id, scenario_id, suite_id"
        " FROM share_refs ORDER BY id"))).all()
    return [RefRow(*r) for r in rows]


async def convert_ref(db: AsyncSession, ref: RefRow) -> dict:
    """单条引用 → grantee 私有副本;成功后删该行。

    返回 {kind, sourceId, copyId, granteeId}(报告/审计口径)。失败抛
    :class:`RefConversionError`,行不动。
    """
    grantee = await db.get(User, ref.grantee_user_id)
    if grantee is None:
        raise RefConversionError("grantee_missing")
    grantee_disp = grantee.display_name or grantee.username

    if ref.scenario_id is not None:
        row = (await db.execute(sa_select(ComposerScenario).where(
            ComposerScenario.scenario_id == ref.scenario_id))
        ).scalar_one_or_none()
        if row is None:
            raise RefConversionError("scenario_missing")
        copy_id = await _existing_fork_scenario(db, grantee.id, row.scenario_id)
        if copy_id is None:
            resolved, _ = await scenario_store.resolve_name_conflict(
                db, grantee.id, row.name or row.scenario_id)
            out = await scenario_store.copy_scenario(
                db, row.scenario_id,
                new_owner=grantee_disp,
                new_owner_id=grantee.id, new_name=resolved,
                activity_kind="scenario.share_fork",
                activity_detail={"fromRef": ref.id, "retired": True},
                origin_id=row.scenario_id,
                origin_owner_name=row.owner_name or "")
            copy_id = out.meta.scenario_id
        await _finish(db, ref, kind="scenario", source_id=row.scenario_id,
                      source_name=row.name or row.scenario_id,
                      copy_id=copy_id, owner_id=row.owner_id,
                      owner_name=row.owner_name or "",
                      grantee=grantee, grantee_disp=grantee_disp,
                      copy_link=f"/scenarios/{copy_id}/detail")
        return {"kind": "scenario", "sourceId": row.scenario_id,
                "copyId": copy_id, "granteeId": grantee.id}

    suite = await db.get(Suite, ref.suite_id)
    if suite is None:
        raise RefConversionError("suite_missing")
    copy_id = await _existing_fork_suite(db, grantee.id, suite.id)
    if copy_id is None:
        try:
            out = await deep_copy_suite(
                db, suite, grantee, await suite_owner_display(db, suite))
        except HTTPException as e:
            raise RefConversionError(str(e.detail)[:200]) from None
        copy_id = out["suiteId"]
    await _finish(db, ref, kind="suite", source_id=str(suite.id),
                  source_name=suite.name, copy_id=str(copy_id),
                  owner_id=suite.owner_id,
                  owner_name=await suite_owner_display(db, suite),
                  grantee=grantee, grantee_disp=grantee_disp,
                  copy_link=f"/suites/{copy_id}")
    return {"kind": "suite", "sourceId": str(suite.id),
            "copyId": str(copy_id), "granteeId": grantee.id}


# ── 内部 ──────────────────────────────────────────────────────────

async def _existing_fork_scenario(db: AsyncSession, owner_id: int,
                                  source_id: str) -> str | None:
    """crash 幂等兜底:grantee 名下已有该源的 fork(含此前手动 fork/
    套件转换带出的成员副本)→ 复用最早一份,不重拷。"""
    return (await db.execute(
        sa_select(ComposerScenario.scenario_id).where(
            ComposerScenario.owner_id == owner_id,
            ComposerScenario.forked_from_id == source_id)
        .order_by(ComposerScenario.created_at).limit(1))).scalar_one_or_none()


async def _existing_fork_suite(db: AsyncSession, owner_id: int,
                               source_id: int) -> int | None:
    return (await db.execute(
        sa_select(Suite.id).where(
            Suite.owner_id == owner_id,
            Suite.forked_from_id == source_id)
        .order_by(Suite.created_at).limit(1))).scalar_one_or_none()


async def _finish(db: AsyncSession, ref: RefRow, *, kind: str,
                  source_id: str, source_name: str, copy_id: str,
                  owner_id: int, owner_name: str,
                  grantee: User, grantee_disp: str,
                  copy_link: str) -> None:
    """收尾三件:删行(幂等锚)→ 双方通知 → 审计。

    副本 commit 在 copy_* 内部完成;此后任何一步都 best-effort,
    不因通知/审计失败回滚转换。
    """
    await db.execute(text(
        "DELETE FROM share_refs WHERE id = :rid"), {"rid": ref.id})
    await db.commit()

    # 通知双方(Q2:逐条通知被分享人与属主)。grantee 走
    # resource_handoff(payload.sender_name 是悬浮标签数据源);属主走
    # share_ref_converted(一次性转换专用,历史行照常展示)。
    try:
        await notify_svc.create_notification(
            db, user_id=grantee.id, type_="resource_handoff",
            title=f"收到副本:{source_name}",
            body=f"引用分享退役:{owner_name or '原属主'} 的{kind_label(kind)}"
                 f"「{source_name}」已转为你的私有副本(实时跟随结束,"
                 f"后续修改各自独立)",
            link=copy_link, resource_type=kind, resource_id=copy_id,
            payload={"sender_name": owner_name or "系统"}, commit=True)
    except Exception as e:  # noqa: BLE001
        await db.rollback()
        logger.warning("share_ref_retire: notify grantee failed: {}", e)
    try:
        await notify_svc.create_notification(
            db, user_id=owner_id, type_="share_ref_converted",
            title=f"引用已转副本:{source_name}",
            body=f"{grantee_disp} 对你的{kind_label(kind)}「{source_name}」"
                 f"的引用已转为 TA 的私有副本(引用分享已退役)",
            link=copy_link, resource_type=kind, resource_id=copy_id,
            commit=True)
    except Exception as e:  # noqa: BLE001
        await db.rollback()
        logger.warning("share_ref_retire: notify owner failed: {}", e)

    try:
        await audit_svc.record(
            db, actor_id=owner_id,
            actor_name=owner_name or "",
            action="share_ref.retire",
            resource_type=kind, resource_id=copy_id,
            resource_name=source_name,
            detail={"granteeId": grantee.id, "granteeName": grantee_disp,
                    "sourceId": source_id, "copyId": copy_id})
    except Exception as e:  # noqa: BLE001
        await db.rollback()
        logger.warning("share_ref_retire: audit failed: {}", e)


def kind_label(kind: str) -> str:
    return "场景" if kind == "scenario" else "用例集"
