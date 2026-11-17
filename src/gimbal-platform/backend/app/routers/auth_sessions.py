"""Auth API(重构 2026-11-16 账户实体化 §1.4;Spec-2 §4.4 D 沿革)。

Endpoints:
- GET    /api/auths                     list owner's accounts
- POST   /api/auths                     create((pool,system,env,username) 唯一)
- GET    /api/auths/{id}                detail(include_secrets 携明文)
- PATCH  /api/auths/{id}                update(password/token_type/…;一处改密处处生效)
- DELETE /api/auths/{id}                delete(ref 条目被本人场景引用则 409)
- GET    /api/auths/{id}/references     引用反查(ref 条目 + 场景引用)
- POST   /api/auths/{id}/test           拨测 = 实例 login_url + 账户凭据

账户 = 登录信息实体:密码只存一份,身份条目按 ref 引用;登录口在
system_env_instances(实例缺席 → 拨测明确报,不回退)。username 明文
(进唯一键),password Fernet 密文。所有端点 owner-scoped —— 用户
永远看不到他人的账户,即使知道整型 id。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, Query, status
from loguru import logger
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..core.security import fernet_decrypt, fernet_encrypt
from ..models import AuthAccount, SystemEnvInstance
from ..schemas.auth_session import (
    AuthAccountCreateIn,
    AuthAccountOut,
    AuthAccountPatchIn,
    AuthAccountSecretsOut,
    AuthListOut,
    AuthReferencesOut,
    TestResult,
)
from ..services import auth_probe, auth_references, query_view_runner

router = APIRouter(prefix="/auths", tags=["auths"])


DbSession = Annotated[AsyncSession, Depends(get_db)]


def _safe_decrypt(encrypted: str) -> str:
    """Decrypt, degrading gracefully after a FERNET_KEY rotation.

    Rows encrypted under a previous (ephemeral) key become
    undecryptable; blowing up with ValueError → HTTP 500 on every
    GET would take the whole auth list down.  Masked placeholder
    instead — the row is still visible/editable so the user can
    re-enter the credential.
    """
    try:
        return fernet_decrypt(encrypted)
    except ValueError:
        return "<无法解密：密钥已轮换，请重新编辑保存>"


def _to_out(a: AuthAccount, *, login_url: str = "",
            identity_count: int = 0, scenario_count: int = 0) -> AuthAccountOut:
    """username 明文(账户实体键);password 恒掩码。"""
    return AuthAccountOut(
        id=a.id,
        username=a.username,
        system=a.system,
        env_id=a.env_id,
        token_type=a.token_type,
        expires_in=a.expires_in,
        is_default=a.is_default,
        account_fields=a.account_fields or {},
        login_url=login_url,
        identity_ref_count=identity_count,
        scenario_ref_count=scenario_count,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


async def _login_urls_of(
    session: AsyncSession, accounts: list[AuthAccount],
) -> dict[int, str]:
    """账户行回显实例登录口((system, env) → login_url;缺席 = '')。"""
    pairs = {(a.system, a.env_id) for a in accounts}
    if not pairs:
        return {}
    rows = (await session.execute(
        select(SystemEnvInstance.system, SystemEnvInstance.env_id,
               SystemEnvInstance.login_url))).all()
    by_pair = {(s, e): u for s, e, u in rows}
    return {a.id: by_pair.get((a.system, a.env_id), "") for a in accounts}


async def _get_owned(
    session: AsyncSession, auth_id: int, owner_id: int,
) -> AuthAccount:
    a = await session.get(AuthAccount, auth_id)
    if a is None or a.owner_id != owner_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"auth not found: {auth_id}"
        )
    return a


async def _revive(user_id: int) -> None:
    """G7/Y2:新建/更新账户 = 补齐信号 → auth_failed/缺失凭证暂停的
    集成实例恢复(失败不阻断)。"""
    try:
        from ..services import integration_runner as _ir
        await _ir.revive_paused_instances(user_id)
    except Exception:  # noqa: BLE001
        pass


def _drop_credential_cache(user_id: int, account: AuthAccount,
                           identities: list) -> None:
    """§7.5:重存 = 认证页「手动刷新」→ 清 runner 缓存会话与 401 拉黑
    (键 = 引用条目名 —— 查询视图的凭证解析按条目)。"""
    for ident in identities:
        query_view_runner.drop_credential(user_id, ident.alias_name)


# ── list ────────────────────────────────────────────────────────
@router.get("", response_model=AuthListOut)
async def list_auths(
    user: CurrentUser, session: DbSession,
    q: Annotated[str | None, Query(max_length=128)] = None,
    token_type: Annotated[str | None, Query(max_length=32)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AuthListOut:
    """Page 信封 + 服务端过滤(M4,§6.3):``q``(username/system 子串;
    username 账户化后为明文,可检索)、``token_type`` 精确。双计数 =
    ref 条目数 + 条目聚合场景数(auth_references.account_ref_counts)。
    """
    base = select(AuthAccount).where(AuthAccount.owner_id == user.id)
    if q:
        base = base.where(or_(
            AuthAccount.username.ilike(f"%{q}%"),
            AuthAccount.system.ilike(f"%{q}%"),
        ))
    if token_type:
        base = base.where(AuthAccount.token_type == token_type)
    total = (await session.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar_one()
    tt_counts = dict((await session.execute(
        select(AuthAccount.token_type, func.count())
        .where(AuthAccount.owner_id == user.id)
        .group_by(AuthAccount.token_type)
    )).all())
    rows = (
        (
            await session.execute(
                base.order_by(AuthAccount.system.asc(), AuthAccount.username.asc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    counts = await auth_references.account_ref_counts(session, list(rows))
    urls = await _login_urls_of(session, list(rows))
    items = [
        _to_out(a, login_url=urls.get(a.id, ""),
                identity_count=counts.get(a.id, {}).get("identity_count", 0),
                scenario_count=counts.get(a.id, {}).get("scenario_count", 0))
        for a in rows
    ]
    return AuthListOut(
        items=items, total=total, page=page, page_size=page_size,
        token_type_counts=tt_counts,
    )


# ── create ──────────────────────────────────────────────────────
@router.post("", response_model=AuthAccountOut, status_code=status.HTTP_201_CREATED)
async def create_auth(
    payload: AuthAccountCreateIn,
    user: CurrentUser,
    session: DbSession,
) -> AuthAccountOut:
    from ..models.environment import Environment
    if await session.get(Environment, payload.env_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "environment_not_found",
                    "message": f"environment not found: {payload.env_id}"})
    # 账户实体键四元组唯一(DB NULLS NOT DISTINCT 兜并发)
    a = AuthAccount(
        owner_id=user.id,
        system=payload.system,
        env_id=payload.env_id,
        username=payload.username,
        password_enc=fernet_encrypt(payload.password),
        token_type=payload.token_type,
        expires_in=payload.expires_in,
        account_fields=payload.account_fields,
        # 未显式置默认时:该 system 首个账户即默认(§8.3 按 system;
        # 部分唯一索引钉死)
        is_default=payload.is_default or (await session.execute(
            select(AuthAccount.id).where(
                AuthAccount.owner_id == user.id,
                AuthAccount.system == payload.system,
                AuthAccount.is_default.is_(True)))).scalar_one_or_none() is None,
    )
    session.add(a)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"account '{payload.username}' already exists for "
                   f"system '{payload.system}' in this environment",
        )
    await session.refresh(a)
    await _revive(user.id)
    return _to_out(a)


@router.post("/{auth_id}/default", response_model=AuthAccountOut)
async def set_default_account(
    auth_id: Annotated[int, PathParam(ge=1)],
    user: CurrentUser,
    session: DbSession,
) -> AuthAccountOut:
    """置为该 system 的默认账户(§8.3:ref_mode=default 条目的取用行,
    system 唯一);同 system 旧默认原子清除。"""
    a = await _get_owned(session, auth_id, user.id)
    await session.execute(
        update(AuthAccount).where(
            AuthAccount.owner_id == user.id,
            AuthAccount.system == a.system,
            AuthAccount.id != a.id,
            AuthAccount.is_default.is_(True),
        ).values(is_default=False))
    a.is_default = True
    await session.commit()
    await session.refresh(a)
    return _to_out(a)


# ── detail ─────────────────────────────────────────────────────
@router.get("/{auth_id}", response_model=AuthAccountSecretsOut | AuthAccountOut)
async def get_auth(
    auth_id: Annotated[int, PathParam(ge=1)],
    user: CurrentUser,
    session: DbSession,
    include_secrets: bool = False,
) -> AuthAccountOut | AuthAccountSecretsOut:
    a = await _get_owned(session, auth_id, user.id)
    urls = await _login_urls_of(session, [a])
    base = _to_out(a, login_url=urls.get(a.id, ""))
    if not include_secrets:
        return base
    # 严解密:密钥轮换后的旧密文不可恢复。快照拷贝会把返回值当真值写进
    # 场景导出产物,不能像列表 _safe_decrypt 那样降级为占位符 — 显式 422。
    try:
        password = fernet_decrypt(a.password_enc)
    except ValueError as e:
        logger.warning("auth.get include_secrets: fernet decrypt failed: {}", e)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="加密凭据已损坏或密钥已轮换，请先在认证管理重新编辑保存",
        )
    return AuthAccountSecretsOut(
        **base.model_dump(by_alias=True, exclude={"password_masked"}),
        password=password)


# ── patch ──────────────────────────────────────────────────────
@router.patch("/{auth_id}", response_model=AuthAccountOut)
async def patch_auth(
    auth_id: Annotated[int, PathParam(ge=1)],
    payload: AuthAccountPatchIn,
    user: CurrentUser,
    session: DbSession,
) -> AuthAccountOut:
    a = await _get_owned(session, auth_id, user.id)
    old = (a.system, a.env_id, a.is_default)
    if "system" in payload.model_fields_set:
        a.system = payload.system
    if "env_id" in payload.model_fields_set:
        if payload.env_id is not None:
            from ..models.environment import Environment
            if await session.get(Environment, payload.env_id) is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"code": "environment_not_found",
                            "message": f"environment not found: "
                                       f"{payload.env_id}"})
        a.env_id = payload.env_id  # type: ignore[assignment]
    if payload.account_fields is not None:
        a.account_fields = payload.account_fields
    if payload.is_default:
        await session.execute(
            update(AuthAccount).where(
                AuthAccount.owner_id == user.id,
                AuthAccount.system == a.system,
                AuthAccount.id != a.id,
                AuthAccount.is_default.is_(True),
            ).values(is_default=False))
        a.is_default = True
    if payload.password is not None:
        # 一处改密处处生效(决策 5):ref 该账户的全部条目下次执行生效
        a.password_enc = fernet_encrypt(payload.password)
    if payload.token_type is not None:
        a.token_type = payload.token_type
    if payload.expires_in is not None:
        a.expires_in = payload.expires_in
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="更新冲突:同系统同环境已存在同名账户",
        )
    await session.refresh(a)
    _drop_credential_cache(
        user.id, a,
        await auth_references.identities_for_account(session, a))
    await _revive(user.id)
    _ = old
    return _to_out(a)


# ── references / delete ────────────────────────────────────────
@router.get("/{auth_id}/references", response_model=AuthReferencesOut)
async def get_references(
    auth_id: Annotated[int, PathParam(ge=1)],
    user: CurrentUser,
    session: DbSession,
) -> AuthReferencesOut:
    """反查面板:谁在用这个账户(ref 条目清单 + 条目名聚合的场景引用)。
    读时实时扫(单一事实源,不建反向索引);场景名按 can_read_scenario
    过滤,剩余 = hidden_count。"""
    a = await _get_owned(session, auth_id, user.id)
    return AuthReferencesOut.model_validate(
        await auth_references.references(session, user=user, account=a))


@router.delete("/{auth_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_auth(
    auth_id: Annotated[int, PathParam(ge=1)],
    user: CurrentUser,
    session: DbSession,
) -> None:
    a = await _get_owned(session, auth_id, user.id)
    # 删除拦截(窄口径):ref 该账户的条目被本人场景模板引用 — 下次运行
    # 会真失效;快照与他人场景不阻断(名字引用,别人解析各自的账户)。
    blocking = await auth_references.blocking_refs(session, user=user, account=a)
    if blocking:
        idents = await auth_references.identities_for_account(session, a)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": (
                    f"账户 {a.username!r} 被身份条目 "
                    f"({'、'.join(i.alias_name for i in idents) or '—'}) "
                    f"引用,而条目又被 {len(blocking)} 个本人场景引用"
                    "(模板),删除会让这些场景下次运行失效;"
                    "请先在场景中移除引用后再删除"
                ),
                "ownScenarioIds": blocking,
            },
        )
    idents = await auth_references.identities_for_account(session, a)
    await session.delete(a)
    await session.commit()
    _drop_credential_cache(user.id, a, idents)


# ── test ───────────────────────────────────────────────────────
@router.post("/{auth_id}/test", response_model=TestResult)
async def test_auth(
    auth_id: Annotated[int, PathParam(ge=1)],
    user: CurrentUser,
    session: DbSession,
) -> TestResult:
    """拨测 = 实例登录口(system_env_instances.login_url)+ 账户凭据
    (重构 §4.3:登录口缺席 = 配置缺失,明确报,不回退业务地址)。"""
    a = await _get_owned(session, auth_id, user.id)
    login_url = (await session.execute(
        select(SystemEnvInstance.login_url).where(
            SystemEnvInstance.system == a.system,
            SystemEnvInstance.env_id == a.env_id))).scalar()
    if not login_url:
        return TestResult(
            ok=False, message="实例未配置登录口 —— 请在环境配置页为"
            f"「{a.system} × 环境#{a.env_id}」维护登录地址后再拨测")
    try:
        password = fernet_decrypt(a.password_enc)
    except ValueError as e:
        logger.warning("auth.test: fernet decrypt failed: {}", e)
        return TestResult(ok=False, message="加密凭据已损坏，请重新录入")

    ok, status_code, message = await auth_probe.probe(
        login_url, a.username, password)
    return TestResult(ok=ok, status_code=status_code, message=message)
