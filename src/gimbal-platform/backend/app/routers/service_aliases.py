"""服务别名路由(服务画像方案 §4.1;基础层)— 读全员 / 写 admin。

配置池语义同 carry(读开放、写收口):别名影响的是所有引用该服务的
场景的执行解析,写面收在 admin。authz M2a S6:别名只登记「名字 → 基础
服务 + 声明槽位」;地址在部署表(``/deployments``),个人别名退役。

webhook v4:入站身份(访问令牌)不再挂别名 —— 见
``routers/access_tokens.py``;回调地址与签名密钥在令牌上。
"""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..schemas.page import PageOut
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser, MemberUser
from ..services import service_aliases
from ..services.service_aliases import UnknownBaseService

router = APIRouter(prefix="/service-aliases", tags=["service-aliases"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

_CAMEL = ConfigDict(populate_by_name=True)


class AliasOut(BaseModel):
    model_config = _CAMEL

    alias_name: str = Field(alias="aliasName")
    base_service: str = Field(alias="baseService")
    # authz M2a S3/S6:别名声明槽位(唯一凭证口径)
    slot: str | None = Field(default=None, alias="slot")
    # 三态接入(P1.0):plate(受管) | external(第三方,无版本管理)
    kind: str = Field(default="plate", alias="kind")
    created_at: str | None = Field(default=None, alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")


class AliasListOut(PageOut[AliasOut]):
    """M4 Page 信封(§6.3)。"""


class AliasCreate(BaseModel):
    model_config = _CAMEL

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    alias_name: str = Field(min_length=1, max_length=128, alias="aliasName")
    slot: str | None = Field(default=None, max_length=64, alias="slot")
    # 三态接入(P1.0):plate 走目录派生强约束。b2-8/b2-10d(归一 v1.0
    # §1.6):external 不派生 —— 必填显式 base_service(指向 plate 目录
    # kind=integration 的服务;校验在 service 层)。
    kind: Literal["plate", "external"] = "plate"
    base_service: str | None = Field(
        default=None, max_length=128, alias="baseService")


class AliasPatch(BaseModel):
    # S6:退役字段(baseUrl/environmentId/credentialAlias/ownerUserId)422,
    # 不静默丢弃 —— 旧客户端以为改了地址更糟
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    slot: str | None = Field(default=None, max_length=64, alias="slot")
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
    """M4(§6.3):Page 信封 + ``q``(alias/base/slot 子串)下推。"""
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
    """登记别名(Admin+;S6 起别名全部团队共享,个人别名退役)。"""
    try:
        created = await service_aliases.create_alias(
            db, alias_name=body.alias_name, slot=body.slot,
            kind=body.kind, base_service=body.base_service)
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
    """改别名(Admin+)。``slot`` 显式给 null = 清除声明。"""
    try:
        patched = await service_aliases.patch_alias(
            db, alias_name,
            slot=body.slot if "slot" in body.model_fields_set else ...,
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
    await service_aliases.delete_alias(db, alias_name)
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=user.display_name or user.username,
        action="alias.write", resource_type="alias",
        resource_id=alias_name, detail={"fn": "delete"},
    )
