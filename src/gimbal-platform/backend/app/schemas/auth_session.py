"""Pydantic schemas for the auth-sessions API (Spec-2 §4.4 D)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .page import PageOut


class AuthSessionOut(BaseModel):
    """Public-facing view of an AuthSession row.

    Note: the password is NEVER returned in plaintext.  ``password_masked``
    is a sentinel the UI uses to render ``<REDACTED>``.  凭证解密注入由
    run_dispatcher 服务端完成(不对外下发)。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    alias: str
    url: str
    username: str  # decrypted server-side
    token_type: str
    expires_in: int
    # S3 槽位绑定:system ''=未归类;env None=不限;slot=注入键;
    # is_default=名字解析取用行;account_fields=账号级字段(明文非密,
    # F6:只能经 ${slot.X.field} 消费)
    system: str = ""
    env_id: int | None = Field(default=None, alias="envId")
    slot: str = ""
    is_default: bool = Field(default=False, alias="isDefault")
    account_fields: dict = Field(default_factory=dict,
                                 alias="accountFields")
    created_at: datetime
    updated_at: datetime
    password_masked: str = Field(default="<REDACTED>")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    # 反查双计数(配套方案 §1.2):N 别名 / N 场景(模板∪方案绑定,
    # 快照不进计数)。默认 0 — 非列表调用方(detail/test)不填。
    alias_ref_count: int = Field(default=0)
    scenario_ref_count: int = Field(default=0)


class AuthListOut(PageOut[AuthSessionOut]):
    """M4 Page 信封 + 全量类型计数(metaText 的服务端供给)。"""

    token_type_counts: dict[str, int] = Field(
        default_factory=dict, alias="tokenTypeCounts")


class AliasRefItem(BaseModel):
    """反查面板 · 别名绑定行(service_aliases.slot 命中)。"""

    alias_name: str
    base_service: str
    environment_id: int | None = None


class ScenarioRefItem(BaseModel):
    """反查面板 · 单条场景引用:kinds ⊆ {template, scheme, snapshot}。

    owner_id 供前端算「删除会被拦截」的预告(与 DELETE 409 同口径:
    本人场景的 template/scheme 才阻断,schemas 见 auth_references)。
    """

    scenario_id: str
    name: str
    kinds: list[str]
    owner_id: int


class ScenarioRefsOut(BaseModel):
    visible: list[ScenarioRefItem] = Field(default_factory=list)
    hidden_count: int = 0


class AuthReferencesOut(BaseModel):
    """GET /auths/{alias}/references(配套方案 §1.3):实时扫,不建反向索引。"""

    alias_refs: list[AliasRefItem] = Field(default_factory=list)
    scenario_refs: ScenarioRefsOut = Field(default_factory=ScenarioRefsOut)


class AuthSessionCreateIn(BaseModel):
    alias: str = Field(min_length=1, max_length=64)
    # S3 槽位绑定:槽名缺省 = 别名;system/env/account_fields 可后补
    slot: str | None = Field(default=None, min_length=1, max_length=64)
    system: str = Field(default="", max_length=128)
    env_id: int | None = Field(default=None, ge=1, alias="envId")
    account_fields: dict = Field(default_factory=dict,
                                 alias="accountFields")
    # authz C2:静态令牌认证方式(自举系统 platform 等)—— 免登录 URL,
    # password 存令牌本体,执行期按 token_type 直接施加,不走登录。
    # url 留空 = 静态方式;登录式(url 非空)与既有行为逐字段一致。
    url: str = Field(default="", max_length=512)
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    token_type: str = Field(default="Bearer")
    expires_in: int = Field(default=7200, ge=0)


class AuthSessionPatchIn(BaseModel):
    system: str | None = Field(default=None, max_length=128)
    env_id: int | None = Field(default=None, ge=1, alias="envId")
    account_fields: dict | None = Field(default=None,
                                        alias="accountFields")
    is_default: bool | None = Field(default=None, alias="isDefault")
    url: str | None = Field(default=None, max_length=512)
    username: str | None = Field(default=None, min_length=1)
    password: str | None = Field(default=None, min_length=1)
    token_type: str | None = None
    expires_in: int | None = Field(default=None, ge=0)


class TestResult(BaseModel):
    ok: bool
    status_code: int | None = None
    message: str


class AuthSessionSecretsOut(AuthSessionOut):
    """include_secrets=true 时的详情视图 — 附解密后的明文 password。

    仅限内网测试环境的策略放宽(2026-08-25 认证改造设计):场景配置页
    "从凭证池导入"需要把明文快照拷进 config.users(导出在前端本地拼装,
    明文必须过客户端)。列表接口行为不变,不带密。
    """

    password: str