"""服务别名路由(服务画像方案 §4.1;基础层)— 读全员 / 写 admin。

配置池语义同 carry(读开放、写收口):别名影响的是所有引用该服务的
场景的执行解析,写面收在 admin;``owner_user_id`` 字段承载个人默认 /
团队共享的语义区分,不等于编辑权限。

入站身份管理面(webhook 设计 v3 P1 §4.5)也挂在本路由:入站凭证
(gic_)/ 入站与回调设置 / grant(ggt_)。权限口径:**别名属主或
admin**(团队共享别名 owner_user_id 为空 → 只有 admin);grant 的
签发是用户自授权(「授权该别名代我执行」),能看到别名的用户即可
签发,撤销限签发人或 admin。
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..schemas.page import PageOut
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.db import get_db
from ..core.deps import AdminUser, CurrentUser, MemberUser
from ..core.security import fernet_encrypt
from ..core.timeutil import iso_utc_z
from ..models.inbound_identity import InboundCredential, InboundGrant
from ..models.service_alias import ServiceAlias
from ..models.user import User
from ..services import inbound_identity, service_aliases
from ..services.inbound_identity import (
    generate_credential_token, generate_grant_token, sha256_hex,
)
from ..services.service_aliases import UnknownBaseService

router = APIRouter(prefix="/service-aliases", tags=["service-aliases"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

_CAMEL = ConfigDict(populate_by_name=True)


class AliasOut(BaseModel):
    model_config = _CAMEL

    alias_name: str = Field(alias="aliasName")
    base_service: str = Field(alias="baseService")
    # F4 方案 B:环境级端点默认层(物化优先级链第三档;NULL = 不提供)
    base_url: str | None = Field(default=None, alias="baseUrl")
    # V5(B):归属环境(group_tag 已退役,外键 → environments)
    environment_id: int | None = Field(default=None, alias="environmentId")
    environment_name: str | None = Field(default=None, alias="environmentName")
    credential_alias: str | None = Field(default=None, alias="credentialAlias")
    owner_user_id: int | None = Field(default=None, alias="ownerUserId")
    # 三态接入(P1.0):plate(受管) | external(第三方,无版本管理)
    kind: str = Field(default="plate", alias="kind")
    # 入站与回调(webhook 设计 v3 P1):secret 只回「是否已设」,密文不外露
    inbound_enabled: bool = Field(default=False, alias="inboundEnabled")
    callback_enabled: bool = Field(default=False, alias="callbackEnabled")
    callback_path: str | None = Field(default=None, alias="callbackPath")
    callback_secret_set: bool = Field(default=False, alias="callbackSecretSet")
    created_at: str | None = Field(default=None, alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")


class AliasListOut(PageOut[AliasOut]):
    """M4 Page 信封(§6.3)。"""


class AliasCreate(BaseModel):
    model_config = _CAMEL

    alias_name: str = Field(min_length=1, max_length=128, alias="aliasName")
    # 2026-09-23 调整:别名 = 环境端点的登记,URL 必填(缺省/空串 422);
    # patch 保持可空兼容(存量行可在触达时补齐)。
    base_url: str = Field(min_length=1, max_length=512, alias="baseUrl")
    environment_id: int | None = Field(default=None, alias="environmentId")
    credential_alias: str | None = Field(
        default=None, max_length=64, alias="credentialAlias")
    owner_user_id: int | None = Field(default=None, alias="ownerUserId")
    # 三态接入(P1.0):plate 走目录派生强约束。b2-8/b2-10d(归一 v1.0
    # §1.6):external 不派生 —— 必填显式 base_service(指向 plate 目录
    # kind=integration 的服务;校验在 service 层)。
    kind: Literal["plate", "external"] = "plate"
    base_service: str | None = Field(
        default=None, max_length=128, alias="baseService")


class AliasPatch(BaseModel):
    model_config = _CAMEL

    base_url: str | None = Field(
        default=None, max_length=512, alias="baseUrl")
    environment_id: int | None = Field(default=None, alias="environmentId")
    credential_alias: str | None = Field(
        default=None, max_length=64, alias="credentialAlias")
    # b2-8:base_service 仅 external 可改(重指向 integration 系统)
    base_service: str | None = Field(
        default=None, max_length=128, alias="baseService")
    # b2-8:kind 仅支持 external→plate(升级路径,§1.8)
    kind: Literal["plate", "external"] | None = None


@router.get("", response_model=AliasListOut)
async def list_aliases(
    user: CurrentUser, db: DbSession,
    base: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=128),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
) -> AliasListOut:
    """M4(§6.3):Page 信封 + ``q``(alias/base/credential 子串)下推。"""
    items, total = await service_aliases.list_aliases(
        db, base=base, q=q, page=page, page_size=page_size)
    return AliasListOut(
        items=[AliasOut.model_validate(a) for a in items],
        total=total, page=page, page_size=page_size,
    )


class ServiceKindsOut(BaseModel):
    """W11 三态分类读面(编排器徽标/保存告警数据源)。

    plate = 受管(可钉修订);external = 第三方(无版本,不计入库
    标准的分母);unknown = 未登记(保存告警口径:提示接入 plate 或
    登记 external 别名;执行侧按 external 保守处理)。
    """

    model_config = _CAMEL

    plate: list[str] = Field(default_factory=list)
    external: list[str] = Field(default_factory=list)
    unknown: list[str] = Field(default_factory=list)


@router.get("/classify", response_model=ServiceKindsOut)
async def classify(
    user: CurrentUser, db: DbSession,
    services: list[str] = Query(default=[], max_length=64),
) -> ServiceKindsOut:
    """步骤 ``service`` 键集 → 三态分类(P1.0 判定链,W11 数据面)。"""
    out = await service_aliases.classify_services(db, services)
    return ServiceKindsOut(**out)


@router.post("", response_model=AliasOut, status_code=201)
async def create_alias(
    user: MemberUser, body: AliasCreate, db: DbSession,
) -> AliasOut:
    """登记别名(M2.5,权限方案 §1.2 两类归属拆行):
    团队共享(owner_user_id 空)= member+;个人默认(owner_user_id
    非空,即「归属字段」)= admin —— 人事/内容权不落进技术运营角色。"""
    if body.owner_user_id is not None and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin_only: personal aliases (ownerUserId) are managed by admins",
        )
    try:
        created = await service_aliases.create_alias(
            db, alias_name=body.alias_name, environment_id=body.environment_id,
            credential_alias=body.credential_alias,
            owner_user_id=body.owner_user_id,
            base_url=body.base_url, kind=body.kind,
            base_service=body.base_service)
    except UnknownBaseService as e:
        # 强约束(§4.1 拍板):裸声明不猜;plate 宕机期间不能登记
        # (kind=external 不受此约束 —— 第三方无目录概念)
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e
    except KeyError as e:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, str(e)) from e
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=user.display_name or user.username,
        action="alias.write", resource_type="alias",
        resource_id=body.alias_name, detail={"fn": "create"},
    )
    return AliasOut.model_validate(created)


@router.patch("/{alias_name}", response_model=AliasOut)
async def patch_alias(
    alias_name: str, user: MemberUser, body: AliasPatch, db: DbSession,
) -> AliasOut:
    """改别名:共享行 member+;个人行 admin(归属域的写权只属 admin)。"""
    row = (await db.execute(
        select(ServiceAlias).where(ServiceAlias.alias_name == alias_name)
    )).scalar_one_or_none()
    if row is not None and row.owner_user_id is not None and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin_only: personal aliases are managed by admins",
        )
    try:
        explicit_env = ("environment_id" in body.model_fields_set
                        or "environmentId" in body.model_fields_set)
        explicit_cred = ("credential_alias" in body.model_fields_set
                         or "credentialAlias" in body.model_fields_set)
        explicit_url = ("base_url" in body.model_fields_set
                        or "baseUrl" in body.model_fields_set)
        patched = await service_aliases.patch_alias(
            db, alias_name,
            environment_id=body.environment_id if explicit_env else ...,
            credential_alias=body.credential_alias if explicit_cred else ...,
            base_url=body.base_url if explicit_url else ...,
            base_service=(body.base_service if body.base_service is not None else ...),
            kind=body.kind)
    except KeyError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=user.display_name or user.username,
        action="alias.write", resource_type="alias",
        resource_id=alias_name, detail={"fn": "patch"},
    )
    return AliasOut.model_validate(patched)


@router.delete("/{alias_name}", status_code=204)
async def delete_alias(
    alias_name: str, user: MemberUser, db: DbSession
) -> None:
    row = (await db.execute(
        select(ServiceAlias).where(ServiceAlias.alias_name == alias_name)
    )).scalar_one_or_none()
    if row is not None and row.owner_user_id is not None and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin_only: personal aliases are managed by admins",
        )
    await service_aliases.delete_alias(db, alias_name)
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=user.display_name or user.username,
        action="alias.write", resource_type="alias",
        resource_id=alias_name, detail={"fn": "delete"},
    )


# ── 入站身份管理(webhook 设计 v3 P1 §4.5;仅 JWT)──────────────────


def _bad(code: str, message: str, status_code: int = 422) -> HTTPException:
    return HTTPException(status_code=status_code,
                         detail={"code": code, "message": message})


async def _get_alias(db: AsyncSession, alias_name: str) -> ServiceAlias:
    row = (await db.execute(
        select(ServiceAlias).where(ServiceAlias.alias_name == alias_name)
    )).scalar_one_or_none()
    if row is None:
        raise _bad("alias_not_found", f"别名不存在: {alias_name}", 404)
    return row


def _require_external(alias: ServiceAlias) -> None:
    """只有 kind=external 可承载入站(D2:入站身份挂在外部系统别名)。"""
    if alias.kind != "external":
        raise _bad(
            "kind_not_external",
            f"只有 kind=external 的别名可以启用入站(当前 {alias.kind})")


def _require_inbound_manager(user: User, alias: ServiceAlias) -> None:
    """入站设置/凭证管理:别名属主或 admin;团队共享别名只有 admin。"""
    if user.role == "admin":
        return
    if alias.owner_user_id is None or alias.owner_user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="inbound managed by the alias owner or an admin")


def valid_callback_path(path: str) -> bool:
    """回调路径判定(唯一实现见 services/inbound_identity;此处再导出
    仅为路由内就近可读)。"""
    return inbound_identity.valid_callback_path(path)


class InboundCredentialIn(BaseModel):
    model_config = _CAMEL

    name: str = Field(default="", max_length=64)


class InboundCredentialOut(BaseModel):
    model_config = _CAMEL

    id: int
    name: str = ""
    created_at: str | None = Field(default=None, alias="createdAt")
    last_used_at: str | None = Field(default=None, alias="lastUsedAt")
    revoked_at: str | None = Field(default=None, alias="revokedAt")


class InboundCredentialCreated(InboundCredentialOut):
    """生成响应:明文令牌只出现一次(库中只存 sha256)。"""

    token: str


class InboundSettingsIn(BaseModel):
    model_config = _CAMEL

    inbound_enabled: bool | None = Field(default=None, alias="inboundEnabled")
    callback_enabled: bool | None = Field(default=None, alias="callbackEnabled")
    callback_path: str | None = Field(
        default=None, max_length=256, alias="callbackPath")
    # 轮换回调签名密钥:生成新 Fernet 密钥,明文只在响应里出现一次
    rotate_secret: bool = Field(default=False, alias="rotateSecret")


class InboundSettingsOut(BaseModel):
    model_config = _CAMEL

    alias_name: str = Field(alias="aliasName")
    kind: str
    inbound_enabled: bool = Field(default=False, alias="inboundEnabled")
    callback_enabled: bool = Field(default=False, alias="callbackEnabled")
    callback_path: str | None = Field(default=None, alias="callbackPath")
    callback_secret_set: bool = Field(default=False, alias="callbackSecretSet")
    # 仅 rotateSecret 时返回:新密钥明文(只此一次)
    callback_secret: str | None = Field(default=None, alias="callbackSecret")


class GrantIn(BaseModel):
    model_config = _CAMEL

    # 有效期(天):缺省 GRANT_DEFAULT_TTL_DAYS,上限 GRANT_MAX_TTL_DAYS
    ttl_days: int | None = Field(default=None, ge=1, alias="ttlDays")


class GrantOut(BaseModel):
    model_config = _CAMEL

    id: int
    alias_name: str = Field(alias="aliasName")
    user_id: int = Field(alias="userId")
    username: str | None = None
    expires_at: str | None = Field(default=None, alias="expiresAt")
    created_at: str | None = Field(default=None, alias="createdAt")
    last_used_at: str | None = Field(default=None, alias="lastUsedAt")
    revoked_at: str | None = Field(default=None, alias="revokedAt")


class GrantCreated(GrantOut):
    token: str


@router.post(
    "/{alias_name}/inbound-credentials",
    response_model=InboundCredentialCreated, status_code=201)
async def create_inbound_credential(
    alias_name: str, user: CurrentUser, db: DbSession,
    body: InboundCredentialIn | None = None,
) -> InboundCredentialCreated:
    """生成入站凭证(gic_):明文只返回一次(设计 §4.5)。"""
    alias = await _get_alias(db, alias_name)
    _require_external(alias)
    _require_inbound_manager(user, alias)
    token = generate_credential_token()
    cred = InboundCredential(
        alias_name=alias_name, token_hash=sha256_hex(token),
        name=((body.name if body is not None else "") or "")[:64],
        created_by=user.id)
    db.add(cred)
    await db.commit()
    await db.refresh(cred)
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id, actor_name=user.display_name or user.username,
        action="inbound.credential.write", resource_type="alias",
        resource_id=alias_name, detail={"fn": "create", "credential": cred.id},
    )
    return InboundCredentialCreated(
        id=cred.id, name=cred.name, token=token,
        createdAt=iso_utc_z(cred.created_at))


@router.get("/{alias_name}/inbound-credentials",
            response_model=list[InboundCredentialOut])
async def list_inbound_credentials(
    alias_name: str, user: CurrentUser, db: DbSession,
) -> list[InboundCredentialOut]:
    alias = await _get_alias(db, alias_name)
    _require_inbound_manager(user, alias)
    rows = (await db.execute(
        select(InboundCredential).where(
            InboundCredential.alias_name == alias_name)
        .order_by(InboundCredential.id.desc()))).scalars().all()
    return [InboundCredentialOut(
        id=r.id, name=r.name, createdAt=iso_utc_z(r.created_at),
        lastUsedAt=iso_utc_z(r.last_used_at), revokedAt=iso_utc_z(r.revoked_at))
        for r in rows]


@router.delete("/{alias_name}/inbound-credentials/{cred_id}",
               status_code=204)
async def revoke_inbound_credential(
    alias_name: str, cred_id: int, user: CurrentUser, db: DbSession,
) -> None:
    alias = await _get_alias(db, alias_name)
    _require_inbound_manager(user, alias)
    cred = await db.get(InboundCredential, cred_id)
    if cred is None or cred.alias_name != alias_name:
        raise _bad("credential_not_found", "凭证不存在", 404)
    if cred.revoked_at is None:
        cred.revoked_at = datetime.now(timezone.utc)
        await db.commit()
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id, actor_name=user.display_name or user.username,
        action="inbound.credential.write", resource_type="alias",
        resource_id=alias_name, detail={"fn": "revoke", "credential": cred_id},
    )


@router.put("/{alias_name}/inbound", response_model=InboundSettingsOut)
async def put_inbound_settings(
    alias_name: str, body: InboundSettingsIn, user: CurrentUser,
    db: DbSession,
) -> InboundSettingsOut:
    """开关入站/回调、设置回调路径、可选轮换签名密钥(§4.5)。

    回调开启的前提:``base_url`` 与 ``callback_path`` 齐备(否则 422
    —— 开了也没有可投递的地址)。密钥在**首次开启时自动生成**,明文
    随本次响应返回一次(否则接收方无从验签);显式 ``rotateSecret``
    换新,旧密钥即时失效 —— 新明文同样只在本次响应出现。轮换后已在途
    的投递行按新密钥签发(密钥投递时从别名现取,设计 §5.2)。"""
    alias = await _get_alias(db, alias_name)
    _require_external(alias)
    _require_inbound_manager(user, alias)
    explicit_path = ("callback_path" in body.model_fields_set
                     or "callbackPath" in body.model_fields_set)
    if explicit_path and body.callback_path is not None \
            and not valid_callback_path(body.callback_path):
        raise _bad(
            "callback_path_invalid",
            "callbackPath 必须是以 / 开头的路径段(不含协议与主机)")
    if body.inbound_enabled is not None:
        alias.inbound_enabled = body.inbound_enabled
    if body.callback_enabled is not None:
        alias.callback_enabled = body.callback_enabled
    if explicit_path:
        alias.callback_path = body.callback_path
    new_secret: str | None = None
    if alias.callback_enabled:
        if not (alias.base_url and alias.callback_path):
            await db.rollback()
            raise _bad(
                "callback_target_missing",
                "开启回调需要 base_url 与 callback_path(可拼出回调 URL)")
        if not alias.callback_secret or body.rotate_secret:
            # 首次开启(auto)与显式轮换同一路径:生成新密钥,**明文随
            # 本响应返回一次**(否则首次开启的接收方永远拿不到密钥、
            # 无法验签);轮换后旧密钥立即失效,已在途投递行按新密钥
            # 签发(密钥投递时从别名现取)。不使用 gic_/ggt_ 前缀 ——
            # 它是签名密钥而非令牌,前缀会与身份令牌混淆。
            new_secret = secrets.token_urlsafe(32)
            alias.callback_secret = fernet_encrypt(new_secret)
    elif body.rotate_secret:
        await db.rollback()
        raise _bad(
            "rotate_requires_callback",
            "rotateSecret 只在回调开启(callbackEnabled)时有意义")
    await db.commit()
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id, actor_name=user.display_name or user.username,
        action="inbound.settings.write", resource_type="alias",
        resource_id=alias_name,
        detail={"fn": "put", "inbound_enabled": alias.inbound_enabled,
                "callback_enabled": alias.callback_enabled,
                "rotated": bool(body.rotate_secret)},
    )
    return InboundSettingsOut(
        aliasName=alias.alias_name, kind=alias.kind,
        inboundEnabled=alias.inbound_enabled,
        callbackEnabled=alias.callback_enabled,
        callbackPath=alias.callback_path,
        callbackSecretSet=bool(alias.callback_secret),
        callbackSecret=new_secret,
    )


@router.post("/{alias_name}/grants",
             response_model=GrantCreated, status_code=201)
async def create_grant(
    alias_name: str, body: GrantIn, user: CurrentUser, db: DbSession,
) -> GrantCreated:
    """当前用户为该别名签发 grant(自授权:授权该别名代我执行)。

    明文 ggt_… 只返回一次;有效期缺省 GRANT_DEFAULT_TTL_DAYS,
    上限 GRANT_MAX_TTL_DAYS(§4.1)。"""
    alias = await _get_alias(db, alias_name)
    _require_external(alias)
    ttl = body.ttl_days if body.ttl_days is not None \
        else settings.GRANT_DEFAULT_TTL_DAYS
    if ttl > settings.GRANT_MAX_TTL_DAYS:
        raise _bad(
            "grant_ttl_too_long",
            f"ttlDays 上限 {settings.GRANT_MAX_TTL_DAYS}(当前 {ttl})")
    token = generate_grant_token()
    now = datetime.now(timezone.utc)
    g = InboundGrant(
        alias_name=alias_name, user_id=user.id,
        token_hash=sha256_hex(token),
        expires_at=now + timedelta(days=ttl))
    db.add(g)
    await db.commit()
    await db.refresh(g)
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id, actor_name=user.display_name or user.username,
        action="inbound.grant.write", resource_type="alias",
        resource_id=alias_name,
        detail={"fn": "issue", "grant": g.id, "ttl_days": ttl},
    )
    return GrantCreated(
        id=g.id, aliasName=alias_name, userId=user.id,
        username=user.username, token=token,
        expiresAt=iso_utc_z(g.expires_at), createdAt=iso_utc_z(g.created_at))


@router.get("/{alias_name}/grants", response_model=list[GrantOut])
async def list_grants(
    alias_name: str, user: CurrentUser, db: DbSession,
) -> list[GrantOut]:
    """列 grant:普通用户只看自己的;admin 看全部(§4.5)。"""
    await _get_alias(db, alias_name)
    q = select(InboundGrant).where(InboundGrant.alias_name == alias_name)
    if user.role != "admin":
        q = q.where(InboundGrant.user_id == user.id)
    rows = (await db.execute(
        q.order_by(InboundGrant.id.desc()))).scalars().all()
    usernames: dict[int, str] = {}
    if rows:
        uids = {r.user_id for r in rows}
        for u in (await db.execute(
                select(User).where(User.id.in_(uids)))).scalars():
            usernames[u.id] = u.username
    return [GrantOut(
        id=r.id, aliasName=r.alias_name, userId=r.user_id,
        username=usernames.get(r.user_id, "(已删除)"),
        expiresAt=iso_utc_z(r.expires_at), createdAt=iso_utc_z(r.created_at),
        lastUsedAt=iso_utc_z(r.last_used_at), revokedAt=iso_utc_z(r.revoked_at))
        for r in rows]


@router.delete("/{alias_name}/grants/{grant_id}", status_code=204)
async def revoke_grant(
    alias_name: str, grant_id: int, user: CurrentUser, db: DbSession,
) -> None:
    """撤销 grant:签发人或 admin。只撤销不硬删(留审计面)。"""
    await _get_alias(db, alias_name)
    g = await db.get(InboundGrant, grant_id)
    if g is None or g.alias_name != alias_name:
        raise _bad("grant_not_found", "grant 不存在", 404)
    if user.role != "admin" and g.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="grant 只能由签发人或 admin 撤销")
    if g.revoked_at is None:
        g.revoked_at = datetime.now(timezone.utc)
        await db.commit()
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id, actor_name=user.display_name or user.username,
        action="inbound.grant.write", resource_type="alias",
        resource_id=alias_name, detail={"fn": "revoke", "grant": grant_id},
    )

