"""activity_events 写入服务(2026-09-23 批次 F3,方案 §3.3)。

与 audit.record 同款口径:复用调用方 session、**独立 commit**、best-effort
(失败只记日志不阻断业务)。调用时机约定:**业务事务提交之后** —— 自行
commit 会把调用方未落的事务一并提交(audit.record 的既有形态,照抄)。

autosave 防刷屏(2026-09-23 评审拍板):``scenario.edit`` 走短窗合并 ——
同 (actor, resource) 在 ``EDIT_COALESCE_SECONDS`` 内已有 edit 行 → 只刷新
created_at 不插新行(编辑器 2.5s 防抖全量 PUT,不合并会刷屏);其余 kind
恒插新行。时间比较统一 aware-UTC(SQLite 行 naive、PG 行 aware,混比会
TypeError,见 timeutil.ensure_aware)。

kind 取值域(写入点唯一清单,勿在别处另开):
* ``scenario.edit``    — scenario_store.update 常规保存
* ``scenario.rename``  — update 且 meta.name 变更
* ``scenario.save_as`` — copy_scenario(另存为/复制到我的)
* ``scenario.handoff_received`` — 分发接收(F1,actor=接收方,发送方进 detail)
"""
from __future__ import annotations

from datetime import timezone

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.timeutil import ensure_aware, utcnow
from ..models import ActivityEvent

EDIT_COALESCE_SECONDS = 300

KIND_EDIT = "scenario.edit"
KIND_RENAME = "scenario.rename"
KIND_SAVE_AS = "scenario.save_as"
KIND_HANDOFF = "scenario.handoff_received"


async def record(
    db: AsyncSession,
    *,
    actor_id: int | None,
    kind: str,
    resource_type: str,
    resource_id: str,
    detail: dict | None = None,
    coalesce: bool | None = None,
) -> None:
    """事件落一条(best-effort,失败不阻断业务,同 audit.record 口径)。

    ``coalesce`` 缺省 = 仅 ``scenario.edit`` 开短窗合并;显式传值可覆盖
    (测试用)。
    """
    try:
        merge = kind == KIND_EDIT if coalesce is None else coalesce
        if merge:
            hit = (await db.execute(
                select(ActivityEvent)
                .where(
                    ActivityEvent.actor_id == actor_id,
                    ActivityEvent.kind == kind,
                    ActivityEvent.resource_type == resource_type,
                    ActivityEvent.resource_id == resource_id,
                )
                .order_by(ActivityEvent.created_at.desc())
                .limit(1)
            )).scalar_one_or_none()
            if hit is not None:
                age = (
                    utcnow().replace(tzinfo=timezone.utc)
                    - ensure_aware(hit.created_at)
                ).total_seconds()
                if 0 <= age < EDIT_COALESCE_SECONDS:
                    hit.created_at = utcnow()
                    await db.commit()
                    return
        db.add(ActivityEvent(
            actor_id=actor_id,
            kind=kind,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail or {},
        ))
        await db.commit()
    except Exception as e:  # noqa: BLE001
        await db.rollback()
        logger.warning("activity: record {} {} failed: {}",
                       kind, resource_id, e)
