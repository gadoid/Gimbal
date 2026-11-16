"""Pydantic schemas for the auth API(重构 2026-11-16 账户实体化 §1.4)。

账户 = 登录信息实体:(pool, system, env, username) 唯一,密码只存一份;
身份条目(service_identities)按 ref 引用账户。url/alias/slot 字段退役:
登录口在实例(system_env_instances.login_url,回显只读),引用键在条目。
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .page import PageOut


class AuthAccountOut(BaseModel):
    """账户行的对外视图(password 恒掩码;解密注入由服务端完成)。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    username: str
    # 系统名(plate system 口径,非服务名;与实例/条目同键域)
    system: str
    env_id: int = Field(alias="envId")
    token_type: str = "Bearer"
    expires_in: int = 7200
    is_default: bool = Field(default=False, alias="isDefault")
    account_fields: dict = Field(default_factory=dict,
                                 alias="accountFields")
    # 实例登录口回显(只读;配置在环境配置页,不在账户上)
    login_url: str = Field(default="", alias="loginUrl")
    # 引用计数(ref 该账户的身份条目数;场景计数 = 条目聚合,默认 0 —
    # 非列表调用方不填)
    identity_ref_count: int = Field(default=0, alias="identityRefCount")
    scenario_ref_count: int = Field(default=0, alias="scenarioRefCount")
    created_at: datetime
    updated_at: datetime
    password_masked: str = Field(default="<REDACTED>")


class AuthListOut(PageOut[AuthAccountOut]):
    """M4 Page 信封 + 全量类型计数(metaText 的服务端供给)。"""

    token_type_counts: dict[str, int] = Field(
        default_factory=dict, alias="tokenTypeCounts")


class IdentityRefItem(BaseModel):
    """反查面板 · 引用该账户的身份条目行。"""

    # populate_by_name:references() 服务层产 snake 键,校验按字段名收,
    # 序列化仍走 camel 别名(P1 缺陷修复:缺此项时 model_validate 只认
    # 别名 → 整包被当未知键丢弃,反查面板恒空)
    model_config = ConfigDict(populate_by_name=True)

    alias_name: str = Field(alias="aliasName")
    base_service: str = Field(alias="baseService")
    env_id: int = Field(alias="envId")
    ref_mode: str = Field(default="default", alias="refMode")
    ref_username: str | None = Field(default=None, alias="refUsername")


class ScenarioRefItem(BaseModel):
    """反查面板 · 单条场景引用:kinds ⊆ {template, snapshot}。

    owner_id 供前端算「删除会被拦截」的预告(与 DELETE 409 同口径:
    本人场景的 template 才阻断,schemas 见 auth_references)。
    """

    model_config = ConfigDict(populate_by_name=True)

    scenario_id: str = Field(alias="scenarioId")
    name: str
    kinds: list[str]
    owner_id: int = Field(alias="ownerId")


class ScenarioRefsOut(BaseModel):
    # hidden_count 无别名,visible 嵌套条目按名收(populate 递归生效)
    model_config = ConfigDict(populate_by_name=True)

    visible: list[ScenarioRefItem] = Field(default_factory=list)
    hidden_count: int = 0


class AuthReferencesOut(BaseModel):
    """GET /auths/{id}/references(账户引用反查):ref 条目清单 + 场景
    引用(经条目名聚合,实时扫,不建反向索引)。"""

    model_config = ConfigDict(populate_by_name=True)

    identity_refs: list[IdentityRefItem] = Field(default_factory=list,
                                                 alias="identityRefs")
    scenario_refs: ScenarioRefsOut = Field(default_factory=ScenarioRefsOut,
                                           alias="scenarioRefs")


class AuthAccountCreateIn(BaseModel):
    """账户登记:system/env 必填(登录打到具体环境实例);登录口不收
    (在实例上)。"""

    system: str = Field(min_length=1, max_length=128)
    env_id: int = Field(ge=1, alias="envId")
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1)
    token_type: str = Field(default="Bearer")
    expires_in: int = Field(default=7200, ge=0)
    account_fields: dict = Field(default_factory=dict,
                                 alias="accountFields")
    is_default: bool = Field(default=False, alias="isDefault")


class AuthAccountPatchIn(BaseModel):
    """username 不可改(账户实体键;换账号 = 删旧建新);system/env 改动
    即换实体坐标(整账户迁移到另一系统/环境)。"""

    system: str | None = Field(default=None, min_length=1, max_length=128)
    env_id: int | None = Field(default=None, ge=1, alias="envId")
    account_fields: dict | None = Field(default=None,
                                        alias="accountFields")
    is_default: bool | None = Field(default=None, alias="isDefault")
    password: str | None = Field(default=None, min_length=1)
    token_type: str | None = None
    expires_in: int | None = Field(default=None, ge=0)


class TestResult(BaseModel):
    ok: bool
    status_code: int | None = None
    message: str


class AuthAccountSecretsOut(AuthAccountOut):
    """include_secrets=true 时的详情视图 — 附解密后的明文 password。

    仅限内网测试环境的策略放宽(2026-08-25 认证改造设计):场景配置页
    "从凭证池导入"需要把明文快照拷进 config.users(导出在前端本地拼装,
    明文必须过客户端)。列表接口行为不变,不带密。
    """

    password: str
