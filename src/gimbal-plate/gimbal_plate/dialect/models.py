"""dialect.models —— 方言层 M2 模型（批次 A1，claude/plate-design.md 第 6 节）。

与存量 ``schema/endpoint`` 的关系（A1 期间两栈并存，A2 切换消费方后退役旧栈）：

- 本模块定义**修订后的 EndpointSpec**：Binding 判别联合（取代 ApiSpec）、
  responses 按结果键（str，N1：键即 outcome 不双写字段）、删 version /
  updated_at（8n）、capability / consumes / produces 词条引用、body_type
  自 RequestSpec 移入 binding。
- DeclarationEntry / QueryView / EndpointMetadata / ServiceDefinition 等
  共享模型仍从 ``gimbal_plate.schema`` 导入（单一定义，A2 归并）。
- 块信封 ``review`` 由方言层处理（parser/renderer），不进任何 M2 模型
  （8s）；本模块的模型均为 ``extra="forbid"`` 封闭模型。

模型内只做自身校验；跨对象校验（引用、一致性）在加载 / release 时
（批次 B 的 F/T/S/C 全量规则）。
"""
from __future__ import annotations

import re
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from gimbal_plate.schema.endpoint.io_spec import DeclarationEntry, _check_declarations
from gimbal_plate.schema.endpoint.metadata import EndpointMetadata
from gimbal_plate.schema.endpoint.query_view import QueryView, resolve_view_params

_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_.\-]{1,63}$")
# http 协议的结果键：三位数字字符串（原 status: int 的字符串化，6.2）
_HTTP_OUTCOME_PATTERN = re.compile(r"^\d{3}$")


class _TaggedBindingMixin:
    """判别联合成员的序列化纪律:tag 字段是**身份字段**,不是数据字段——
    即便等于默认值也恒序列化(否则 exclude_defaults 会剥掉 tag,重解析时
    判别联合失tag;往返与 hash 均依赖此纪律)。键位置保持模型定义序。"""

    TAG_FIELD = "protocol"

    @model_serializer(mode="wrap")
    def _keep_tag(self, handler, info):  # noqa: ANN001, ANN202
        data = handler(self)
        tag = getattr(self, self.TAG_FIELD)
        if self.TAG_FIELD in data:
            return data
        return {self.TAG_FIELD: tag, **data}


class HttpBinding(_TaggedBindingMixin, BaseModel):
    """http 协议的 Binding（判别联合的首个实例，P5）。

    ``auth`` 描述被测接口自身的认证方式，与 plate 服务是否认证无关；
    ``body_type`` 自 RequestSpec 移入（请求体形态是协议层属性）。
    """

    model_config = ConfigDict(extra="forbid")

    protocol: Literal["http"] = "http"
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
    path: str
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float = 30.0
    auth: Literal["none", "bearer", "basic", "cookie", "custom"] = "none"
    body_type: Literal["none", "json", "form", "multipart", "raw", "binary"] = "json"

    def locator(self) -> tuple[str, str]:
        """协议自己的接口定位字段（路由键组成，F3：protocol+service+locator）。"""
        return (self.method, self.path)

    def side_effect_free(self) -> bool:
        """无副作用判定（query_views 护栏与取数约束的依据）。"""
        return self.method == "GET"

    @model_validator(mode="after")
    def _validate(self) -> "HttpBinding":
        if not self.path.startswith("/"):
            raise ValueError(f"HttpBinding.path={self.path!r} 必须以 '/' 开头")
        if not (0 < self.timeout_seconds <= 600):
            raise ValueError(
                f"HttpBinding.timeout_seconds={self.timeout_seconds} 必须在 (0, 600]"
            )
        return self

    def outcome_is_success(self, outcome: str) -> bool:
        """成功结果判定：任意 2xx（已定，第 12 节第 5 项）。"""
        return bool(_HTTP_OUTCOME_PATTERN.match(outcome)) and outcome.startswith("2")

    def outcome_is_valid(self, outcome: str) -> bool:
        """结果键合法性由 binding 判定（http：三位数字，1xx–5xx 语义段）。"""
        return bool(_HTTP_OUTCOME_PATTERN.match(outcome)) and outcome[0] in "12345"


Binding = Annotated[Union[HttpBinding], Field(discriminator="protocol")]


