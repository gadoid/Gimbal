"""board_cards 读写(服务画像方案 §3.3/§5.3)。

权限边界 = 作者(方案裁定):作者可编辑/降级/删除,他人只读——
``board_cards.author_id`` 即边界,不另设权限表。promote 用**单条
UPDATE**(CASE 表达式)在同一语句内完成「降旧升新」,不存在两张
root 的中间态;唯一性兜底是 partial unique index ``uq_board_cards_root``
(先例:composer_run_schemes 的默认方案索引)。
"""
from __future__ import annotations

from sqlalchemy import case, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.timeutil import iso_naive_utc
from ..models.board_card import QUADRANTS, BoardCard


class CardForbidden(Exception):
    """非作者对卡片的写操作。"""


def card_out(card: BoardCard) -> dict:
    return {
        "id": card.id, "subjectKind": card.subject_kind,
        "subjectId": card.subject_id, "body": card.body,
        "isRoot": card.is_root, "quadrant": card.quadrant,
        "annotatesNodeId": card.annotates_node_id,
        "authorId": card.author_id,
        "createdAt": iso_naive_utc(card.created_at),
        "updatedAt": iso_naive_utc(card.updated_at),
    }


async def _get_owned(db: AsyncSession, card_id: int, user_id: int) -> BoardCard:
    card = await db.get(BoardCard, card_id)
    if card is None:
        raise KeyError(f"card_not_found: {card_id}")
    if card.author_id is None or card.author_id != user_id:
        # author_id NULL = 作者已注销 → 转只读(admin 接管旁路随 P2)
        raise CardForbidden(f"not_card_author: {card_id}")
    return card


async def create_card(
    db: AsyncSession, *, user_id: int, author_name: str, subject_id: str, body: str,
    quadrant: str, annotates_node_id: str | None = None,
) -> dict:
    if quadrant not in QUADRANTS:
        raise ValueError(f"bad_quadrant: {quadrant}")
    card = BoardCard(
        subject_kind="endpoint", subject_id=subject_id, body=body,
        quadrant=quadrant, annotates_node_id=annotates_node_id,
        author_id=user_id,
        # 姓名快照(M2):作者注销后卡片转只读、展示「已注销」(§2.1)
        author_name=author_name,
    )
    db.add(card)
    await db.commit()
    # server_default 时间列在异步会话里不会自动回填,显式刷新防懒加载
    await db.refresh(card)
    return card_out(card)


async def patch_card(
    db: AsyncSession, card_id: int, *, user_id: int,
    body: str | None = None, quadrant: str | None = None,
    annotates_node_id: str | None = ...,  # type: ignore[assignment]  # 哨兵:显式传 None = 清空
) -> dict:
    card = await _get_owned(db, card_id, user_id)
    if body is not None:
        card.body = body
    if quadrant is not None:
        if quadrant not in QUADRANTS:
            raise ValueError(f"bad_quadrant: {quadrant}")
        card.quadrant = quadrant
    if annotates_node_id is not ...:
        card.annotates_node_id = annotates_node_id
    await db.commit()
    await db.refresh(card)  # onupdate 时间列同上:刷新防懒加载
    return card_out(card)


async def delete_card(db: AsyncSession, card_id: int, *, user_id: int) -> None:
    card = await _get_owned(db, card_id, user_id)
    await db.delete(card)
    await db.commit()


async def promote_card(db: AsyncSession, card_id: int, *, user_id: int) -> dict:
    """设为 root:同主体内降旧升新,单条 UPDATE 原子完成(§3.3)。"""
    card = await _get_owned(db, card_id, user_id)
    await db.execute(
        update(BoardCard)
        .where(BoardCard.subject_kind == card.subject_kind,
               BoardCard.subject_id == card.subject_id)
        .values(is_root=case((BoardCard.id == card.id, True), else_=False))
    )
    await db.commit()
    await db.refresh(card)
    return card_out(card)


async def demote_card(db: AsyncSession, card_id: int, *, user_id: int) -> dict:
    """降级:腾出 root 槽位,卡回到自己所属象限(quadrant 一直在,§3.3)。"""
    card = await _get_owned(db, card_id, user_id)
    card.is_root = False
    await db.commit()
    await db.refresh(card)
    return card_out(card)
