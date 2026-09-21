"""服务画像路由(服务画像方案 §5.3)— P1:热力网格 + 接口级线索板 + 自建卡。

* ``GET  /api/services/{service}/grid`` — 全员可读(纯读派生层);
* ``GET  /api/endpoints/{endpoint_id}/board`` — 线索板(``endpoint_id``
  是点分命名空间,用 ``:path`` 转换器,同 endpoint_catalog 既有写法);
* ``/api/board-cards`` — 自建卡 CRUD + promote,权限边界 = 作者(§3.3)。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..schemas.service_profile import (
    BoardResponse,
    CardCreate,
    CardOut,
    CardPatch,
    ServiceGrid,
)
from ..services import board_assembler, board_cards
from ..services.board_cards import CardForbidden

router = APIRouter(prefix="/services", tags=["service-profile"])
board_router = APIRouter(prefix="/endpoints", tags=["service-profile"])
cards_router = APIRouter(prefix="/board-cards", tags=["service-profile"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/{service}/grid", response_model=ServiceGrid)
async def service_grid(service: str, user: CurrentUser, db: DbSession) -> ServiceGrid:
    """服务级热力网格:一屏全接口 + 四格信号 + 盲区统计(§2)。"""
    return ServiceGrid.model_validate(await board_assembler.grid(db, service))


@board_router.get("/{endpoint_id:path}/board", response_model=BoardResponse)
async def endpoint_board(
    user: CurrentUser,
    db: DbSession,
    endpoint_id: str = Path(min_length=1),
    expand: str | None = Query(default=None),
) -> BoardResponse:
    """接口级线索板:主体 + 测试象限 + 自建卡 + trails(§3)。

    ``?expand=<nodeId>`` 拉该节点的二度关联(P1 支持场景节点 → 它引用
    的其他接口),默认只拉一度,避免一次拉巨图。
    """
    return BoardResponse.model_validate(
        await board_assembler.board(db, endpoint_id, user_id=user.id, expand=expand)
    )


def _card_http(e: Exception) -> HTTPException:
    if isinstance(e, CardForbidden):
        return HTTPException(status.HTTP_403_FORBIDDEN, "not_card_author")
    if isinstance(e, KeyError):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    if isinstance(e, ValueError):
        return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    raise e


@cards_router.post("", response_model=CardOut, status_code=201)
async def create_card(
    user: CurrentUser, body: CardCreate, db: DbSession,
) -> CardOut:
    try:
        return CardOut.model_validate(await board_cards.create_card(
            db, user_id=user.id,
            author_name=user.display_name or user.username,
            subject_id=body.subject_id, body=body.body,
            quadrant=body.quadrant,
            annotates_node_id=body.annotates_node_id,
        ))
    except Exception as e:  # noqa: BLE001 — 统一翻译为 HTTP
        raise _card_http(e) from e


@cards_router.patch("/{card_id}", response_model=CardOut)
async def patch_card(
    card_id: int, user: CurrentUser, body: CardPatch, db: DbSession,
) -> CardOut:
    try:
        # 显式传 null = 清空注解;字段缺省 = 不动 → service 层哨兵(...)
        explicit = ("annotates_node_id" in body.model_fields_set
                    or "annotatesNodeId" in body.model_fields_set)
        return CardOut.model_validate(await board_cards.patch_card(
            db, card_id, user_id=user.id, body=body.body,
            quadrant=body.quadrant,
            annotates_node_id=body.annotates_node_id if explicit else ...,
        ))
    except Exception as e:  # noqa: BLE001
        raise _card_http(e) from e


@cards_router.delete("/{card_id}", status_code=204)
async def delete_card(card_id: int, user: CurrentUser, db: DbSession) -> None:
    try:
        await board_cards.delete_card(db, card_id, user_id=user.id)
    except Exception as e:  # noqa: BLE001
        raise _card_http(e) from e


@cards_router.post("/{card_id}/promote", response_model=CardOut)
async def promote_card(card_id: int, user: CurrentUser, db: DbSession) -> CardOut:
    """设为 root:同主体降旧升新,单条 UPDATE 原子完成(§3.3)。"""
    try:
        return CardOut.model_validate(
            await board_cards.promote_card(db, card_id, user_id=user.id)
        )
    except Exception as e:  # noqa: BLE001
        raise _card_http(e) from e


@cards_router.post("/{card_id}/demote", response_model=CardOut)
async def demote_card(card_id: int, user: CurrentUser, db: DbSession) -> CardOut:
    """降级:腾出 root 槽位,卡回到自己所属象限(§3.3)。"""
    try:
        return CardOut.model_validate(
            await board_cards.demote_card(db, card_id, user_id=user.id)
        )
    except Exception as e:  # noqa: BLE001
        raise _card_http(e) from e
