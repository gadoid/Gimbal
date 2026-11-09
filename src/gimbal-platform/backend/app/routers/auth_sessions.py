"""Auth-sessions API (Spec-2 §4.4 D).

Endpoints:
- GET    /api/auths                 list owner's credentials
- POST   /api/auths                 create
- GET    /api/auths/{id}            detail
- PATCH  /api/auths/{id}            update (url/username/password/token_type/expires_in/system/env/accountFields/isDefault)
- DELETE /api/auths/{id}            delete
- POST   /api/auths/{id}/test       hit alias.url with username+password; parse token

(fetch-token 端点已随 V1 executor 退役移除 —— 凭证解密注入由
run_dispatcher 服务端完成,不再对外下发明文凭证。)

All endpoints are owner-scoped — a user can never see another user's
auth-sessions, even if they know the integer id.
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
from ..models import AuthSession
from ..schemas.auth_session import (
    AuthListOut,
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
        system=a.system,
        envId=a.env_id,
        slot=a.slot,
        isDefault=a.is_default,
        accountFields=a.account_fields or {},
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
@router.get("", response_model=AuthListOut)
async def list_auths(
    user: CurrentUser, session: DbSession,
    q: Annotated[str | None, Query(max_length=128)] = None,
    token_type: Annotated[str | None, Query(max_length=32)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AuthListOut:
    """Page 信封 + 服务端过滤(M4,§6.3):``q``(alias/url 子串;
    username 是 Fernet 密文,服务端不可检索 —— 如实收缩,不含 username)、
    ``token_type`` 精确。双计数一次扫描服务全部行(配套方案 §1.2):
    alias_ref_count = service_aliases 绑定数;scenario_ref_count =
    模板 ∪ 方案绑定去重场景数(快照不进计数 — 面板里按 kind 展示)。

    ``tokenTypeCounts`` 是**全量过滤集**(非当前页)的类型计数 —— 服务端
    分页后前端拿不到全集,metaText「N Bearer · N 整段头」改由这里供给。
    """
    base = select(AuthSession).where(AuthSession.owner_id == user.id)
    if q:
        base = base.where(or_(
            AuthSession.alias.ilike(f"%{q}%"),
            AuthSession.url.ilike(f"%{q}%"),
        ))
    if token_type:
        base = base.where(AuthSession.token_type == token_type)
    total = (await session.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar_one()
    tt_counts = dict((await session.execute(
        select(AuthSession.token_type, func.count())
        .where(AuthSession.owner_id == user.id)
        .group_by(AuthSession.token_type)
    )).all())
    rows = (
        (
            await session.execute(
                base.order_by(AuthSession.alias.asc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    counts = await auth_references.counts(session)
    items = [
        _to_out(a).model_copy(update={
            "alias_ref_count": counts.get(a.alias, {}).get("alias_count", 0),
            "scenario_ref_count": counts.get(a.alias, {}).get("scenario_count", 0),
        })
        for a in rows
    ]
    return AuthListOut(
        items=items, total=total, page=page, page_size=page_size,
        token_type_counts=tt_counts,
    )


# ── create ──────────────────────────────────────────────────────
@router.post("", response_model=AuthSessionOut, status_code=status.HTTP_201_CREATED)
async def create_auth(
    payload: AuthSessionCreateIn,
    user: CurrentUser,
    session: DbSession,
) -> AuthSessionOut:
    slot = payload.slot or payload.alias
    # 应用层 (owner, alias) 名字唯一:引用面板/query_view 缓存/
    # drop_credential 都按名工作,名字必须无歧义(DB 权威键是四元组)
    dup = (await session.execute(select(AuthSession.id).where(
        AuthSession.owner_id == user.id,
        AuthSession.alias == payload.alias))).scalar_one_or_none()
    if dup is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"alias '{payload.alias}' already exists for this user")
    if payload.env_id is not None:
        from ..models.environment import Environment
        if await session.get(Environment, payload.env_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "environment_not_found",
                        "message": f"environment not found: "
                                   f"{payload.env_id}"})
    # 首个绑定即该槽默认(部分唯一索引钉死每槽至多一个默认)
    has_default = (await session.execute(select(AuthSession.id).where(
        AuthSession.owner_id == user.id,
        AuthSession.slot == slot,
        AuthSession.is_default.is_(True)))).scalar_one_or_none()
    a = AuthSession(
        owner_id=user.id,
        alias=payload.alias,
        url=payload.url,
        username_enc=fernet_encrypt(payload.username),
        password_enc=fernet_encrypt(payload.password),
        token_type=payload.token_type,
        expires_in=payload.expires_in,
        # S3 槽位绑定:槽名缺省 = 别名;env 不限;system 未认领 = ''
        system=payload.system,
        env_id=payload.env_id,
        slot=slot,
        account_fields=payload.account_fields,
        is_default=has_default is None,
    )
    session.add(a)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"slot '{slot}' already bound for this system/env",
        )
    await session.refresh(a)
    # G7/Y2:新建凭证 = 补齐信号 → auth_failed/缺失凭证暂停的集成实例
    # 恢复(与 update 同钩;失败不阻断)。
    try:
        from ..services import integration_runner as _ir
        await _ir.revive_paused_instances(user.id)
    except Exception:  # noqa: BLE001
        pass
    return _to_out(a)


@router.post("/{auth_id}/default", response_model=AuthSessionOut)
async def set_default_binding(
    auth_id: Annotated[int, PathParam(ge=1)],
    user: CurrentUser,
    session: DbSession,
) -> AuthSessionOut:
    """置为该槽的默认绑定(S3):名字解析与环境未命中时的取用行;
    同槽旧默认原子清除。"""
    a = await _get_owned(session, auth_id, user.id)
    await session.execute(
        update(AuthSession).where(
            AuthSession.owner_id == user.id,
            AuthSession.slot == a.slot,
            AuthSession.id != a.id,
            AuthSession.is_default.is_(True),
        ).values(is_default=False))
    a.is_default = True
    await session.commit()
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
    # S3 槽位绑定:system/env/account_fields(env 显式 null = 清空,
    # 与项目默认环境同款 fields_set 口径);is_default=true = 换默认
    if "system" in payload.model_fields_set:
        a.system = payload.system or ""
    if "env_id" in payload.model_fields_set:
        if payload.env_id is not None:
            from ..models.environment import Environment
            if await session.get(Environment, payload.env_id) is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"code": "environment_not_found",
                            "message": f"environment not found: "
                                       f"{payload.env_id}"})
        a.env_id = payload.env_id
    if payload.account_fields is not None:
        a.account_fields = payload.account_fields
    if payload.is_default:
        # 置默认:同槽清旧默认(原子切换;部分唯一索引兜并发)
        await session.execute(
            update(AuthSession).where(
                AuthSession.owner_id == user.id,
                AuthSession.slot == a.slot,
                AuthSession.id != a.id,
                AuthSession.is_default.is_(True),
            ).values(is_default=False))
        a.is_default = True
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
    # G7/Y2 集成实例复活:凭证更新 → auth_failed 暂停的实例恢复调度
    # (个人模式匹配持有人;平台模式由 operator/admin 改平台凭证触发)。
    # 失败不阻断凭证更新(复活是增强,下拍调度前还有别的人口)。
    try:
        from ..services import integration_runner as _ir
        await _ir.revive_paused_instances(user.id)
    except Exception:  # noqa: BLE001
        pass
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
    过滤(public / owner / 引用;authz W3 起 admin 无旁路),剩余 = hidden_count(§1.4)。
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
    if not a.url:
        # authz C2:静态令牌方式无登录端点,不探测(令牌直接施加)
        return TestResult(ok=True, message="静态令牌认证:无登录流程,不做拨测")
    try:
        username = fernet_decrypt(a.username_enc)
        password = fernet_decrypt(a.password_enc)
    except ValueError as e:
        logger.warning("auth.test: fernet decrypt failed: {}", e)
        return TestResult(ok=False, message="加密凭据已损坏，请重新录入")

    ok, status_code, message = await auth_probe.probe(a.url, username, password)
    return TestResult(ok=ok, status_code=status_code, message=message)