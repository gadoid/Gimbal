"""访问令牌路由(webhook v4 §5.1)— 个人与平台令牌一组接口。

authz W5:所有注册用户可签发 / 使用 / 管理自己的个人令牌(写面 =
属主 ∨ users.manage 管理);平台令牌**入口已关**(签发/scope 候选 →
410,C1 退役存量),存量平台令牌的列表与写面暂维持 ops.write。
super_admin 另有查看全部(``?all=1``)与强制失效(用户管理职责,
dev-plan W4「勿扩大化」)。

令牌明文与回调签名密钥只展示一次(D10);已吊销令牌只读(§3.4)。
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..core.timeutil import iso_utc_z
from ..models.access_token import AccessToken, AccessTokenScope
from ..models.auth_session import AuthSession
from ..models.integration_task import IntegrationTask
from ..models.permission import AuditLog
from ..models.service_alias import ServiceAlias
from ..models.user import User
from ..services import access_token as at
from ._ownership import has_capability
from ..services import audit as audit_svc
from ..services.cron_expr import describe_cron

router = APIRouter(prefix="/access-tokens", tags=["access-tokens"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


def _bad(code: str, message: str, status_code: int = 422) -> HTTPException:
    return HTTPException(status_code=status_code,
                         detail={"code": code, "message": message})


def _iso(dt) -> "str | None":
    return iso_utc_z(dt) if dt is not None else None


# ── 装载与序列化 ────────────────────────────────────────────────


async def _get_token(db: AsyncSession, token_id: int) -> AccessToken:
    tok = await db.get(AccessToken, token_id)
    if tok is None:
        raise _bad("token_not_found", f"令牌不存在: {token_id}", 404)
    return tok


def _require_view(user: User, tok: AccessToken) -> None:
    """详情闸 = can_view(本人 ∨ 平台令牌面)∨ users.manage(管理面)。

    authz W4 的执行可见收敛只收紧**运营面**(executions/webhook 投递
    按 tokenId 查走的 can_view);令牌详情是用户管理职责的一部分
    (dev-plan W4「勿扩大化」:super_admin 可 all=1 列表 + 强制失效,
    详情随管理面保留)。"""
    if not at.can_view(user, tok) and not has_capability(user, "users.manage"):
        raise _bad("token_not_found", f"令牌不存在: {tok.id}", 404)


def _require_manage(user: User, tok: AccessToken) -> None:
    """写面(authz W5,表 A 驱动):属主(任意角色)∨ users.manage
    (管理面)。旧口径「admin+ 可代管他人个人令牌 / 属主 user 角色仅
    吊销豁免」随签发开放一并收编 —— 代管是用户管理职责,归
    users.manage。authz C1:平台令牌分支随平台模式退役。"""
    if tok.user_id == user.id or has_capability(user, "users.manage"):
        return
    raise _bad("token_not_found", f"令牌不存在: {tok.id}", 404)


async def _scope_counts(db: AsyncSession, token_ids: list[int]) -> dict[int, dict]:
    if not token_ids:
        return {}
    rows = (await db.execute(
        select(AccessTokenScope.token_id,
               func.count(AccessTokenScope.alias_name),
               func.count(AccessTokenScope.auth_id))
        .where(AccessTokenScope.token_id.in_(token_ids))
        .group_by(AccessTokenScope.token_id))).all()
    return {tid: {"aliases": na, "auths": nu} for tid, na, nu in rows}


async def _task_counts(db: AsyncSession, token_ids: list[int]) -> dict[int, dict]:
    """注册任务数(含不满足数)。不满足 = 按 §3.3 分类有缺项。"""
    out: dict[int, dict] = {tid: {"total": 0, "unsatisfied": 0}
                            for tid in token_ids}
    if not token_ids:
        return out
    tpls = (await db.execute(select(IntegrationTask).where(
        IntegrationTask.template_id.is_(None),
        IntegrationTask.removed_at.is_(None),
        IntegrationTask.token_id.in_(token_ids)))).scalars().all()
    by_token: dict[int, list[IntegrationTask]] = {}
    for t in tpls:
        by_token.setdefault(t.token_id, []).append(t)
        out.setdefault(t.token_id, {"total": 0, "unsatisfied": 0})
        out[t.token_id]["total"] += 1
    for tid, tasks in by_token.items():
        tok = await _get_token(db, tid)
        scope_aliases, scope_auths = await at.load_scope(db, tid)
        for tpl in tasks:
            missing = await _task_missing(db, tpl, tok,
                                          scope_aliases, scope_auths)
            if missing:
                out[tid]["unsatisfied"] += 1
    return out


async def _task_missing(
    db: AsyncSession, tpl: IntegrationTask, tok: AccessToken,
    scope_aliases: set, scope_auths: set,
) -> "list[at.ScopeMissing] | None":
    """单个注册任务的缺项(§3.3 #6 分类;与运行前复核同一口径 ——
    子集判定走 ``services.check_scope`` 单一实现(§3.2),范围集由
    调用方预载传入,免逐任务重查)。"""
    from ..models.composer_scenario import ComposerScenario
    from ..services.scenario_store import definition_from_payload

    scen = (await db.execute(select(ComposerScenario).where(
        ComposerScenario.scenario_id == tpl.scenario_id))).scalar() \
        if tpl.scenario_id else None
    if scen is None:
        return None      # 场景缺失走 run 面报错,不是范围缺项
    bindings = await _task_bindings(db, tpl, scen)
    used = await at.used_sets_for_definition(
        db, definition_from_payload(scen.payload), bindings)
    return await at.check_scope(db, tok, tok.user_id, used,
                                scope=(scope_aliases, scope_auths))


async def _task_bindings(db: AsyncSession, tpl, scen) -> dict:
    from ..services.scheme_store import resolve_for_run
    scheme = await resolve_for_run(db, scen.scenario_id, tpl.scheme_id)
    payload = (scheme.payload if scheme else {}) or {}
    return dict(payload.get("serviceBindings") or {})


def _token_out(
    tok: AccessToken, *, scope: dict, tasks: dict,
    owner_label: "str | None" = None, include_owner: bool = False,
) -> dict:
    out: dict[str, Any] = {
        "id": tok.id,
        "kind": tok.kind,
        "name": tok.name,
        "tokenHint": tok.token_hint,
        "status": tok.status,
        "invalidatedReason": tok.invalidated_reason,
        "invalidationNote": tok.invalidation_note,
        "expiresAt": _iso(tok.expires_at),
        "invalidatedAt": _iso(tok.invalidated_at),
        "revokedAt": _iso(tok.revoked_at),
        "lastUsedAt": _iso(tok.last_used_at),
        "createdAt": _iso(tok.created_at),
        "callbackUrl": tok.callback_url,
        "callbackSecretSet": bool(tok.callback_secret),
        # 派生提示(§5.1):已设回调但密钥解不开(FERNET_KEY 轮换)
        "signingKeyUsable": (False if tok.callback_url and not tok.callback_secret
                             else at.secret_usable(tok)) if tok.callback_url
        or tok.callback_secret else None,
        "scopeCounts": scope,
        "taskCounts": tasks,
    }
    if include_owner:
        out["ownerId"] = tok.user_id
        out["ownerName"] = owner_label
    return out


async def _owner_labels(db: AsyncSession, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    rows = (await db.execute(
        select(User.id, User.username, User.display_name).where(
            User.id.in_(ids)))).all()
    return {uid: (dn or un) for uid, un, dn in rows}


# ── 列表 / 候选 / 详情 ──────────────────────────────────────────


@router.get("")
async def list_tokens(
    user: CurrentUser, db: DbSession,
    kind: Annotated[str, Query(max_length=16)] = "personal",
    all_view: Annotated[bool, Query(alias="all")] = False,
    owner: Annotated[int | None, Query(ge=1)] = None,
    owner_name: Annotated[str | None, Query(alias="ownerName",
                                            max_length=64)] = None,
    status_filter: Annotated[str | None, Query(alias="status",
                                               max_length=16)] = None,
) -> dict:
    """令牌列表。``kind=personal``:本人;``all=1``(users.manage):
    全部,可按属主(id 或用户名/昵称模糊,2026-11-05 评审 P2-6:管理员
    通常不知道数字 id)与状态过滤。authz C1:kind=platform 面退役。
    不返回明文与密钥。"""
    if all_view:
        if not has_capability(user, "users.manage"):
            raise _bad("capability_forbidden", "查看全部令牌需能力 users.manage", 403)
        q = select(AccessToken)
        if kind == at.PERSONAL_KIND:
            q = q.where(AccessToken.kind == kind)
        if owner is not None:
            q = q.where(AccessToken.user_id == owner)
        if owner_name:
            # 转义 LIKE 通配符:输入里的 % / _ 按字面匹配(修复轮评审 P3-3)
            pat = "%" + (owner_name.replace("\\", "\\\\")
                         .replace("%", "\\%").replace("_", "\\_")) + "%"
            matched = (await db.execute(select(User.id).where(or_(
                User.username.ilike(pat, escape="\\"),
                User.display_name.ilike(pat, escape="\\"))))).scalars().all()
            q = q.where(AccessToken.user_id.in_(matched or [-1]))
        if status_filter in ("active", "expired", "invalidated", "revoked"):
            # 状态是派生值:先取全部再过滤(量级 = 全平台令牌数,可接受)
            rows = (await db.execute(q.order_by(AccessToken.id.desc()))).scalars().all()
            rows = [r for r in rows if r.status == status_filter]
        else:
            rows = (await db.execute(q.order_by(AccessToken.id.desc()))).scalars().all()
    else:
        if kind == at.PERSONAL_KIND:
            q = select(AccessToken).where(
                AccessToken.kind == kind, AccessToken.user_id == user.id)
        else:
            raise _bad("kind_invalid", "kind ∈ personal")
        rows = (await db.execute(q.order_by(AccessToken.id.desc()))).scalars().all()
    ids = [r.id for r in rows]
    scopes = await _scope_counts(db, ids)
    tasks = await _task_counts(db, ids)
    include_owner = all_view
    labels: dict[int, str] = {}
    if include_owner:
        labels = await _owner_labels(db, {r.user_id for r in rows})
    items = [
        _token_out(r,
                   scope=scopes.get(r.id, {"aliases": 0, "auths": 0}),
                   tasks=tasks.get(r.id, {"total": 0, "unsatisfied": 0}),
                   owner_label=labels.get(r.user_id),
                   include_owner=include_owner)
        for r in rows
    ]
    # 额度提示(不含已吊销,D3)
    active_n = sum(1 for r in rows if r.revoked_at is None
                   and r.kind == kind)
    return {"items": items,
            "quota": {"used": active_n, "limit": at.TOKEN_LIMIT}}


@router.get("/scope-candidates")
async def scope_candidates(
    user: CurrentUser, db: DbSession,
    kind: Annotated[str, Query(max_length=16)] = "personal",
) -> dict:
    """范围候选(§5.1):全部服务别名 + 本人凭证池。authz C1:平台
    候选面(平台凭证池)随平台模式退役。"""
    if kind != at.PERSONAL_KIND:
        raise _bad("kind_invalid", "kind ∈ personal")
    holder = user.id
    aliases = (await db.execute(
        select(ServiceAlias.alias_name).order_by(ServiceAlias.alias_name))
    ).scalars().all()
    auths: list[dict] = []
    if holder is not None:
        rows = (await db.execute(
            select(AuthSession.id, AuthSession.alias).where(
                AuthSession.owner_id == holder)
            .order_by(AuthSession.alias))).all()
        auths = [{"id": rid, "alias": alias} for rid, alias in rows]
    return {"aliases": list(aliases), "auths": auths}


# ── 创建 ────────────────────────────────────────────────────────


class ScopeIn(BaseModel):
    aliases: list[str] = Field(default_factory=list, max_length=200)
    authIds: list[int] = Field(default_factory=list, max_length=200)


class TokenCreateIn(BaseModel):
    kind: str = Field(default="personal", max_length=16)
    name: str = Field(min_length=1, max_length=64)
    ttlDays: int = Field(default=at.TOKEN_DEFAULT_TTL_DAYS, ge=1,
                         le=at.TOKEN_MAX_TTL_DAYS)
    callbackUrl: str | None = Field(default=None, max_length=512)
    scope: ScopeIn = Field(default_factory=ScopeIn)


@router.post("", status_code=201)
async def create_token(
    body: TokenCreateIn, user: CurrentUser, db: DbSession,
) -> dict:
    """签发(§5.1):额度事务内计数;回调主机白名单;一次性返回
    ``{token, callbackSecret?}`` —— 明文只此一次(D10)。"""
    if body.kind != at.PERSONAL_KIND:
        raise _bad("kind_invalid", "kind ∈ personal")
    owner_id = user.id

    callback_secret_plain: "str | None" = None
    if body.callbackUrl:
        ok, _host = at.check_callback_url(body.callbackUrl)
        if not ok:
            raise _bad(
                at.ERR_CALLBACK_HOST_NOT_ALLOWED,
                "回调主机不在白名单内(联系管理员配置 CALLBACK_HOST_"
                "ALLOWLIST;空白名单 = 不允许任何回调地址)")
    # 与 PUT /scope 同款范围对象校验(评审 2026-11-05 P2:此前直写
    # _write_scope,别名不存在触发外键 500、他人凭证 id 落脏数据)
    await _validate_scope_candidates(db, owner_id, body.scope)

    # 额度:同 kind 未吊销计数(平台令牌全平台共享 5 张,D3)。
    # §5.1「事务内锁行计数」:锁属主 users 行(个人 = 本人,平台 =
    # __platform__)串行化同一属主的并发创建 —— 计数与插入都在持锁
    # 事务内完成(:366 commit 才放锁),不会超发;不同属主互不阻塞。
    await db.execute(
        select(User.id).where(User.id == owner_id).with_for_update())
    used = (await db.execute(select(func.count()).select_from(AccessToken)
        .where(AccessToken.kind == body.kind,
               AccessToken.user_id == owner_id,
               AccessToken.revoked_at.is_(None)))).scalar_one()
    if used >= at.TOKEN_LIMIT:
        raise _bad(at.ERR_TOKEN_LIMIT_REACHED,
                   f"令牌额度已满({at.TOKEN_LIMIT} 张,不含已吊销;"
                   "可吊销闲置令牌腾出额度)", 409)

    plaintext = at.generate_plaintext()
    tok = AccessToken(
        user_id=owner_id, kind=body.kind, name=body.name.strip()[:64],
        token_hash=at.sha256_hex(plaintext),
        token_hint=at.token_hint_of(plaintext),
        expires_at=at.expire_at(body.ttlDays),
        callback_url=body.callbackUrl or None,
        created_by=user.id)
    if body.callbackUrl:
        # 首开即发密钥(照搬 v3 口径):设置地址即生成签名密钥,明文随
        # 本次响应返回一次,否则接收方无从验签
        callback_secret_plain = at.generate_callback_secret()
        tok.callback_secret = at.encrypt_secret(callback_secret_plain)
    db.add(tok)
    await db.flush()
    await _write_scope(db, tok, body.scope)
    await db.commit()
    await db.refresh(tok)
    await audit_svc.record(
        db, actor_id=user.id, actor_name=user.display_name or user.username,
        action="token.create", resource_type="access_token",
        resource_id=str(tok.id), resource_name=tok.name,
        detail={"kind": tok.kind, "ttl_days": body.ttlDays,
                "scope": {"aliases": body.scope.aliases,
                          "auth_ids": body.scope.authIds},
                "callback_set": bool(body.callbackUrl)})
    return {"id": tok.id, "token": plaintext,
            "callbackSecret": callback_secret_plain}


async def _validate_scope_candidates(
    db: AsyncSession, owner_id: int, scope: ScopeIn,
) -> None:
    """范围对象必须存在且属该池:防把别人的凭证 id 塞进范围(否则
    子集判定会静默放行越权资源)。"""
    if scope.aliases:
        rows = (await db.execute(select(ServiceAlias.alias_name).where(
            ServiceAlias.alias_name.in_(set(scope.aliases))))).scalars().all()
        unknown = sorted(set(scope.aliases) - set(rows))
        if unknown:
            raise _bad("scope_alias_unknown",
                       "服务别名不存在: " + "、".join(unknown))
    if scope.authIds:
        n = (await db.execute(select(func.count()).select_from(AuthSession)
            .where(AuthSession.owner_id == owner_id,
                   AuthSession.id.in_(set(scope.authIds))))).scalar_one()
        if n != len(set(scope.authIds)):
            raise _bad("scope_auth_unknown",
                       "凭证不存在或不属于该令牌的凭证池")


async def _write_scope(db: AsyncSession, tok: AccessToken, scope: ScopeIn) -> None:
    """范围整体替换(PUT /scope 与创建共用)。"""
    await db.execute(AccessTokenScope.__table__.delete().where(
        AccessTokenScope.token_id == tok.id))
    for alias in dict.fromkeys(scope.aliases):
        db.add(AccessTokenScope(token_id=tok.id, alias_name=alias))
    for aid in dict.fromkeys(scope.authIds):
        db.add(AccessTokenScope(token_id=tok.id, auth_id=aid))


# ── 详情 / 范围 / 生命周期 ──────────────────────────────────────


@router.get("/{token_id}")
async def get_token(token_id: int, user: CurrentUser, db: DbSession) -> dict:
    """详情:范围、回调、注册任务(逐个预检,缺项按 §3.3 分类)、
    最近调用(§7.2,含被拒)。"""
    tok = await _get_token(db, token_id)
    _require_view(user, tok)
    scope_aliases, scope_auths = await at.load_scope(db, tok.id)
    # 范围明细(名称化:凭证 id → 别名)
    auth_rows: dict[int, str] = {}
    if scope_auths:
        rows = (await db.execute(select(AuthSession.id, AuthSession.alias).where(
            AuthSession.owner_id == tok.user_id,
            AuthSession.id.in_(scope_auths)))).all()
        auth_rows = {rid: alias for rid, alias in rows}
    # 注册任务逐个预检
    tpls = (await db.execute(select(IntegrationTask).where(
        IntegrationTask.template_id.is_(None),
        IntegrationTask.removed_at.is_(None),
        IntegrationTask.token_id == tok.id)
        .order_by(IntegrationTask.id))).scalars().all()
    tasks_out = []
    for tpl in tpls:
        missing = await _task_missing(db, tpl, tok, scope_aliases, scope_auths)
        tasks_out.append({
            "id": tpl.id, "name": tpl.name,
            "cronText": describe_cron(tpl.trigger_cron),
            "triggerCron": tpl.trigger_cron,
            "satisfied": missing is None,
            "missing": [
                {"kind": m.kind, "name": m.name, "deleted": m.deleted}
                for m in (missing or [])],
            "hint": at.missing_hint(missing) if missing else "",
        })
    # 最近调用:审计 access_token/令牌 id 的 inbound.run ∪ inbound.denied
    calls = (await db.execute(
        select(AuditLog).where(
            AuditLog.resource_type == "access_token",
            AuditLog.resource_id == str(tok.id),
            AuditLog.action.in_(("inbound.run", "inbound.denied")))
        .order_by(AuditLog.id.desc()).limit(50))).scalars().all()
    exec_ids = [d.get("execution") for c in calls
                if c.action == "inbound.run"
                and isinstance((d := c.detail or {}).get("execution"), int)]
    exec_status: dict[int, dict] = {}
    if exec_ids:
        from ..models.execution import Execution
        rows = (await db.execute(select(
            Execution.id, Execution.status, Execution.config_json).where(
            Execution.id.in_(exec_ids)))).all()
        for eid, st, cfg in rows:
            exec_status[eid] = {
                "status": st,
                "outOfScope": bool((cfg or {}).get("outOfScope", {}).get(
                    "targets") or (cfg or {}).get("outOfScope", {}).get(
                    "builtinAuths") or (cfg or {}).get("outOfScope", {}).get(
                    "strategyEntries")) if isinstance(cfg, dict) else False}
    calls_out = [{
        "id": c.id, "action": c.action,
        "at": _iso(c.created_at),
        "denied": c.action == "inbound.denied",
        "reason": (c.detail or {}).get("reason"),
        "scenarioName": (c.detail or {}).get("scenario_name"),
        "fn": (c.detail or {}).get("fn"),
        "executionId": (c.detail or {}).get("execution"),
        "clientRef": (c.detail or {}).get("client_ref"),
        **(exec_status.get((c.detail or {}).get("execution"))
           if c.action == "inbound.run"
           and isinstance((c.detail or {}).get("execution"), int) else {}),
    } for c in calls]
    scopes = (await _scope_counts(db, [tok.id])).get(
        tok.id, {"aliases": 0, "auths": 0})
    tasks = {"total": len(tasks_out),
             "unsatisfied": sum(1 for t in tasks_out if not t["satisfied"])}
    owner_labels = await _owner_labels(db, {tok.user_id})
    return {
        **_token_out(tok, scope=scopes, tasks=tasks,
                     owner_label=owner_labels.get(tok.user_id),
                     include_owner=True),
        "scope": {"aliases": sorted(scope_aliases),
                  "auths": [{"id": rid, "alias": auth_rows[rid]}
                            for rid in sorted(scope_auths)
                            if rid in auth_rows]},
        "tasks": tasks_out,
        "recentCalls": calls_out,
    }


class TokenRenewIn(BaseModel):
    ttlDays: int = Field(ge=1, le=at.TOKEN_MAX_TTL_DAYS)


@router.post("/{token_id}/renew")
async def renew_token(
    token_id: int, body: TokenRenewIn, user: CurrentUser, db: DbSession,
) -> dict:
    """续期:新到期 = now + ttlDays,明文与 id 不变;已失效 409
    (须重新生成)。到期暂停的注册实例自动恢复。"""
    tok = await _get_token(db, token_id)
    _require_manage(user, tok)
    try:
        at.ensure_active_for_write(tok)
    except at.TokenAuthError as e:
        raise _bad(e.code, e.message, e.status_code)
    if tok.invalidated_at is not None:
        raise _bad(at.ERR_REGENERATE_REQUIRED,
                   "令牌已失效,不能续期;请重新生成", 409)
    tok.expires_at = at.expire_at(body.ttlDays)
    await db.commit()
    await audit_svc.record(
        db, actor_id=user.id, actor_name=user.display_name or user.username,
        action="token.renew", resource_type="access_token",
        resource_id=str(tok.id), resource_name=tok.name,
        detail={"ttl_days": body.ttlDays})
    await at.revive_token_tasks(db, tok)
    return {"id": tok.id, "expiresAt": _iso(tok.expires_at)}


@router.post("/{token_id}/regenerate")
async def regenerate_token(
    token_id: int, user: CurrentUser, db: DbSession,
) -> dict:
    """重新生成:新明文/hint/hash,清失效,重设有效期(缺省 TTL);
    失效与到期暂停的注册实例自动恢复,运行中的任务不受影响。"""
    tok = await _get_token(db, token_id)
    _require_manage(user, tok)
    try:
        at.ensure_active_for_write(tok)
    except at.TokenAuthError as e:
        raise _bad(e.code, e.message, e.status_code)
    plaintext = at.rotate_plaintext(tok)
    tok.invalidated_at = None
    tok.invalidated_reason = None
    tok.invalidation_note = None
    tok.expires_at = at.expire_at(at.TOKEN_DEFAULT_TTL_DAYS)
    await db.commit()
    await audit_svc.record(
        db, actor_id=user.id, actor_name=user.display_name or user.username,
        action="token.regenerate", resource_type="access_token",
        resource_id=str(tok.id), resource_name=tok.name,
        detail={"kind": tok.kind})
    await at.revive_token_tasks(db, tok)
    return {"id": tok.id, "token": plaintext,
            "expiresAt": _iso(tok.expires_at)}


@router.put("/{token_id}/scope")
async def put_scope(
    token_id: int, body: ScopeIn, user: CurrentUser, db: DbSession,
    dry_run: Annotated[bool, Query(alias="dryRun")] = False,
) -> dict:
    """范围整体替换;``?dryRun=1`` 只返回将不满足的任务(前端收紧前
    确认)。空维度合法(D4:某维度为空即不允许任何该类资源)。"""
    tok = await _get_token(db, token_id)
    _require_manage(user, tok)
    try:
        at.ensure_active_for_write(tok)
    except at.TokenAuthError as e:
        raise _bad(e.code, e.message, e.status_code)
    await _validate_scope_candidates(db, tok.user_id, body)
    # 试算:以新范围对全部注册任务预检
    scope_aliases, scope_auths = await at.load_scope(db, tok.id)
    tpls = (await db.execute(select(IntegrationTask).where(
        IntegrationTask.template_id.is_(None),
        IntegrationTask.removed_at.is_(None),
        IntegrationTask.token_id == tok.id))).scalars().all()
    unsatisfied: list[dict] = []
    new_aliases, new_auths = set(body.aliases), set(body.authIds)
    for tpl in tpls:
        missing = await _task_missing(db, tpl, tok, new_aliases, new_auths)
        if missing:
            unsatisfied.append({
                "id": tpl.id, "name": tpl.name,
                "missing": [{"kind": m.kind, "name": m.name,
                             "deleted": m.deleted} for m in missing]})
    if dry_run:
        return {"unsatisfied": unsatisfied}
    old = {"aliases": sorted(scope_aliases), "authIds": sorted(scope_auths)}
    await _write_scope(db, tok, body)
    await db.commit()
    await audit_svc.record(
        db, actor_id=user.id, actor_name=user.display_name or user.username,
        action="token.scope.write", resource_type="access_token",
        resource_id=str(tok.id), resource_name=tok.name,
        detail={"from": old, "to": {"aliases": body.aliases,
                                    "authIds": body.authIds}})
    return {"unsatisfied": unsatisfied}


class CallbackIn(BaseModel):
    url: str | None = Field(default=None, max_length=512)


@router.put("/{token_id}/callback")
async def put_callback(
    token_id: int, body: CallbackIn, user: CurrentUser, db: DbSession,
) -> dict:
    """改回调地址;设置地址时若无签名密钥则自动生成并一次性返回
    (照搬 v3 首开即发);清空地址保留密钥(§3.4)。已吊销令牌 409
    (在途事件不得被转发到别处)。"""
    tok = await _get_token(db, token_id)
    _require_manage(user, tok)
    try:
        at.ensure_active_for_write(tok)
    except at.TokenAuthError as e:
        raise _bad(e.code, e.message, e.status_code)
    new_secret: "str | None" = None
    old_url = tok.callback_url
    if body.url:
        ok, _host = at.check_callback_url(body.url)
        if not ok:
            raise _bad(at.ERR_CALLBACK_HOST_NOT_ALLOWED,
                       "回调主机不在白名单内")
        tok.callback_url = body.url
        if not tok.callback_secret:
            new_secret = at.generate_callback_secret()
            tok.callback_secret = at.encrypt_secret(new_secret)
    else:
        tok.callback_url = None      # 清空地址保留密钥
    await db.commit()
    await audit_svc.record(
        db, actor_id=user.id, actor_name=user.display_name or user.username,
        action="token.callback.write", resource_type="access_token",
        resource_id=str(tok.id), resource_name=tok.name,
        detail={"from": old_url, "to": tok.callback_url,
                "secret_generated": bool(new_secret)})
    return {"id": tok.id, "callbackUrl": tok.callback_url,
            "callbackSecret": new_secret}


@router.post("/{token_id}/callback-secret/rotate")
async def rotate_callback_secret(
    token_id: int, user: CurrentUser, db: DbSession,
) -> dict:
    """轮换签名密钥:新明文一次性返回;在途投递行按新密钥签发。"""
    tok = await _get_token(db, token_id)
    _require_manage(user, tok)
    try:
        at.ensure_active_for_write(tok)
    except at.TokenAuthError as e:
        raise _bad(e.code, e.message, e.status_code)
    new_secret = at.generate_callback_secret()
    tok.callback_secret = at.encrypt_secret(new_secret)
    await db.commit()
    await audit_svc.record(
        db, actor_id=user.id, actor_name=user.display_name or user.username,
        action="token.callback_secret.rotate", resource_type="access_token",
        resource_id=str(tok.id), resource_name=tok.name, detail={})
    return {"id": tok.id, "callbackSecret": new_secret}


class InvalidateIn(BaseModel):
    note: str | None = Field(default=None, max_length=500)


@router.post("/{token_id}/invalidate")
async def invalidate_token(
    token_id: int, body: InvalidateIn, user: CurrentUser, db: DbSession,
) -> dict:
    """admin 强制失效(D33):原因 ``admin``,处置说明随通知下发;
    属主重新生成后任务自动恢复。"""
    tok = await _get_token(db, token_id)
    if not has_capability(user, "users.manage"):
        raise _bad("token_not_found", f"令牌不存在: {tok.id}", 404)
    if tok.revoked_at is not None:
        # 已吊销 = 终态只读,写操作 409(§3.4);改密/停用链的已失效
        # 再失效保持幂等(§3.4 invalidate 前置「有效/已到期」)
        raise _bad(at.ERR_TOKEN_REVOKED,
                   "令牌已吊销(终态,只读;吊销后强制失效无意义)", 409)
    if tok.invalidated_at is not None:
        return {"id": tok.id, "status": tok.status}   # 幂等
    now = at.now_utc()
    tok.invalidated_at = now
    tok.invalidated_reason = at.REASON_ADMIN
    tok.invalidation_note = (body.note or "")[:500] or None
    # 注册方实例按 §3.4 → token_invalidated 暂停 + 通知(处置说明随通知)
    await at.pause_token_instances(
        db, tok, at.PAUSE_TOKEN_INVALIDATED,
        "管理员已强制失效该令牌"
        + (f":{tok.invalidation_note}" if tok.invalidation_note else "")
        + ";重新生成后任务自动恢复")
    await db.commit()
    await audit_svc.record(
        db, actor_id=user.id, actor_name=user.display_name or user.username,
        action="token.invalidate", resource_type="access_token",
        resource_id=str(tok.id), resource_name=tok.name,
        detail={"reason": at.REASON_ADMIN, "note": body.note})
    return {"id": tok.id, "status": tok.status}


@router.delete("/{token_id}")
async def revoke_token(token_id: int, user: CurrentUser, db: DbSession) -> dict:
    """吊销(软删,终态):响应带 ``pendingTasks``;再吊销幂等 200。
    user 角色可吊销自己的令牌(§2.3)。"""
    tok = await _get_token(db, token_id)
    _require_manage(user, tok)
    if tok.revoked_at is not None:
        return {"id": tok.id, "revoked": True, "pendingTasks": []}
    tok.revoked_at = at.now_utc()
    # 注册方实例暂停(token_revoked;由 JWT 管理者解绑后接管)
    pending = await at.pause_token_instances(
        db, tok, at.PAUSE_TOKEN_REVOKED,
        "令牌已吊销:经它注册的任务暂停;请在集成详情「解绑令牌」后"
        "由你接管;如只是轮换请用「重新生成」")
    await db.commit()
    await audit_svc.record(
        db, actor_id=user.id, actor_name=user.display_name or user.username,
        action="token.revoke", resource_type="access_token",
        resource_id=str(tok.id), resource_name=tok.name,
        detail={"kind": tok.kind, "pending_tasks": len(pending)})
    from ..services.webhook_outbox import wake
    wake()
    return {"id": tok.id, "revoked": True,
            "pendingTasks": [{"id": t["id"], "name": t["name"]}
                             for t in pending]}


# ── 令牌 → 任务的暂停 / 恢复联动(§3.4):实现在服务层 ──────────
# at.pause_token_instances / at.revive_token_tasks —— 改密、停用、admin
# 强制失效、吊销四处入口共用同一联动,不在路由层各写一份。
