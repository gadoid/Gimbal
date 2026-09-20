"""Auth-sessions API (Spec-2 §4.4 D).

Endpoints:
- GET    /api/auths                 list owner's credentials
- POST   /api/auths                 create
- GET    /api/auths/{id}            detail
- PATCH  /api/auths/{id}            update (url/username/password/token_type/expires_in)
- DELETE /api/auths/{id}            delete
- POST   /api/auths/{id}/test       hit alias.url with username+password; parse token

(fetch-token 端点已随 V1 executor 退役移除 —— 凭证解密注入由
run_dispatcher 服务端完成,不再对外下发明文凭证。)

All endpoints are owner-scoped — a user can never see another user's
auth-sessions, even if they know the integer id.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..core.security import fernet_decrypt, fernet_encrypt
from ..models import AuthSession
from ..schemas.auth_session import (
    AuthReferencesOut,
    AuthSessionCreateIn,
    AuthSessionOut,
    AuthSessionPatchIn,
    AuthSessionSecretsOut,
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


def _to_out(a: AuthSession) -> AuthSessionOut:
    """Decrypt username for the response (password stays masked)."""
    return AuthSessionOut(
        id=a.id,
        alias=a.alias,
        url=a.url,
        username=_safe_decrypt(a.username_enc),
        token_type=a.token_type,
        expires_in=a.expires_in,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


async def _get_owned(session: AsyncSession, auth_id: int, owner_id: int) -> AuthSession:
    a = await session.get(AuthSession, auth_id)
    if a is None or a.owner_id != owner_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"auth not found: {auth_id}"
        )
    return a


# ── list ────────────────────────────────────────────────────────
@router.get("", response_model=list[AuthSessionOut])
async def list_auths(
    user: CurrentUser, session: DbSession
) -> list[AuthSessionOut]:
    """双计数一次扫描服务全部行(配套方案 §1.2):
    alias_ref_count = service_aliases 绑定数;scenario_ref_count =
    模板 ∪ 方案绑定去重场景数(快照不进计数 — 面板里按 kind 展示)。"""
    rows = (
        (
            await session.execute(
                select(AuthSession)
                .where(AuthSession.owner_id == user.id)
                .order_by(AuthSession.alias.asc())
            )
        )
        .scalars()
        .all()
    )
    counts = await auth_references.counts(session)
    return [
        AuthSessionOut(
            id=a.id,
            alias=a.alias,
            url=a.url,
            username=_safe_decrypt(a.username_enc),
            token_type=a.token_type,
            expires_in=a.expires_in,
            created_at=a.created_at,
            updated_at=a.updated_at,
            alias_ref_count=counts.get(a.alias, {}).get("alias_count", 0),
            scenario_ref_count=counts.get(a.alias, {}).get("scenario_count", 0),
        )
        for a in rows
    ]


# ── create ──────────────────────────────────────────────────────
@router.post("", response_model=AuthSessionOut, status_code=status.HTTP_201_CREATED)
async def create_auth(
    payload: AuthSessionCreateIn,
    user: CurrentUser,
    session: DbSession,
) -> AuthSessionOut:
    a = AuthSession(
        owner_id=user.id,
        alias=payload.alias,
        url=payload.url,
        username_enc=fernet_encrypt(payload.username),
        password_enc=fernet_encrypt(payload.password),
        token_type=payload.token_type,
        expires_in=payload.expires_in,
    )
    session.add(a)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"alias '{payload.alias}' already exists for this user",
        )
    await session.refresh(a)
    return _to_out(a)


# ── detail ─────────────────────────────────────────────────────
@router.get("/{auth_id}", response_model=AuthSessionSecretsOut | AuthSessionOut)
async def get_auth(
    auth_id: Annotated[int, PathParam(ge=1)],
    user: CurrentUser,
    session: DbSession,
    include_secrets: bool = False,
) -> AuthSessionOut | AuthSessionSecretsOut:
    a = await _get_owned(session, auth_id, user.id)
    if not include_secrets:
        return _to_out(a)
    # 严解密:密钥轮换后的旧密文不可恢复。快照拷贝会把返回值当真值写进
    # 场景导出产物,不能像列表 _safe_decrypt 那样降级为占位符 — 显式 422。
    try:
        username = fernet_decrypt(a.username_enc)
        password = fernet_decrypt(a.password_enc)
    except ValueError as e:
        logger.warning("auth.get include_secrets: fernet decrypt failed: {}", e)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="加密凭据已损坏或密钥已轮换，请先在认证管理重新编辑保存",
        )
    return AuthSessionSecretsOut(
        id=a.id,
        alias=a.alias,
        url=a.url,
        username=username,
        password=password,
        token_type=a.token_type,
        expires_in=a.expires_in,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


# ── patch ──────────────────────────────────────────────────────
@router.patch("/{auth_id}", response_model=AuthSessionOut)
async def patch_auth(
    auth_id: Annotated[int, PathParam(ge=1)],
    payload: AuthSessionPatchIn,
    user: CurrentUser,
    session: DbSession,
) -> AuthSessionOut:
    a = await _get_owned(session, auth_id, user.id)
    if payload.url is not None:
        a.url = payload.url
    if payload.username is not None:
        a.username_enc = fernet_encrypt(payload.username)
    if payload.password is not None:
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
            status_code=status.HTTP_409_CONFLICT, detail="更新冲突"
        )
    await session.refresh(a)
    # 查询凭证复活钩子(§7.5):重存 = 认证页"手动刷新"动作 → 清 runner
    # 缓存会话与 401 拉黑,下次查询重装凭证冷启登录(§6.2 不自动重登不变)
    query_view_runner.drop_credential(user.id, a.alias)
    return _to_out(a)


# ── delete ─────────────────────────────────────────────────────
@router.get("/{alias}/references", response_model=AuthReferencesOut)
async def get_references(
    alias: Annotated[str, PathParam(min_length=1, max_length=64)],
    user: CurrentUser,
    session: DbSession,
) -> AuthReferencesOut:
    """反查面板:谁在用这个凭证名(配套方案 §1.3)。四类引用,读时实时
    扫(单一事实源,不建反向索引);计数照给、场景名按 can_read_scenario
    过滤(admin 全量 / public / owner),剩余 = hidden_count(§1.4)。
    名字命中 ≠ 对象引用 — 引用解析按执行者本人池,文案须如实。"""
    return AuthReferencesOut.model_validate(
        await auth_references.references(session, user=user, alias=alias))


@router.delete("/{auth_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_auth(
    auth_id: Annotated[int, PathParam(ge=1)],
    user: CurrentUser,
    session: DbSession,
) -> None:
    a = await _get_owned(session, auth_id, user.id)
    # 删除拦截(窄口径,方案 §1.4.3/§1.5 拍板):仅本人场景的模板/方案
    # 绑定引用硬拦 — 这些下次运行会真失效;别名绑定、同名他场景、
    # config.users 快照不阻断(名字引用,别人解析各自的同名凭证)。
    blocking = await auth_references.blocking_refs(
        session, user=user, alias=a.alias)
    if blocking:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": (
                    f"凭证 {a.alias!r} 被 {len(blocking)} 个本人场景引用"
                    "(模板/方案绑定),删除会让这些场景下次运行失效;"
                    "请先在场景中移除引用后再删除"
                ),
                "ownScenarioIds": blocking,
            },
        )
    await session.delete(a)
    await session.commit()
    query_view_runner.drop_credential(user.id, a.alias)


# ── test ───────────────────────────────────────────────────────
@router.post("/{auth_id}/test", response_model=TestResult)
async def test_auth(
    auth_id: Annotated[int, PathParam(ge=1)],
    user: CurrentUser,
    session: DbSession,
) -> TestResult:
    """Dial the stored credential against ``url`` (probe service)."""
    a = await _get_owned(session, auth_id, user.id)
    try:
        username = fernet_decrypt(a.username_enc)
        password = fernet_decrypt(a.password_enc)
    except ValueError as e:
        logger.warning("auth.test: fernet decrypt failed: {}", e)
        return TestResult(ok=False, message="加密凭据已损坏，请重新录入")

    ok, status_code, message = await auth_probe.probe(a.url, username, password)
    return TestResult(ok=ok, status_code=status_code, message=message)