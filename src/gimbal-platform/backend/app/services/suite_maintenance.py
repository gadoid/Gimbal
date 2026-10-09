"""suite 后台维护(重构方案:草稿 30 天清理)。

平台无周期任务基建,由 lifespan 挂轻量循环任务小时级巡检(决策记录);
删除幂等、多进程并发执行无害。窗口判定:30 天未改动且**无主体成员**
的草稿(非空草稿的积累由 SUITE_DRAFT_CAP 兜住,不由本任务清理)。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from ..core import db as db_module
from ..models.suite import Suite, SuiteMember


async def sweep_stale_drafts(days: int = 30) -> int:
    """删除超期空草稿,返回删除数。幂等(删不存在的行无害)。"""
    cutoff = datetime.now(timezone.utc).replace(
        tzinfo=None) - timedelta(days=days)
    removed = 0
    async with db_module.SessionLocal() as db:
        drafts = (await db.execute(select(Suite).where(
            Suite.updated_at < cutoff))).scalars().all()
        for s in drafts:
            if not (s.mode_config or {}).get("draft"):
                continue
            has_main = (await db.execute(
                select(SuiteMember.scenario_id).where(
                    SuiteMember.suite_id == s.id,
                    SuiteMember.role == "main")
                .limit(1))).scalar_one_or_none() is not None
            if has_main:
                continue           # 非空草稿:交给 SUITE_DRAFT_CAP
            await db.delete(s)     # 成员行随组合外键 CASCADE
            await db.commit()
            removed += 1
    return removed
