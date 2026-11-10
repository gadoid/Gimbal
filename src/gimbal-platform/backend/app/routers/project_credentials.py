"""项目凭证 API(authz M2a S8,s8-detail §二 S8.1)。

项目凭证 = 归属项目的槽位绑定(``auth_sessions.project_id``;owner_id
NULL)。修订总原则 1:唯一的共享凭证;只有项目管理员能录入 / 修改,
成员只能选用、**看不到明文**。

Endpoints(前缀 ``/projects/{project_id}/credentials``):

- GET                 列表 —— 项目成员(非成员 404,Admin+ 不旁路);
                      成员视图不含用户名(``username=''``),密码恒掩码
- POST                新建 —— 项目管理员(``_manage_gate``;r5-2.2 起
                      Admin+ 不旁路,与选用门同口径:凭证是项目的,
                      不是平台的);密码 ≥6 位(r6:短密码不受引擎按值
                      掩码保护)
- PATCH  /{cid}       修改 —— 同上;改 ``url`` 须同时重录 ``password``
                      (r5-2.2:拨测把解密凭据发往该地址,单改地址 =
                      把存量密码重定向到任意收集端)
- POST   /{cid}/default  同槽原子换默认 —— 同上
- DELETE /{cid}       删除 —— 同上(依赖它的项目源实例下次执行暂停)
- POST   /{cid}/test  拨测 —— 同上

公共项目:409 ``public_project_no_credentials``(无成员,项目凭证无意义)。
无 ``include_secrets``;明文唯一出口 = 拨测(发往凭证自身登录地址,
而改地址须重录密码)。写面审计
``project.credential.write``(资源 = 项目;detail 记 op / 凭证 id / 槽名);
写后复活该项目凭证源暂停的集成实例。
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
from ..models import AuthSession
from ..models.project import Project
from ..schemas.auth_session import (
    AuthSessionCreateIn,
    AuthSessionOut,
    AuthSessionPatchIn,
    TestResult,
)
from ..services import auth_probe
from .auth_sessions import _to_out
from .projects import _audit, _my_role

router = APIRouter(prefix="/projects/{project_id}/credentials",
                   tags=["project-credentials"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


class ProjectCredentialListOut(BaseModel):
    items: list[AuthSessionOut] = Field(default_factory=list)
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
    # 存在性先于公共项目判定:非成员对公共项目同样拿 409 无泄露(公共
    # 项目全员可见)。r5-2.2:管理门 = 项目管理员,Admin+ 不旁路 ——
    # 与选用门(can_use_project_credentials)同口径,收掉「Admin+ 不能
    # 用却能改址拨测导出」的自相矛盾;非成员 404,成员非管理员 403
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


def _require_maskable_password(password: str | None) -> None:
    """r6 小项:项目凭证密码 ≥6 位 —— 引擎按值掩码的登记阈值就是 6,
    短密码在 events/rows/日志证据面不受掩码保护(共享凭证必须护住)。"""
    if password is not None and len(password) < 6:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "password_too_short_for_masking",
                    "message": "密码至少 6 位 —— 短于 6 位的凭证不受"
                               "执行记录按值掩码保护(项目成员可见)"})


async def _get_cred(db: AsyncSession, project_id: int, cid: int) -> AuthSession:
    a = await db.get(AuthSession, cid)
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
        "op": op, "credentialId": a.id, "slot": a.slot, "alias": a.alias})
    if op == "delete":
        return
    try:
        from ..services import integration_runner as _ir
        await _ir.revive_paused_instances(project_id=proj.id)
    except Exception:  # noqa: BLE001 — 复活是增强
        logger.opt(exception=True).warning(
            "project credentials: revive hook failed")


def _member_view(out: AuthSessionOut) -> AuthSessionOut:
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
    rows = (await db.execute(select(AuthSession).where(
        AuthSession.project_id == proj.id).order_by(
            AuthSession.slot, AuthSession.id))).scalars().all()
    items = [_to_out(a) for a in rows]
    if not can_manage:
        items = [_member_view(o) for o in items]
    return ProjectCredentialListOut(items=items, canManage=can_manage)


# ── create ──────────────────────────────────────────────────────
@router.post("", response_model=AuthSessionOut,
             status_code=status.HTTP_201_CREATED)
async def create_project_credential(
    payload: AuthSessionCreateIn, user: CurrentUser, db: DbSession,
    project_id: int,
) -> AuthSessionOut:
    proj = await _manage_gate(db, user, project_id)
    _require_maskable_password(payload.password)
    slot = payload.slot or payload.alias
    # 应用层 (project, alias) 名字唯一(与个人面 (owner, alias) 同口径)
    dup = (await db.execute(select(AuthSession.id).where(
        AuthSession.project_id == proj.id,
        AuthSession.alias == payload.alias))).scalar_one_or_none()
    if dup is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "alias_exists",
                    "message": f"alias '{payload.alias}' already exists "
                               "in this project"})
    if payload.env_id is not None:
        from ..models.environment import Environment
        if await db.get(Environment, payload.env_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "environment_not_found",
                        "message": f"environment not found: "
                                   f"{payload.env_id}"})
    has_default = (await db.execute(select(AuthSession.id).where(
        AuthSession.project_id == proj.id,
        AuthSession.slot == slot,
        AuthSession.is_default.is_(True)))).scalar_one_or_none()
    a = AuthSession(
        owner_id=None, project_id=proj.id,
        alias=payload.alias, url=payload.url,
        username_enc=fernet_encrypt(payload.username),
        password_enc=fernet_encrypt(payload.password),
        token_type=payload.token_type, expires_in=payload.expires_in,
        system=payload.system, env_id=payload.env_id, slot=slot,
        account_fields=payload.account_fields,
        is_default=has_default is None,
    )
    db.add(a)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "slot_bound",
                    "message": f"slot '{slot}' already bound for this "
                               "system/env"}) from None
    await db.refresh(a)
    out = _to_out(a)
    await _after_write(db, user, proj, "create", a)
    return out


async def _set_default(db: AsyncSession, a: AuthSession) -> None:
    await db.execute(update(AuthSession).where(
        AuthSession.project_id == a.project_id,
        AuthSession.slot == a.slot,
        AuthSession.id != a.id,
        AuthSession.is_default.is_(True),
    ).values(is_default=False))
    a.is_default = True


@router.post("/{cid}/default", response_model=AuthSessionOut)
async def set_default_project_credential(
    user: CurrentUser, db: DbSession, project_id: int,
    cid: Annotated[int, PathParam(ge=1)],
) -> AuthSessionOut:
    proj = await _manage_gate(db, user, project_id)
    a = await _get_cred(db, proj.id, cid)
    await _set_default(db, a)
    await db.commit()
    await db.refresh(a)
    out = _to_out(a)
    await _after_write(db, user, proj, "default", a)
    return out


# ── patch ──────────────────────────────────────────────────────
@router.patch("/{cid}", response_model=AuthSessionOut)
async def patch_project_credential(
    payload: AuthSessionPatchIn, user: CurrentUser, db: DbSession,
    project_id: int, cid: Annotated[int, PathParam(ge=1)],
) -> AuthSessionOut:
    proj = await _manage_gate(db, user, project_id)
    a = await _get_cred(db, proj.id, cid)
    _require_maskable_password(payload.password)
    if payload.url is not None and payload.url != a.url and \
            payload.password is None:
        # r5-2.2:改登录地址必须同时重录密码 —— 拨测/执行会把解密
        # 凭据发往 a.url,单改地址即把存量密码重定向到任意端点
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "url_change_requires_password",
                    "message": "修改登录地址须重新录入密码"
                               "(凭据会发往该地址,改址即改去向)"})
    if "system" in payload.model_fields_set:
        a.system = payload.system or ""
    if "env_id" in payload.model_fields_set:
        if payload.env_id is not None:
            from ..models.environment import Environment
            if await db.get(Environment, payload.env_id) is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"code": "environment_not_found",
                            "message": f"environment not found: "
                                       f"{payload.env_id}"})
        a.env_id = payload.env_id
    if payload.account_fields is not None:
        a.account_fields = payload.account_fields
    if payload.is_default:
        await _set_default(db, a)
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
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "update_conflict", "message": "更新冲突"}) from None
    await db.refresh(a)
    out = _to_out(a)
    await _after_write(db, user, proj, "update", a)
    return out


# ── delete ─────────────────────────────────────────────────────
@router.delete("/{cid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_credential(
    user: CurrentUser, db: DbSession, project_id: int,
    cid: Annotated[int, PathParam(ge=1)],
) -> None:
    proj = await _manage_gate(db, user, project_id)
    a = await _get_cred(db, proj.id, cid)
    snapshot = SimpleNamespace(id=a.id, slot=a.slot, alias=a.alias)
    await db.delete(a)
    await db.commit()
    await _after_write(db, user, proj, "delete", snapshot)


# ── test ───────────────────────────────────────────────────────
@router.post("/{cid}/test", response_model=TestResult)
async def test_project_credential(
    user: CurrentUser, db: DbSession, project_id: int,
    cid: Annotated[int, PathParam(ge=1)],
) -> TestResult:
    proj = await _manage_gate(db, user, project_id)
    a = await _get_cred(db, proj.id, cid)
    if not a.url:
        return TestResult(ok=True, message="静态令牌认证:无登录流程,不做拨测")
    try:
        username = fernet_decrypt(a.username_enc)
        password = fernet_decrypt(a.password_enc)
    except ValueError as e:
        logger.warning("project credential test: decrypt failed: {}", e)
        return TestResult(ok=False, message="加密凭据已损坏，请重新录入")
    ok, status_code, message = await auth_probe.probe(a.url, username, password)
    return TestResult(ok=ok, status_code=status_code, message=message)
