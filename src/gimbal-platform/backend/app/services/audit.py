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
    "adaptation.batch.rollback",
    "alias.write",        # 别名登记/改/删
    # I4(集成线 v2 §3.2):外部目录只读标记 admin 写(误标 = 平台账号
    # 可能执行写操作,须留痕)
    "external_endpoint.query_safe",
    # (authz W3 死键退役,同 A3 先例:share.admin_revoke /
    # scenario.admin_delete / scenario.admin_publish / suite.admin_delete /
    # suite.admin_publish 随越属主旁路消亡,不再可写;历史行照常展示)
    "suite.admin_unpublish",  # admin 下架公共 suite 本体(§10;表 B steward)
    # ── 横向件补全轮(2026-10-20)──────────────────────────────
    # admin-only 特权写:平台凭证直接决定全体平台模式集成任务的认证面
    "integration.credential.write",  # 平台凭证登记/删除(admin)
    # admin 越属主的可见性变更(表 B steward:下架公共对象)—— 属主
    # 自操作不记(只记越属主那一半)
    "scenario.admin_unpublish",
    # ── 访问令牌(webhook v4 §7.2)──────────────────────────────
    "token.create",               # 签发(令牌 id、名称、kind、操作人)
    "token.renew",                # 续期
    "token.regenerate",           # 重新生成(新明文,不记明文)
    "token.revoke",               # 吊销
    "token.invalidate",           # 强制失效(原因 password/deactivated/admin)
    "token.scope.write",          # 范围整体替换(新旧)
    "token.callback.write",       # 回调地址改写(不记密钥)
    "token.callback_secret.rotate",  # 回调签名密钥轮换
    "token.task.unbind",          # 任务解绑令牌(D26)
    "integration.task.dispose",   # 删除用户时的集成任务处置(§3.6)
    # ── 入站发起的操作(webhook v4:资源列 = access_token / 令牌 id)──
    "inbound.run",                # 经令牌发起执行(场景 / 临时调用)
    "inbound.denied",             # 令牌请求被拒(拒绝原因与缺项;只记 hint)
    "inbound.task.write",         # 经令牌注册/修改/删除/触发集成任务
    # ── 回调投递的人工干预:admin / 令牌属主点补发
    "webhook.redeliver",          # 人工补发回调(新建一行 pending)
)


async def record(
    db: AsyncSession,
    *,
    actor_id: int | None,
    actor_name: str,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    resource_name: str | None = None,
    detail: dict | None = None,
) -> None:
    """落一条审计记录(best-effort:失败仅记日志,不抛)。

    ``resource_name``:资源名称快照,与 actor_name 同理 —— 资源事后被删,
    审计仍可读(读侧优先展示名称,旧记录回落 ``type:id``)。
    """
    from loguru import logger

    merged = dict(detail or {})
    if resource_name:
        merged.setdefault("resource_name", resource_name)
    try:
        db.add(AuditLog(
            actor_id=actor_id, actor_name=actor_name or "", action=action,
            resource_type=resource_type, resource_id=resource_id,
            detail=merged,
        ))
        await db.commit()
    except Exception as e:  # noqa: BLE001
        await db.rollback()
        logger.warning("audit: record {} failed: {}", action, e)


async def record_inbound(db: AsyncSession, principal, action: str, *,
                         detail: dict | None = None) -> None:
    """令牌发起的操作统一落审计(webhook v4 §7.2):JWT 调用方 no-op;
    actor 取 Principal.user(令牌属主或 ``__platform__``),资源列 =
    ``access_token`` / 令牌 id —— 令牌「最近调用」即按资源列取
    ``inbound.run`` ∪ ``inbound.denied``。detail 恒带令牌快照。"""
    if not getattr(principal, "is_token", False):
        return
    u = principal.user
    tok = principal.token
    await record(
        db, actor_id=u.id, actor_name=u.display_name or u.username,
        action=action, resource_type="access_token",
        resource_id=str(tok.id),
        detail={"token_id": tok.id, "token_name": tok.name,
                "token_kind": tok.kind, "identity_mode": principal.identity_mode,
                **(detail or {})})


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
