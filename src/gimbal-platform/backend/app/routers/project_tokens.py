"""项目令牌管理面(authz M2b Q2,m2b-detail §2.6)。

项目令牌 = 以「项目用户」权限访问单个项目的外部调用身份(``kind=
'project'``):区锁到本项目、执行恒用项目凭证;负责人(holder)是指定的
一位项目管理员,承担问责 / 通知,执行记录属主 = 调用时的负责人。

Endpoints(前缀 ``/projects/{project_id}/tokens``;门 = 项目管理员,
与 S8 项目凭证同门:r5-2.2 口径 Admin+ 不旁路 —— 令牌是项目的,
不是平台的;非成员 404、成员非管理员 403;公共项目 409):

- GET  ``""``                    列表(含负责人 / 待确认 / 负责人是否合格)
- GET  ``/scope-candidates``     范围候选 = 全部服务别名 + 本项目凭证
- POST ``""``                    签发(holderId 缺省 = 发起人,须是项目
                                 管理员);明文只返回一次;每项目 5 枚
- GET  ``/{tid}``                详情(范围 / 注册任务预检 / 最近调用)
- POST ``/{tid}/renew`` · ``/regenerate`` · PUT ``/{tid}/scope`` ·
  PUT ``/{tid}/callback`` · POST ``/{tid}/callback-secret/rotate`` ·
  DELETE ``/{tid}``              与个人令牌同语义(复用 access_tokens 核心)
- PUT  ``/{tid}/holder``         换绑:目标 = 发起人 → 立即生效;否则待
                                 目标确认(M4)
- POST ``/{tid}/holder/accept`` · ``/decline``  仅待确认的新负责人本人

写面另记审计 ``project.token.write``(资源 = 项目;detail = op / 令牌 id)。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, status
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..models.access_token import AccessToken
from ..models.auth_session import AuthSession
from ..models.project import Project, ProjectMember
from ..models.service_alias import ServiceAlias
from ..models.user import User
from ..services import access_token as at
from ..services import audit as audit_svc
from . import access_tokens as pt
from .projects import _audit, _my_role

router = APIRouter(prefix="/projects/{project_id}/tokens",
                   tags=["project-tokens"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
TokenId = Annotated[int, PathParam(ge=1)]


def _bad(code: str, message: str, status_code: int = 422) -> HTTPException:
    return HTTPException(status_code=status_code,
                         detail={"code": code, "message": message})


async def _load_normal_project(db: AsyncSession, project_id: int) -> Project:
    proj = await db.get(Project, project_id)
    if proj is None:
        raise _bad("not_found", f"project not found: {project_id}", 404)
    if proj.kind == "public":
        raise _bad("public_project_no_tokens",
                   "公共项目没有项目令牌(无成员;外部调用请用个人令牌)", 409)
    return proj


async def _manage_gate(db: AsyncSession, user, project_id: int) -> Project:
    # r5-2.2 同口径(S8 项目凭证 _manage_gate):管理门 = 项目管理员,
    # Admin+ 不旁路 —— 令牌是项目的,不是平台的(2026-11-11 收口,此前
    # 走 _require_manage 的 Admin+ 旁路与凭证面自相矛盾);非成员 404,
    # 成员非管理员 403
    proj = await _load_normal_project(db, project_id)
    my_role = await _my_role(db, user, proj.id)
    if my_role == "admin":
        return proj
    if my_role is None:
        raise _bad("not_found", f"project not found: {project_id}", 404)
    raise _bad("not_project_admin", "只有项目管理员能维护项目令牌", 403)


async def _get_ptoken(db: AsyncSession, proj: Project, tid: int) -> AccessToken:
    tok = await db.get(AccessToken, tid)
    if tok is None or not at.is_project_token(tok) \
            or tok.project_id != proj.id:
        raise _bad("token_not_found", f"令牌不存在: {tid}", 404)
    return tok


async def _is_project_admin(db: AsyncSession, project_id: int,
                            user_id: int) -> bool:
    role = (await db.execute(select(ProjectMember.role).where(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id))).scalar_one_or_none()
    return role == ProjectMember.ROLE_ADMIN


async def _labels(db: AsyncSession, ids: set) -> dict[int, str]:
    ids = {i for i in ids if i is not None}
    if not ids:
        return {}
    rows = (await db.execute(select(
        User.id, User.username, User.display_name).where(
            User.id.in_(ids)))).all()
    return {uid: (dn or un) for uid, un, dn in rows}


async def _holder_fields(db: AsyncSession, tok: AccessToken,
                         labels: dict[int, str]) -> dict:
    problem = await at.holder_problem(db, tok)
    return {
        "projectId": tok.project_id,
        "holderId": tok.holder_id,
        "holderName": labels.get(tok.holder_id),
        "holderPendingId": tok.holder_pending_id,
        "holderPendingName": labels.get(tok.holder_pending_id),
        "holderValid": problem is None,
        "holderProblem": problem,
    }


async def _project_audit(db, user, proj: Project, op: str,
                         tok: AccessToken, **extra) -> None:
    try:
        await _audit(db, user, "project.token.write", proj, {
            "op": op, "tokenId": tok.id, "tokenName": tok.name, **extra})
    except Exception:  # noqa: BLE001 — 审计失败不阻断写面
        logger.opt(exception=True).warning("project token audit failed")


# ── 列表 / 候选 ──────────────────────────────────────────────────


@router.get("")
async def list_project_tokens(
    user: CurrentUser, db: DbSession, project_id: int,
) -> dict:
    proj = await _manage_gate(db, user, project_id)
    rows = (await db.execute(select(AccessToken).where(
        AccessToken.kind == at.PROJECT_KIND,
        AccessToken.project_id == proj.id).order_by(
            AccessToken.id.desc()))).scalars().all()
    ids = [r.id for r in rows]
    scopes = await pt._scope_counts(db, ids)
    tasks = await pt._task_counts(db, ids)
    labels = await _labels(db, {r.holder_id for r in rows}
                           | {r.holder_pending_id for r in rows})
    items = []
    for r in rows:
        items.append({
            **pt._token_out(
                r, scope=scopes.get(r.id, {"aliases": 0, "auths": 0}),
                tasks=tasks.get(r.id, {"total": 0, "unsatisfied": 0})),
            **await _holder_fields(db, r, labels)})
    used = sum(1 for r in rows if r.revoked_at is None)
    return {"items": items,
            "quota": {"used": used, "limit": at.TOKEN_LIMIT}}


@router.get("/scope-candidates")
async def project_scope_candidates(
    user: CurrentUser, db: DbSession, project_id: int,
) -> dict:
    proj = await _manage_gate(db, user, project_id)
    aliases = (await db.execute(select(ServiceAlias.alias_name).order_by(
        ServiceAlias.alias_name))).scalars().all()
    rows = (await db.execute(select(
        AuthSession.id, AuthSession.alias, AuthSession.slot).where(
            AuthSession.project_id == proj.id).order_by(
                AuthSession.slot, AuthSession.id))).all()
    return {"aliases": list(aliases),
            "auths": [{"id": rid, "alias": alias, "slot": slot}
                      for rid, alias, slot in rows]}


# ── 签发 ────────────────────────────────────────────────────────


class ProjectTokenCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    ttlDays: int = Field(default=at.TOKEN_DEFAULT_TTL_DAYS, ge=1,
                         le=at.TOKEN_MAX_TTL_DAYS)
    callbackUrl: str | None = Field(default=None, max_length=512)
    scope: pt.ScopeIn = Field(default_factory=pt.ScopeIn)
    # 负责人(缺省 = 发起人;须是本项目的项目管理员)
    holderId: int | None = Field(default=None, ge=1)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project_token(
    body: ProjectTokenCreateIn, user: CurrentUser, db: DbSession,
    project_id: int,
) -> dict:
    proj = await _manage_gate(db, user, project_id)
    holder_id = body.holderId or user.id
    if not await _is_project_admin(db, proj.id, holder_id):
        raise _bad("holder_not_project_admin",
                   "负责人必须是本项目的项目管理员", 422)
    secret_plain: str | None = None
    if body.callbackUrl:
        ok, _host = at.check_callback_url(body.callbackUrl)
        if not ok:
            raise _bad(at.ERR_CALLBACK_HOST_NOT_ALLOWED,
                       "回调主机不在白名单内(联系管理员配置 CALLBACK_HOST_"
                       "ALLOWLIST)")
    await pt._validate_scope_candidates(db, None, body.scope,
                                        project_id=proj.id)
    # 额度:每项目 5 枚(不含已吊销);锁项目行串行化并发签发
    await db.execute(select(Project.id).where(
        Project.id == proj.id).with_for_update())
    used = (await db.execute(select(func.count()).select_from(AccessToken)
        .where(AccessToken.kind == at.PROJECT_KIND,
               AccessToken.project_id == proj.id,
               AccessToken.revoked_at.is_(None)))).scalar_one()
    if used >= at.TOKEN_LIMIT:
        raise _bad(at.ERR_TOKEN_LIMIT_REACHED,
                   f"项目令牌额度已满({at.TOKEN_LIMIT} 张,不含已吊销)", 409)
    plaintext = at.generate_plaintext()
    tok = AccessToken(
        user_id=None, kind=at.PROJECT_KIND, project_id=proj.id,
        holder_id=holder_id, name=body.name.strip()[:64],
        token_hash=at.sha256_hex(plaintext),
        token_hint=at.token_hint_of(plaintext),
        expires_at=at.expire_at(body.ttlDays),
        callback_url=body.callbackUrl or None, created_by=user.id)
    if body.callbackUrl:
        secret_plain = at.generate_callback_secret()
        tok.callback_secret = at.encrypt_secret(secret_plain)
    db.add(tok)
    await db.flush()
    await pt._write_scope(db, tok, body.scope)
    await db.commit()
    await db.refresh(tok)
    await audit_svc.record(
        db, actor_id=user.id, actor_name=user.display_name or user.username,
        action="token.create", resource_type="access_token",
        resource_id=str(tok.id), resource_name=tok.name,
        detail={"kind": tok.kind, "project_id": proj.id,
                "holder_id": holder_id, "ttl_days": body.ttlDays,
                "scope": {"aliases": body.scope.aliases,
                          "auth_ids": body.scope.authIds},
                "callback_set": bool(body.callbackUrl)})
    await _project_audit(db, user, proj, "create", tok, holderId=holder_id)
    return {"id": tok.id, "token": plaintext, "callbackSecret": secret_plain}


# ── 详情 / 生命周期(复用个人令牌核心)─────────────────────────────


@router.get("/{tid}")
async def get_project_token(
    user: CurrentUser, db: DbSession, project_id: int, tid: TokenId,
) -> dict:
    proj = await _manage_gate(db, user, project_id)
    tok = await _get_ptoken(db, proj, tid)
    out = await pt.token_detail(db, tok)
    labels = await _labels(db, {tok.holder_id, tok.holder_pending_id})
    out.pop("ownerId", None)
    out.pop("ownerName", None)
    return {**out, **await _holder_fields(db, tok, labels)}


@router.post("/{tid}/renew")
async def renew_project_token(
    body: pt.TokenRenewIn, user: CurrentUser, db: DbSession,
    project_id: int, tid: TokenId,
) -> dict:
    proj = await _manage_gate(db, user, project_id)
    tok = await _get_ptoken(db, proj, tid)
    out = await pt.renew_core(db, user, tok, body)
    await _project_audit(db, user, proj, "renew", tok)
    return out


@router.post("/{tid}/regenerate")
async def regenerate_project_token(
    user: CurrentUser, db: DbSession, project_id: int, tid: TokenId,
) -> dict:
    proj = await _manage_gate(db, user, project_id)
    tok = await _get_ptoken(db, proj, tid)
    out = await pt.regenerate_core(db, user, tok)
    await _project_audit(db, user, proj, "regenerate", tok)
    return out


@router.put("/{tid}/scope")
async def put_project_token_scope(
    body: pt.ScopeIn, user: CurrentUser, db: DbSession,
    project_id: int, tid: TokenId, dryRun: bool = False,
) -> dict:
    proj = await _manage_gate(db, user, project_id)
    tok = await _get_ptoken(db, proj, tid)
    out = await pt.put_scope_core(db, user, tok, body, dry_run=dryRun)
    if not dryRun:
        await _project_audit(db, user, proj, "scope", tok)
    return out


@router.put("/{tid}/callback")
async def put_project_token_callback(
    body: pt.CallbackIn, user: CurrentUser, db: DbSession,
    project_id: int, tid: TokenId,
) -> dict:
    proj = await _manage_gate(db, user, project_id)
    tok = await _get_ptoken(db, proj, tid)
    out = await pt.put_callback_core(db, user, tok, body)
    await _project_audit(db, user, proj, "callback", tok)
    return out


@router.post("/{tid}/callback-secret/rotate")
async def rotate_project_token_secret(
    user: CurrentUser, db: DbSession, project_id: int, tid: TokenId,
) -> dict:
    proj = await _manage_gate(db, user, project_id)
    tok = await _get_ptoken(db, proj, tid)
    out = await pt.rotate_secret_core(db, user, tok)
    await _project_audit(db, user, proj, "rotate_secret", tok)
    return out


@router.delete("/{tid}")
async def revoke_project_token(
    user: CurrentUser, db: DbSession, project_id: int, tid: TokenId,
) -> dict:
    proj = await _manage_gate(db, user, project_id)
    tok = await _get_ptoken(db, proj, tid)
    out = await pt.revoke_core(db, user, tok)
    await _project_audit(db, user, proj, "revoke", tok)
    return out


# ── 换绑(M4)────────────────────────────────────────────────────


class HolderIn(BaseModel):
    userId: int = Field(ge=1)


async def _apply_holder(db: AsyncSession, tok: AccessToken,
                        new_holder: int) -> None:
    """换绑生效:负责人改写 + 令牌注册模板迁移(同事务)+ 复活。"""
    from ..services import integration_runner as ir

    tok.holder_id = new_holder
    tok.holder_pending_id = None
    await ir.rebind_token_templates(db, tok.id, new_holder)
    await db.commit()
    try:
        await ir.revive_paused_instances(token_id=tok.id)
    except Exception:  # noqa: BLE001 — 复活是增强
        logger.opt(exception=True).warning("project token: revive failed")


async def _notify(db: AsyncSession, user_id: int | None, title: str,
                  body: str, link: str) -> None:
    if user_id is None:
        return
    from ..services.notifications import create_notification
    try:
        await create_notification(db, user_id=user_id, type_="project_token",
                                  title=title, body=body, link=link)
    except Exception:  # noqa: BLE001 — 通知是增强
        logger.opt(exception=True).warning("project token notify failed")


@router.put("/{tid}/holder")
async def rebind_holder(
    body: HolderIn, user: CurrentUser, db: DbSession,
    project_id: int, tid: TokenId,
) -> dict:
    proj = await _manage_gate(db, user, project_id)
    tok = await _get_ptoken(db, proj, tid)
    if tok.revoked_at is not None:
        raise _bad(at.ERR_TOKEN_REVOKED, "令牌已吊销(终态只读)", 409)
    if not await _is_project_admin(db, proj.id, body.userId):
        raise _bad("holder_not_project_admin",
                   "负责人必须是本项目的项目管理员", 422)
    link = f"/projects/{proj.id}?tab=tokens"
    if body.userId == tok.holder_id:
        tok.holder_pending_id = None
        await db.commit()
        return {"id": tok.id, "holderId": tok.holder_id,
                "holderPendingId": None, "pending": False}
    if body.userId == user.id:
        # 换给自己:立即生效(本人即知情)
        old = tok.holder_id
        await _apply_holder(db, tok, body.userId)
        await _project_audit(db, user, proj, "holder", tok,
                             fromHolder=old, toHolder=body.userId)
        await _notify(db, old, f"项目令牌「{tok.name}」负责人已变更",
                      f"{user.display_name or user.username} 接任了负责人",
                      link)
        return {"id": tok.id, "holderId": tok.holder_id,
                "holderPendingId": None, "pending": False}
    tok.holder_pending_id = body.userId
    await db.commit()
    await _project_audit(db, user, proj, "holder_request", tok,
                         toHolder=body.userId)
    await _notify(db, body.userId, f"请确认接任项目令牌「{tok.name}」负责人",
                  f"{user.display_name or user.username} 请你接任项目"
                  f"「{proj.name}」令牌「{tok.name}」的负责人;确认前令牌"
                  "仍由原负责人负责", link)
    return {"id": tok.id, "holderId": tok.holder_id,
            "holderPendingId": tok.holder_pending_id, "pending": True}


async def _pending_gate(db: AsyncSession, user, project_id: int,
                        tid: int) -> tuple[Project, AccessToken]:
    proj = await _load_normal_project(db, project_id)
    tok = await _get_ptoken(db, proj, tid)
    if tok.holder_pending_id != user.id:
        raise _bad("token_not_found", f"令牌不存在: {tid}", 404)
    return proj, tok


@router.post("/{tid}/holder/accept")
async def accept_holder(
    user: CurrentUser, db: DbSession, project_id: int, tid: TokenId,
) -> dict:
    proj, tok = await _pending_gate(db, user, project_id, tid)
    if tok.revoked_at is not None:
        raise _bad(at.ERR_TOKEN_REVOKED, "令牌已吊销(终态只读)", 409)
    if not await _is_project_admin(db, proj.id, user.id):
        raise _bad("holder_not_project_admin",
                   "你已不是本项目的项目管理员,无法接任", 409)
    old = tok.holder_id
    await _apply_holder(db, tok, user.id)
    await _project_audit(db, user, proj, "holder_accept", tok,
                         fromHolder=old, toHolder=user.id)
    await _notify(db, old, f"项目令牌「{tok.name}」负责人已变更",
                  f"{user.display_name or user.username} 已确认接任负责人",
                  f"/projects/{proj.id}?tab=tokens")
    return {"id": tok.id, "holderId": tok.holder_id, "holderPendingId": None}


@router.post("/{tid}/holder/decline")
async def decline_holder(
    user: CurrentUser, db: DbSession, project_id: int, tid: TokenId,
) -> dict:
    proj, tok = await _pending_gate(db, user, project_id, tid)
    tok.holder_pending_id = None
    await db.commit()
    await _project_audit(db, user, proj, "holder_decline", tok)
    await _notify(db, tok.holder_id, f"项目令牌「{tok.name}」换绑被拒绝",
                  f"{user.display_name or user.username} 拒绝接任负责人",
                  f"/projects/{proj.id}?tab=tokens")
    return {"id": tok.id, "holderId": tok.holder_id, "holderPendingId": None}


# ── 项目删除 / 负责人失格的联动(projects / users 路由调用)──────────


async def revoke_all_for_project(db: AsyncSession, project_id: int) -> int:
    """项目删除:吊销该项目全部未吊销令牌(调用方 commit)。"""
    rows = (await db.execute(select(AccessToken).where(
        AccessToken.kind == at.PROJECT_KIND,
        AccessToken.project_id == project_id,
        AccessToken.revoked_at.is_(None)))).scalars().all()
    now = at.now_utc()
    for tok in rows:
        tok.revoked_at = now
    return len(rows)


async def notify_holder_lost(db: AsyncSession, project_id: int,
                             user_id: int) -> None:
    """负责人失格(移出 / 降级 / 停用)→ 通知该项目其余项目管理员换绑。
    best-effort;不落库状态(认证派生拒绝即生效)。"""
    try:
        toks = (await db.execute(select(AccessToken).where(
            AccessToken.kind == at.PROJECT_KIND,
            AccessToken.project_id == project_id,
            AccessToken.holder_id == user_id,
            AccessToken.revoked_at.is_(None)))).scalars().all()
        if not toks:
            return
        admins = (await db.execute(select(ProjectMember.user_id).where(
            ProjectMember.project_id == project_id,
            ProjectMember.role == ProjectMember.ROLE_ADMIN,
            ProjectMember.user_id != user_id))).scalars().all()
        names = "、".join(f"「{t.name}」" for t in toks)
        for aid in admins:
            await _notify(db, aid, "项目令牌待换绑负责人",
                          f"令牌 {names} 的负责人已失格,令牌暂不可用;"
                          "请在项目令牌页换绑负责人",
                          f"/projects/{project_id}?tab=tokens")
    except Exception:  # noqa: BLE001
        logger.opt(exception=True).warning("notify_holder_lost failed")