class RequestSpec(BaseModel):
    """请求声明树（body_type 已移入 binding）。

    声明树纪律（模板态 path、兄弟命名唯一等）沿用 ``_check_declarations``
    ——与旧栈同一实现，单一来源（io_spec）。
    """

    model_config = ConfigDict(extra="forbid")

    declarations: list[DeclarationEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_tree(self) -> "RequestSpec":
        # owner 仅用于报错定位;模型层无 id 上下文,给稳定占位
        _check_declarations(self.declarations, owner="request")
        return self


class ResponseSpec(BaseModel):
    """响应声明树。

    N1（已定）：outcome 即 ``EndpointSpec.responses`` 的键，本模型**不双写**
    outcome 字段——键为唯一真源；``spec_path`` 锚点的 ``@outcome`` 段与
    C 类规则均读键。不设 term 字段（第 12 节第 4 项，业务结果语义走
    Statement）。
    """

    model_config = ConfigDict(extra="forbid")

    description: str = ""
    declarations: list[DeclarationEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_tree(self) -> "ResponseSpec":
        _check_declarations(self.declarations, owner="response")
        return self


class EndpointSpec(BaseModel):
    """被测系统的一个接口契约（修订版，取代 schema/endpoint/endpoint.py）。

    相对旧版的变更（6.2，全部已定）：
        - ``api: ApiSpec`` → ``binding: Binding``（service 移出坐标，只在外壳）；
        - ``responses: dict[int, ResponseSpec]`` → ``dict[str, ResponseSpec]``
          （键 = outcome；http 为三位数字字符串）；
        - 删除 ``version`` / ``updated_at``（8n：版本归 release，历史归 git）；
        - 新增 ``capability``（cap 类 Term id）与 ``consumes`` / ``produces``
          （生产 / 消费语义的词条引用，与 MIME 无关——存量 ApiSpec 同名
          MIME 字段弃置不迁移）。
    """

    model_config = ConfigDict(extra="forbid")

    # ── 唯一标识与外壳 ──
    id: str
    system: str
    service: str
    name: str
    description: str = ""

    # ── 语义锚点（词条引用；按需建立，是否必填由交付件清单按版本决定）──
    capability: str | None = None
    consumes: list[str] = Field(default_factory=list)
    produces: list[str] = Field(default_factory=list)

    # ── 协议坐标 ──
    binding: Binding

    # ── 输入输出形态 ──
    request: RequestSpec | None = None
    responses: dict[str, ResponseSpec] = Field(default_factory=dict)

    # ── 取数视图与业务元信息（复用存量模型）──
    query_views: list[QueryView] | None = None
    metadata: EndpointMetadata = Field(default_factory=EndpointMetadata)

    @model_validator(mode="after")
    def _validate_integrity(self) -> "EndpointSpec":
        if not self.id or not _ID_PATTERN.match(self.id):
            raise ValueError(
                f"EndpointSpec.id={self.id!r} 不合法(需匹配 ^[a-z][a-z0-9_.\\-]{{1,63}}$)"
            )
        if not self.system or not self.service or not self.name:
            raise ValueError("EndpointSpec.system / service / name 不可为空")
        # id 以 system 为前缀（沿用既有契约：拿到 id 即可反查归属系统）
        if not self.id.startswith(f"{self.system}."):
            raise ValueError(
                f"EndpointSpec.id={self.id!r} 必须以 system 字段 "
                f"'{self.system}' 作为 prefix"
            )
        # 结果键合法性 + 至少一个成功结果（http：任意 2xx）
        for outcome in self.responses:
            if not self.binding.outcome_is_valid(outcome):
                raise ValueError(
                    f"EndpointSpec {self.id}: 非法结果键 {outcome!r}"
                    f"（合法性由 binding 判定）"
                )
        if self.responses and not any(
            self.binding.outcome_is_success(o) for o in self.responses
        ):
            raise ValueError(
                f"EndpointSpec {self.id}: responses 须至少声明一个成功结果"
                f"（http：任意 2xx）"
            )
        # body_type=none ⇒ 零请求声明
        if (
            self.binding.body_type == "none"
            and self.request is not None
            and self.request.declarations
        ):
            raise ValueError(
                f"EndpointSpec {self.id}: binding.body_type=none 不得带请求声明"
            )
        # 非 side_effect_free 挂 query_views 须显式 query_safe（护栏沿用 §3.3④）
        if self.query_views:
            if not self.binding.side_effect_free() and not self.metadata.query_safe:
                raise ValueError(
                    f"EndpointSpec {self.id}: 有副作用的 binding"
                    f"（{self.binding.method}）挂 query_views 须显式"
                    f" metadata.query_safe=True"
                )
            for v in self.query_views:
                _, missing = resolve_view_params(self, v)
                missing = [k for k in missing if k not in (v.query_params or [])]
                if missing:
                    raise ValueError(
                        f"EndpointSpec {self.id} view {v.name!r}: 必填键经 "
                        f"view.params▸default▸example 合并后仍缺 {missing}"
                    )
        return self


class Frontmatter(BaseModel):
    """交付物文件头（6.1）。文件即交付物；id 缺省取路径（8w：一旦被引用
    须显式写出）。"""

    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    type: str
    system: str | None = None  # 缺省按目录推断
    # 公共默认值供文件内接口块继承（继承在解析期物化进对象——内容寻址
    # 对象自含，P7）
    service: str | None = None


class Statement(BaseModel):
    """片段（6.3）：kind 锁「说的是哪一类事」，槽位中的词条锁「说的是哪个东西」。

    ``text`` = 块后紧跟的段落，解析时派生、不写入块内；``anchor`` 按交付物
    类型的锚点语法解析（语法表与 S 类校验全量在批次 B）。
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal[
        "mention", "define", "rule", "outcome", "transition", "step", "note"
    ]
    slots: dict[str, Union[str, int, list[str]]] = Field(default_factory=dict)
    anchor: str = ""
    text: str = ""  # 原文：解析时由块后段落派生，不写入块内（渲染时散文节点承载）


class Term(BaseModel):
    """词条（6.4）：概念身份。kind 五类由 id 前缀解析（entity/attr/value/
    cap/outcome），固定深度，父节点由 id 推导——id 规则校验在加载期
    （批次 B 的 T 类规则），模型内不重复。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str  # 业务名称：词表、展示、RAG 前缀
    aliases: list[str] = Field(default_factory=list)
    gloss: str = ""
    status: Literal["active", "deprecated"] = "active"
    replaced_by: str | None = None
    refers: str | None = None  # 仅 attr → attr（外键 → 主键），T6
