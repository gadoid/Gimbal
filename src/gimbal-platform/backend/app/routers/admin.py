"""Admin 查询端点(P2-3:审计日志,admin only)。"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import AdminUser
from ..schemas.page import PageOut
from ..services import audit as audit_svc

router = APIRouter(prefix="/admin", tags=["admin"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    actor_id: int | None = Field(default=None, alias="actorId")
    actor_name: str = Field(default="", alias="actorName")
    action: str
    resource_type: str | None = Field(default=None, alias="resourceType")
    resource_id: str | None = Field(default=None, alias="resourceId")
    detail: dict = Field(default_factory=dict)
    created_at: datetime = Field(alias="createdAt")


class AuditLogPage(PageOut[AuditLogOut]):
    """M4 Page 信封(§6.3)+ 可过滤动作词表。"""

    actions: list[str] = Field(default_factory=list)


@router.get("/audit-logs", response_model=AuditLogPage)
async def list_audit_logs(
    user: AdminUser,
    db: DbSession,
    action: Annotated[str | None, Query(max_length=64)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AuditLogPage:
    """特权写审计(权限方案 §6):新→旧分页;``action`` 精确过滤;
    ``actions`` 带回词表供前端过滤 chip。"""
    rows, total = await audit_svc.list_page(
        db, action=action, page=page, page_size=page_size)
    return AuditLogPage(
        items=[AuditLogOut.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
        actions=list(audit_svc.AUDIT_ACTIONS),
    )
