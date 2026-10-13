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

from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import func, select, update as sa_update
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
            # 2-5(2026-10-13):age 以**库时钟**为锚(now() 标量与
            # created_at 同源同时区,Python 只做差)—— 此前 Python
            # utcnow() 与列的 server_default now() 混比,库时区非 UTC
            # 的 PG 上 age 恒负(本地 +8 → -8h),短窗合并永远不触发、
            # edit 事件翻倍。SQLite 的 now() 是 UTC 字符串,解析后同源。
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
                db_now = (await db.execute(select(func.now()))).scalar()
                if isinstance(db_now, str):     # SQLite: "YYYY-MM-DD HH:MM:SS"
                    db_now = datetime.strptime(db_now, "%Y-%m-%d %H:%M:%S")
                hit_at = hit.created_at
                if isinstance(db_now, datetime) and db_now.tzinfo is not None                         and (hit_at is None or hit_at.tzinfo is None):
                    hit_at = hit_at.replace(tzinfo=timezone.utc) if hit_at else None
                if hit_at is not None and db_now >= hit_at:
                    age = (ensure_aware(db_now)
                           - ensure_aware(hit_at)).total_seconds()
                    if 0 <= age < EDIT_COALESCE_SECONDS:
                        await db.execute(
                            sa_update(ActivityEvent)
                            .where(ActivityEvent.id == hit.id)
                            .values(created_at=func.now()))
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
