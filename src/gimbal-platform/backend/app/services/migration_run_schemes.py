"""一次性迁移:payload.orchestration.runSchemes → composer_run_schemes 表。

对 init_db「schema 变更随 DB 重建」惯例的一次有记录偏离(spec §4.3):
方案是用户资产不可重建丢失,且单机部署没有带外迁移窗口。幂等 —
搬完清键,有方案存量的场景数随之归零;ensure_default 对已补场景是
no-op。阶段④清理时整体下线。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.composer_scenario import ComposerScenario
from . import scheme_store


async def migrate_run_schemes_to_table(db: AsyncSession) -> int:
    """遍历全部场景:有 runSchemes 存量的搬入新表并清键;所有场景
    ensure_default(D8 全物化 — 无方案存量的场景也要有默认方案行)。

    返回有方案数据可搬的场景数(幂等:重跑恒 0)。
    """
    rows = (await db.execute(select(ComposerScenario))).scalars().all()
    moved = 0
    for row in rows:
        orch = dict((row.payload or {}).get("orchestration") or {})
        legacy = orch.get("runSchemes") or []
        for s in legacy:
            try:
                await scheme_store.create_scheme(
                    db, row.scenario_id,
                    name=s.get("name") or f"未命名-{row.scenario_id[:8]}",
                    payload=s)
            except ValueError:
                continue  # 重名(如与默认方案撞名)跳过,不阻断迁移
        await scheme_store.ensure_default_scheme(db, row.scenario_id)
        if legacy:
            orch["runSchemes"] = []
            payload = dict(row.payload or {})
            payload["orchestration"] = orch
            row.payload = payload  # JSON 列不追踪原地变更,必须整体重赋值
            moved += 1
    if moved:
        await db.commit()
    return moved
