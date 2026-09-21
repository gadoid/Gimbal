"""user_stars 收藏入库(M6-2,权限方案 §4/PG迁移方案 §7 M6)。

UserStar 表(M2 建)吸收 data/stars.json(marks_store 退役):star 端点
形状不变、``starred`` 仍为读时投影 —— 替换对前端透明。收藏上限 20
服务端 409 兜底(客户端先拦不变)。
"""
from __future__ import annotations

from pathlib import Path

from loguru import logger
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.permission import UserStar

STAR_CAP = 20


class StarCapExceeded(Exception):
    """收藏数达上限(20)。attributes: current(当前收藏数)。"""

    def __init__(self, current: int) -> None:
        super().__init__(f"star_cap_exceeded: {current}")
        self.current = current


async def star_ids(db: AsyncSession, user_id: int) -> set[str]:
    """该用户的全部收藏场景 id(读时投影与 ?starred= 过滤的集合源)。"""
    rows = (await db.execute(
        select(UserStar.scenario_id).where(UserStar.user_id == user_id)
    )).scalars().all()
    return set(rows)


async def set_star(
    db: AsyncSession, user_id: int, scenario_id: str, starred: bool
) -> None:
    """收藏/取消;收藏时超上限(20)抛 :class:`StarCapExceeded`。"""
    if not starred:
        await db.execute(delete(UserStar).where(
            UserStar.user_id == user_id, UserStar.scenario_id == scenario_id))
        await db.commit()
        return
    exists = (await db.execute(
        select(UserStar.scenario_id).where(
            UserStar.user_id == user_id,
            UserStar.scenario_id == scenario_id)
    )).scalar_one_or_none()
    if exists is not None:
        return
    current = (await db.execute(
        select(func.count()).select_from(UserStar)
        .where(UserStar.user_id == user_id)
    )).scalar_one()
    if current >= STAR_CAP:
        raise StarCapExceeded(current)
    db.add(UserStar(user_id=user_id, scenario_id=scenario_id))
    try:
        await db.commit()
    except IntegrityError:
        # 并发双击收藏同一场景:唯一约束兜底,幂等成功
        await db.rollback()


async def absorb_legacy_stars(db: AsyncSession) -> int:
    """一次性吸收 data/stars.json → UserStar 行,成功后改名为 .absorbed。

    幂等:文件不在场即 no-op(已吸收/从未有)。悬空 id(场景已删)按
    CASCADE 语义过滤掉。返回吸收行数。
    """
    legacy = Path(settings.DATA_DIR) / "stars.json"
    if not legacy.exists():
        return 0
    import json

    from ..models.composer_scenario import ComposerScenario

    try:
        raw = json.loads(legacy.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001  损坏文件:改名弃用,不阻塞启动
        logger.warning("user_stars: legacy stars.json unreadable ({}), retiring it", e)
        legacy.rename(legacy.with_suffix(".json.absorbed-corrupt"))
        return 0

    known = set((await db.execute(
        select(ComposerScenario.scenario_id))).scalars())
    absorbed = 0
    for uid, ids in (raw or {}).items():
        try:
            user_id = int(uid)
        except (TypeError, ValueError):
            continue
        for sid in set(ids or []):
            if sid not in known:
                continue
            db.add(UserStar(user_id=user_id, scenario_id=sid))
            absorbed += 1
    try:
        await db.commit()
    except IntegrityError:
        # 重复吸收(唯一约束)——按行过滤后不该发生;兜底不丢启动
        await db.rollback()
        logger.warning("user_stars: legacy absorb hit conflicts; skipping")
        absorbed = 0
    legacy.rename(legacy.with_suffix(".json.absorbed"))
    logger.info("user_stars: absorbed {} legacy stars from stars.json", absorbed)
    return absorbed
