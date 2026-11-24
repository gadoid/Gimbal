"""服务别名路由(服务画像方案 §4.1;重构 2026-11-16 身份条目化)——
读全员 / 写 admin。

条目 = 「某环境某服务以什么身份登录」的引用声明(底座
``service_identities``);``slot`` 输出 = 条目名(规约延续,旧客户端
零适配),``kind`` 自服务主档。地址在部署表/实例表,个人别名早已退役。

webhook v4:入站身份(访问令牌)不再挂别名 —— 见
``routers/access_tokens.py``;回调地址与签名密钥在令牌上。
"""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..schemas.page import PageOut
from pydantic import BaseModel, ConfigDict, Field, model_validator
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
    # 重构:注入键 = 条目名(规约延续);kind 自服务主档
    slot: str | None = Field(default=None, alias="slot")
    kind: str = Field(default="plate", alias="kind")
    env_id: int | None = Field(default=None, alias="envId")
    ref_mode: str = Field(default="default", alias="refMode")
    ref_username: str | None = Field(default=None, alias="refUsername")
    display: str = Field(default="", alias="display")
    created_at: str | None = Field(default=None, alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")


class AliasListOut(PageOut[AliasOut]):
    """M4 Page 信封(§6.3)。"""


class AliasCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    alias_name: str = Field(min_length=1, max_length=128, alias="aliasName")
    # plate 走派生强约束(目录 ∪ 主档);external 显式 base_service
    # (指向主档第三方服务;校验在 service 层)。
    kind: Literal["plate", "external"] = "plate"
    base_service: str | None = Field(
        default=None, max_length=128, alias="baseService")
    # 重构新维度:环境必填(缺省 = 平台默认环境兜底)+ 账户引用
    env_id: int | None = Field(default=None, ge=1, alias="envId")
    ref_mode: Literal["default", "username"] = "default"
    ref_username: str = Field(default="", max_length=128, alias="refUsername")
    display: str = Field(default="", max_length=128)

    @model_validator(mode="after")
    def _username_ref_requires_name(self) -> "AliasCreate":
        """refMode=username 必须带 refUsername ——
        此前该组合可入库,后端执行回落默认账户、前端按空名过滤报缺,
        单源镜像在边缘值上分叉。写面拒绝,存量旧值仍按回落语义解析。"""
        if self.ref_mode == "username" and not self.ref_username.strip():
            raise ValueError(
                "ref_username_required: refMode=username 必须填写引用用户名")
        return self


class AliasPatch(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    base_service: str | None = Field(
        default=None, max_length=128, alias="baseService")
    kind: Literal["plate", "external"] | None = None
    ref_mode: Literal["default", "username"] | None = Field(
        default=None, alias="refMode")
    ref_username: str | None = Field(
        default=None, max_length=128, alias="refUsername")
    display: str | None = Field(default=None, max_length=128)


@router.get("", response_model=AliasListOut)
async def list_aliases(
    user: CurrentUser, db: DbSession,
    base: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=128),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
) -> AliasListOut:
    """M4(§6.3):Page 信封 + ``q``(alias/base/display 子串)下推。"""
    items, total = await service_aliases.list_aliases(
        db, base=base, q=q, page=page, page_size=page_size)
    return AliasListOut(
        items=[AliasOut.model_validate(a) for a in items],
        total=total, page=page, page_size=page_size,
    )


class ServiceKindsOut(BaseModel):
    """W11 三态分类读面(编排器徽标/保存告警数据源;kind 自主档)。"""

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
    """登记身份条目(Admin+;条目全部团队共享)。"""
    try:
        created = await service_aliases.create_alias(
            db, alias_name=body.alias_name,
            kind=body.kind, base_service=body.base_service,
            env_id=body.env_id, ref_mode=body.ref_mode,
            ref_username=body.ref_username, display=body.display)
    except UnknownBaseService as e:
        # 强约束:裸声明不猜;plate 不可达且主档未登记时不能登记
        # (kind=external 不受此约束 —— 第三方无目录概念)
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e
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
    """改身份条目(Admin+):ref/display 可改;``base_service`` 仅 external
    可重指(悬空条目唯一修正路径);``kind`` 由主档承载,转型在主档侧。"""
    try:
        patched = await service_aliases.patch_alias(
            db, alias_name,
            base_service=(body.base_service if body.base_service is not None else ...),
            kind=body.kind,
            ref_mode=body.ref_mode,
            ref_username=body.ref_username,
            display=body.display)
    except KeyError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e
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
    """删身份条目(Admin+):引用该条目名的场景模板下次运行将报缺 —
    前端删除确认时按引用计数提示(auth_references.cached_scenario_refs)。"""
    await service_aliases.delete_alias(db, alias_name)
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=user.display_name or user.username,
        action="alias.write", resource_type="alias",
        resource_id=alias_name, detail={"fn": "delete"},
    )
