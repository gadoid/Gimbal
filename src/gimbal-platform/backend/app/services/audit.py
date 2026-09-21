"""审计日志服务(P2-3,权限方案 §6)。

只记**特权写**——角色变更/删除用户/重置密码/公告/carry 写/适配 ops
应用/别名写;普通读与成员自身常规 CRUD 不记。best-effort:审计失败
不阻断业务(特权写已发生,审计是事后取证面,不因日志故障回滚操作)。
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.permission import AuditLog

# 动作词表(权限方案 §6 清单;新动作在此登记,便于审计 tab 过滤)
AUDIT_ACTIONS = (
    "user.create",        # admin 开号
    "user.role_change",   # 角色/启停/密码重置等人事写
    "user.delete",        # 删除用户(含处置方式)
    "user.reset_password",
    "announcement.publish",
    "carry.write",        # carry bindings/defaults 写
    "adaptation.op.apply",
    "adaptation.batch.apply",
    "adaptation.batch.rollback",
    "alias.write",        # 别名登记/改/删
)


async def record(
    db: AsyncSession,
    *,
    actor_id: int | None,
    actor_name: str,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: dict | None = None,
) -> None:
    """落一条审计记录(best-effort:失败仅记日志,不抛)。"""
    from loguru import logger

    try:
        db.add(AuditLog(
            actor_id=actor_id, actor_name=actor_name or "", action=action,
            resource_type=resource_type, resource_id=resource_id,
            detail=detail or {},
        ))
        await db.commit()
    except Exception as e:  # noqa: BLE001
        await db.rollback()
        logger.warning("audit: record {} failed: {}", action, e)


async def list_page(
    db: AsyncSession,
    *,
    action: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[AuditLog], int]:
    """审计查询(admin only;新→旧)。"""
    base = select(AuditLog)
    if action:
        base = base.where(AuditLog.action == action)
    total = (await db.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar_one()
    rows = (await db.execute(
        base.order_by(AuditLog.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return list(rows), int(total)
