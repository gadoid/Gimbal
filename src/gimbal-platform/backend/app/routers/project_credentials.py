"""项目凭证 API(authz M2a S8;重构 2026-11-16 项目账户池对称化 §1.4)。

项目凭证 = 归属项目的登录账户(``auth_accounts.project_id``;owner_id
NULL)。修订总原则 1:唯一的共享账户;只有项目管理员能录入 / 修改,
成员只能选用。可见性双口径:**本管理面列表**
仍掩码(``_member_view``:成员视图 ``username=''``,密码恒掩码);
**检索面**(``GET /auth?source=project``)username 对成员明文 —— 按名
引用必需,掩码在此面不适用。

Endpoints(前缀 ``/projects/{project_id}/credentials``):

- GET                 列表 —— 项目成员(非成员 404,Admin+ 不旁路)
- POST                新建 —— 项目管理员(``_manage_gate``);(system,
                      env, username) 唯一;密码 ≥6 位(r6 掩码阈值)
- PATCH  /{cid}       修改 —— 同上;一处改密处处生效(条目 ref 共享)
- POST   /{cid}/default  同 system 原子换默认(0059 起默认按
  (池, system) 唯一,清旧默认不看 env)—— 同上
- DELETE /{cid}       删除 —— 同上(依赖它的项目源实例下次执行暂停)
- POST   /{cid}/test  拨测 —— 实例 login_url + 账户凭据(§4.3)

公共项目:409 ``public_project_no_credentials``。明文唯一出口 = 拨测。
登录地址(url)已上提实例(system_env_instances.login_url)—— 账户
表单不再收,「改址须重录密码」防护随口径迁移至实例面(服务注册页
由 ops.write 治理)。写面审计 ``project.credential.write``;写后复活
该项目凭证源暂停的集成实例。
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, status
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..core.security import fernet_decrypt, fernet_encrypt
from ..models import AuthAccount, Project, SystemEnvInstance
from ..models.environment import Environment
# r6 小项闸已上提单源(TOK-08a:个人池对齐同款),本地名保留免改调用点
from ._password_gate import require_maskable_password as _require_maskable_password
from ..schemas.auth_session import (
    AuthAccountCreateIn,
    AuthAccountOut,
    AuthAccountPatchIn,
    TestResult,
)
from ..services import auth_probe
from ..services.account_integrity import account_integrity_conflict
from .auth_sessions import _login_urls_of, _to_out
from .projects import _audit, _my_role

router = APIRouter(prefix="/projects/{project_id}/credentials",
                   tags=["project-credentials"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


class ProjectCredentialListOut(BaseModel):
    items: list[AuthAccountOut] = Field(default_factory=list)
    # 请求者能否维护(项目管理员 ∨ Admin+)—— 前端据此显隐写面
    canManage: bool = False


def _not_found(project_id: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "not_found",
                "message": f"project not found: {project_id}"})


async def _load_normal_project(db: AsyncSession, project_id: int) -> Project:
    proj = await db.get(Project, project_id)
    if proj is None:
        raise _not_found(project_id)
    if proj.kind == "public":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "public_project_no_credentials",
                    "message": "公共项目没有项目凭证(公共内容由订阅者用"
                               "自己的凭证执行)"})
    return proj


async def _manage_gate(db: AsyncSession, user, project_id: int) -> Project:
    # 存在性先于公共项目判定:r5-2.2 管理门 = 项目管理员,Admin+ 不旁路;
    # 非成员 404,成员非管理员 403
    proj = await _load_normal_project(db, project_id)
    my_role = await _my_role(db, user, proj.id)
    if my_role == "admin":
        return proj
    if my_role is None:
        raise _not_found(project_id)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "not_project_admin",
                "message": "只有项目管理员能维护项目凭证"})


# r6 小项闸已上提单源(_password_gate;本地名经由顶部 import 保留)


async def _get_cred(db: AsyncSession, project_id: int, cid: int) -> AuthAccount:
    a = await db.get(AuthAccount, cid)
    if a is None or a.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found",
                    "message": f"credential not found: {cid}"})
    return a


async def _after_write(db: AsyncSession, user, proj: Project, op: str,
                       a) -> None:
    """审计 + 复活钩子(best-effort,均不阻断写面)。"""
    await _audit(db, user, "project.credential.write", proj, {
        "op": op, "credentialId": a.id,
        "system": a.system, "username": a.username})
    if op == "delete":
        return
    try:
        from ..services import integration_runner as _ir
        await _ir.revive_paused_instances(project_id=proj.id)
    except Exception:  # noqa: BLE001 — 复活是增强
        logger.opt(exception=True).warning(
            "project credentials: revive hook failed")


def _member_view(out: AuthAccountOut) -> AuthAccountOut:
    """成员视图:不给账号(用户名);密码本就恒掩码。"""
    return out.model_copy(update={"username": ""})


# ── list ────────────────────────────────────────────────────────
@router.get("", response_model=ProjectCredentialListOut)
async def list_project_credentials(
    user: CurrentUser, db: DbSession, project_id: int,
) -> ProjectCredentialListOut:
    proj = await _load_normal_project(db, project_id)
    role = await _my_role(db, user, proj.id)
    if role is None:
        # r5-2.2:Admin+ 非成员同 404 —— 凭证是项目的,读面不因平台
        # 角色放宽(管理面已同口径收口)
        raise _not_found(project_id)
    can_manage = role == "admin"
    rows = (await db.execute(select(AuthAccount).where(
        AuthAccount.project_id == proj.id).order_by(
            AuthAccount.system, AuthAccount.id))).scalars().all()
    urls = await _login_urls_of(db, list(rows))
    items = [_to_out(a, login_url=urls.get(a.id, "")) for a in rows]
    if not can_manage:
        items = [_member_view(o) for o in items]
    return ProjectCredentialListOut(items=items, canManage=can_manage)


# ── create ──────────────────────────────────────────────────────
@router.post("", response_model=AuthAccountOut,
             status_code=status.HTTP_201_CREATED)
async def create_project_credential(
    payload: AuthAccountCreateIn, user: CurrentUser, db: DbSession,
    project_id: int,
) -> AuthAccountOut:
    proj = await _manage_gate(db, user, project_id)
    _require_maskable_password(payload.password)
    if await db.get(Environment, payload.env_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "environment_not_found",
                    "message": f"environment not found: {payload.env_id}"})
    a = AuthAccount(
        owner_id=None, project_id=proj.id,
        system=payload.system, env_id=payload.env_id,
        username=payload.username,
        password_enc=fernet_encrypt(payload.password),
        token_type=payload.token_type, expires_in=payload.expires_in,
        account_fields=payload.account_fields,
        # 未显式置默认时:该 system 首个账户即默认(§8.3 按 system)
        is_default=payload.is_default or (await db.execute(
            select(AuthAccount.id).where(
                AuthAccount.project_id == proj.id,
                AuthAccount.system == payload.system,
                AuthAccount.is_default.is_(True)))).scalar_one_or_none() is None,
    )
    db.add(a)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        # 按约束名分派(blanket 把默认位冲突误报
        # 成撞名)
        _code, _msg = account_integrity_conflict(e)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": _code,
                    "message": _msg or (
                        f"account '{payload.username}' already exists "
                        f"for system '{payload.system}' in this "
                        "environment")}) from e
    await db.refresh(a)
    await _after_write(db, user, proj, "create", a)
    return _to_out(a)


async def _set_default(db: AsyncSession, a: AuthAccount) -> None:
    await db.execute(update(AuthAccount).where(
        AuthAccount.project_id == a.project_id,
        AuthAccount.system == a.system,
        AuthAccount.id != a.id,
        AuthAccount.is_default.is_(True),
    ).values(is_default=False))
    a.is_default = True


@router.post("/{cid}/default", response_model=AuthAccountOut)
async def set_default_project_credential(
    user: CurrentUser, db: DbSession, project_id: int,
    cid: Annotated[int, PathParam(ge=1)],
) -> AuthAccountOut:
    proj = await _manage_gate(db, user, project_id)
    a = await _get_cred(db, proj.id, cid)
    await _set_default(db, a)
    await db.commit()
    await db.refresh(a)
    await _after_write(db, user, proj, "default", a)
    return _to_out(a)


# ── patch ──────────────────────────────────────────────────────
@router.patch("/{cid}", response_model=AuthAccountOut)
async def patch_project_credential(
    payload: AuthAccountPatchIn, user: CurrentUser, db: DbSession,
    project_id: int, cid: Annotated[int, PathParam(ge=1)],
) -> AuthAccountOut:
    proj = await _manage_gate(db, user, project_id)
    a = await _get_cred(db, proj.id, cid)
    _require_maskable_password(payload.password)
    if "system" in payload.model_fields_set:
        a.system = payload.system
    if "env_id" in payload.model_fields_set:
        if payload.env_id is not None and \
                await db.get(Environment, payload.env_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "environment_not_found",
                        "message": f"environment not found: {payload.env_id}"})
        a.env_id = payload.env_id  # type: ignore[assignment]
    if payload.account_fields is not None:
        a.account_fields = payload.account_fields
    if payload.is_default:
        await _set_default(db, a)
    if payload.password is not None:
        a.password_enc = fernet_encrypt(payload.password)
    if payload.token_type is not None:
        a.token_type = payload.token_type
    if payload.expires_in is not None:
        a.expires_in = payload.expires_in
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        # 按约束名分派(改默认位撞 uq_account_
        # default 不是泛化「更新冲突」)
        _code, _msg = account_integrity_conflict(e)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": _code if _msg else "update_conflict",
                    "message": _msg or "更新冲突"}) from e
    await db.refresh(a)
    await _after_write(db, user, proj, "update", a)
    return _to_out(a)


# ── delete ─────────────────────────────────────────────────────
@router.delete("/{cid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_credential(
    user: CurrentUser, db: DbSession, project_id: int,
    cid: Annotated[int, PathParam(ge=1)],
) -> None:
    proj = await _manage_gate(db, user, project_id)
    a = await _get_cred(db, proj.id, cid)
    snapshot = SimpleNamespace(
        id=a.id, system=a.system, username=a.username)
    await db.delete(a)
    await db.commit()
    await _after_write(db, user, proj, "delete", snapshot)


# ── test ───────────────────────────────────────────────────────
@router.post("/{cid}/test", response_model=TestResult)
async def test_project_credential(
    user: CurrentUser, db: DbSession, project_id: int,
    cid: Annotated[int, PathParam(ge=1)],
) -> TestResult:
    """拨测 = 实例登录口 + 项目账户凭据(§4.3:缺席明确报,不回退)。"""
    proj = await _manage_gate(db, user, project_id)
    a = await _get_cred(db, proj.id, cid)
    login_url = (await db.execute(
        select(SystemEnvInstance.login_url).where(
            SystemEnvInstance.system == a.system,
            SystemEnvInstance.env_id == a.env_id))).scalar()
    if not login_url:
        return TestResult(
            ok=False, message="实例未配置登录口 —— 请在服务注册页"
            f"「{a.system} × 环境#{a.env_id}」的实例配置中维护登录地址"
            "后再拨测")
    try:
        password = fernet_decrypt(a.password_enc)
    except ValueError as e:
        logger.warning("project credential test: decrypt failed: {}", e)
        return TestResult(ok=False, message="加密凭据已损坏，请重新录入")
    ok, status_code, message = await auth_probe.probe(
        login_url, a.username, password)
    return TestResult(ok=ok, status_code=status_code, message=message)
