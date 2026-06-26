"""EndpointSpec 与 hook Protocol 定义。

设计要点(对应 v3 文档 §3.4/§3.5/§3.6 + PLATE_DESIGN §2.1/§3.2/§3.4):
  - EndpointSpec 是 ``@final`` + ``frozen=True`` 的 dataclass:
      * @final:不允许继承(拉式收集用 ``type(attr) is EndpointSpec`` 严格匹配)
      * frozen=True:实例不可变,锁内取出后到锁外用是安全的(无 TOCTOU 风险)
  - ``__post_init__`` 强校四件事:
      a. 必填字段类型(``request``/``responses`` 必须是 BaseModel 子类或 None)
      b. 契约保真护栏(role-aware,D6 + D7):
         - request 角色:``extra in ('forbid', 'ignore')``,必须显式表态(D6)
         - response 角色(``responses`` / ``default_response``):
           ``extra = 'forbid'``(契约保真硬约束,v3 §3.6;D6)
         - data 角色(``response_data_models``):``extra in ('forbid', 'ignore')``,
           必须显式表态(D7 —— data 是服务端内部结构,不是 wire 响应壳)
         - 禁用清单双向生效(``str_strip_whitespace`` 等 wire 改写不分方向)
      c. category × mutates_state 交叉校验
         (QUERY/TOOL ⇒ mutates_state is False,设计 §3.2 / §3.4(c))
      d. bindings 校验(PR-D2):元素必须 FieldBinding、to_path 非空、
         transform 在白名单内。自环检查留给 test_invariants.py 聚合(本 PR 不在
         ``__post_init__`` 做 —— 精确反向索引是 PR-D4 的事)
      e. 错误信息对作者友好(写明原因 + 修复建议)
  - 三个 ``runtime_checkable Protocol``(MockHook/ValidateHook/BuildRequestHook)
    本期不实装,签名本期定;实现 hook 的作者用 ``isinstance(spec.mock_hook, MockHook)``
    即可校验协议
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, final, runtime_checkable

from pydantic import BaseModel

from Plate.binding import FieldBinding, _KNOWN_TRANSFORMS
from Plate.serialization import (
    _hook_ref,
    _model_ref,
    _sorted_response_union,
    _sorted_responses,
)


# ════════════════════════════════════════════════════════════════════════════
# EndpointCategory — 接口分类(PR-B 新增,PLATE_DESIGN §2.1)
# ════════════════════════════════════════════════════════════════════════════


class EndpointCategory(str, Enum):
    """接口在业务体系中的角色分类。给人 / AI 理解和决策用,不构成强约束。

    对应设计:PLATE_DESIGN.md §2.1
    选择 ``str, Enum`` 是为了让 category 可序列化(JSON / YAML),
    与外部系统(MCP / API doc)互通。
    """

    BUSINESS = "business"   # 主业务流程接口(有业务意义的状态变更)
    QUERY = "query"         # 查询接口(返回具体业务实体数据,无业务状态变更)
    TOOL = "tool"           # 工具型接口(系统级能力,与具体业务实体无关)


# ════════════════════════════════════════════════════════════════════════════
# 三个 hook Protocol(本期不实装,签名本期定 —— v3 §3.7)
# ════════════════════════════════════════════════════════════════════════════

@runtime_checkable
class MockHook(Protocol):
    """被 mock 响应生成时调用,产出完整 response body dict。

    返回 ``None`` = 走通用 mock 逻辑(用 spec.responses[status] + Field(examples=) 填字段)。
    返回 ``dict`` = 用该 dict 作为响应 body,跳过通用填充。
    """

    def __call__(self, spec: "EndpointSpec", request_payload: dict) -> dict | None: ...


@runtime_checkable
class ValidateHook(Protocol):
    """被 response 校验时调用,在 extra=forbid 之后、断言策略之前。

    hook 内 raise 即视为该次响应校验失败。
    """

    def __call__(
        self, spec: "EndpointSpec", response_payload: dict, status: int
    ) -> None: ...


@runtime_checkable
class BuildRequestHook(Protocol):
    """被请求构建时调用,在 model_validate 之后、httpx 发出之前。

    返回值替换原 body dict,让 hook 可以做"按系统特异规则"重组 body。
    """

    def __call__(self, spec: "EndpointSpec", values: dict) -> dict: ...


# ════════════════════════════════════════════════════════════════════════════
# 契约保真禁用清单(v3 §5.4)
# ════════════════════════════════════════════════════════════════════════════

# 这些 Pydantic 选项会改写 wire 格式,契约模型必须全部关闭。
# _assert_safe_model 在 spec 注册期逐一检查。
_FORBIDDEN_CONFIG_KEYS: tuple[tuple[str, str], ...] = (
    ("str_strip_whitespace", "会把 ' abc ' 改成 'abc',破坏 wire 格式"),
    ("coerce_numbers_to_str", "会在 55 / '55' 之间互转,影响类型判断"),
    ("use_enum_values", "会把 Enum 实例替换为字面值,改变 wire 表示"),
)


# ════════════════════════════════════════════════════════════════════════════
# EndpointSpec 主体
# ════════════════════════════════════════════════════════════════════════════

@final
@dataclass(frozen=True)
class EndpointSpec:
    """单个 endpoint 的契约描述。数据为主、hook 为辅,默认走通用行为。

    字段分组:
      数据(必填):method / path
      分类(PR-B 新增):category / mutates_state
      数据(可空):request(GET 类允许 None) / responses(允许空 dict)
      文档元数据(喂 mock / 后期 OpenAPI 导出):summary / description / tags / auth_required
      预留槽位(本期不实装,Optional=None,后期启用零破坏):
        default_response / response_union
      能力 hook(本期不实装,None = 走通用行为):mock_hook / validate_hook / build_request_hook
    """

    # —— 数据(必填)——
    method: str
    path: str

    # —— 分类(PR-B 新增,PLATE_DESIGN §2.1 + §3.2)——
    category: EndpointCategory = EndpointCategory.BUSINESS
    mutates_state: bool = True

    # —— 跨端点依赖(PR-D2 新增,PLATE_DESIGN §2.2 + §3.5)——
    bindings: tuple[FieldBinding, ...] = ()

    # —— 数据(可选)——
    request: type[BaseModel] | None = None
    responses: dict[int, type[BaseModel]] = field(default_factory=dict)
    # response_data_models: data 内部模型(可深入校验 envelope.data 内部)
    # 角色语义:D7(data 角色 — 允许 extra=ignore,详见 _assert_safe_model 注释)
    response_data_models: dict[int, type[BaseModel]] = field(default_factory=dict)

    # —— 文档元数据 ——
    summary: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    auth_required: bool = False

    # —— 预留槽位(本期不实装)——
    default_response: type[BaseModel] | None = None
    response_union: dict[int, tuple[type[BaseModel], ...]] = field(default_factory=dict)

    # —— 能力 hook(本期不实装,None = 走通用行为)——
    mock_hook: MockHook | None = None
    validate_hook: ValidateHook | None = None
    build_request_hook: BuildRequestHook | None = None

    def __post_init__(self) -> None:
        # (a) 必填字段类型校验
        if not isinstance(self.method, str) or not self.method:
            raise TypeError(
                f"EndpointSpec({self.path!r}): method 必须是非空字符串,实际 "
                f"{type(self.method).__name__}: {self.method!r}"
            )
        if not isinstance(self.path, str) or not self.path:
            raise TypeError(
                f"EndpointSpec: path 必须是字符串(必填),实际 {type(self.path).__name__}: {self.path!r}"
            )
        if self.request is not None and not _is_basemodel_subclass(self.request):
            raise TypeError(
                f"EndpointSpec({self.path}): request 必须是 BaseModel 子类或 None,"
                f"实际 {self.request!r}"
            )
        for code, model in self.responses.items():
            if not isinstance(code, int):
                raise TypeError(
                    f"EndpointSpec({self.path}): responses 的 key 必须是 int 状态码,"
                    f"实际 {type(code).__name__}: {code!r}"
                )
            if not _is_basemodel_subclass(model):
                raise TypeError(
                    f"EndpointSpec({self.path}): responses[{code}] 必须是 BaseModel 子类,"
                    f"实际 {model!r}"
                )
        if self.default_response is not None and not _is_basemodel_subclass(self.default_response):
            raise TypeError(
                f"EndpointSpec({self.path}): default_response 必须是 BaseModel 子类或 None,"
                f"实际 {self.default_response!r}"
            )
        for code, models in self.response_union.items():
            if not isinstance(code, int):
                raise TypeError(
                    f"EndpointSpec({self.path}): response_union 的 key 必须是 int 状态码"
                )
            if not isinstance(models, tuple) or not all(_is_basemodel_subclass(m) for m in models):
                raise TypeError(
                    f"EndpointSpec({self.path}): response_union[{code}] 必须是 "
                    f"(BaseModel 子类, ...) 元组,实际 {models!r}"
                )

        # (b) category × mutates_state 交叉校验(PR-B / PLATE_DESIGN §3.2 + §3.4(c))
        #
        # 业务动机:CT(契约保活)主动探测必须避免触发业务写入。
        # category 是给消费者用的分类标签,mutates_state 是给 category 背书的可验证事实。
        # 允许 QUERY/TOOL 类携带 mutates_state=True = 探测脚本可能在生产意外触发
        # 业务写入(真实事故风险),所以这里 fail-fast。
        #
        # 用 ``is False`` 而非 ``not``,防 ``None`` 滑过:
        #   - ``not None`` 是 True,会让 None 被当成 "符合要求",留下静默不一致
        #   - ``None is False`` 是 False,会拒绝 None 强制作者显式表态
        if self.category in (EndpointCategory.QUERY, EndpointCategory.TOOL):
            if self.mutates_state is not False:
                raise ValueError(
                    f"EndpointSpec({self.path!r}): category={self.category.value} "
                    f"必须 mutates_state=False(否则 CT 主动探测会触发业务写入)。"
                    f"实际 mutates_state={self.mutates_state!r}。"
                    f"对应设计:PLATE_DESIGN.md §3.2"
                )

        # (c) 契约保真护栏(v3 §3.6 + D6 role-aware)
        if self.request is not None:
            _assert_safe_model(
                self.request, f"EndpointSpec({self.path}).request", role_kind="request"
            )
        for code, model in self.responses.items():
            _assert_safe_model(
                model, f"EndpointSpec({self.path}).responses[{code}]", role_kind="response"
            )
        if self.default_response is not None:
            _assert_safe_model(
                self.default_response,
                f"EndpointSpec({self.path}).default_response",
                role_kind="response",
            )
        for code, model in self.response_data_models.items():
            # D7: data 角色 — 响应壳内部 data 字段的精细化建模,允许 extra=ignore
            # 业务理由:data 是服务端内部结构,非 wire 响应壳(D6);常见 200+ 字段
            # (OrderDetailData 204 字段的 ES 文档),演进中用 ignore 表达"先建容器,
            # 后续按需补字段"。
            _assert_safe_model(
                model,
                f"EndpointSpec({self.path}).response_data_models[{code}]",
                role_kind="data",
            )

        # (d) bindings 校验(PR-D2 / PLATE_DESIGN §2.2 + §3.5)
        # 业务理由:bindings 是 L1 字段,可被 review pipeline 静态校验;
        # 构造期 fail-fast 防"等到运行时才发现 binding 拼错"。
        # 自环检查(本 binding 的 from_path 不能指向本 endpoint)留给
        # test_invariants.py 聚合 —— 精确反向索引是 PR-D4 的事。
        if self.bindings:
            for i, b in enumerate(self.bindings):
                # 类型校验
                if not isinstance(b, FieldBinding):
                    raise TypeError(
                        f"EndpointSpec({self.path!r}): bindings[{i}] 不是 FieldBinding "
                        f"实例(类型={type(b).__name__})。"
                        f"对应设计:PLATE_DESIGN.md §2.2"
                    )
                # 路径校验:to_path 不为空(注入位置必须明确)
                if not b.to_path:
                    raise ValueError(
                        f"EndpointSpec({self.path!r}): bindings[{i}].to_path 不能为空 "
                        f"(注入目标必须明确,空 tuple 语义模糊,禁止)。"
                    )
                # transform 必须在白名单内(防拼写错误 + 让 review pipeline 可 grep)
                if b.transform is not None and b.transform not in _KNOWN_TRANSFORMS:
                    raise ValueError(
                        f"EndpointSpec({self.path!r}): bindings[{i}].transform="
                        f"{b.transform!r} 不在已知集合 {_KNOWN_TRANSFORMS} 中。"
                        f"修复:用 None / 'identity' / 已知 transform 之一。"
                    )

    # ── 文档与 introspection 辅助(供 mock/contract check 工具使用)──

    def response_models(self) -> dict[int, type[BaseModel]]:
        """返回 ``{status: model}``,与 ``self.responses`` 同形(浅拷贝)。"""
        return dict(self.responses)

    def has_request(self) -> bool:
        return self.request is not None

    # ── 序列化(PR-2.0 / PLATE_EVOLUTION §3)──
    #
    # 业务承诺:序列化产物 byte-equal(同 spec 多次序列化结果一致),
    # 排序无关字段(tags / responses / response_union)在序列化前先排序。
    # 反序列化"非 BaseModel 字段"严格还原;BaseModel 引用留 None —— 重建
    # 责任在 PR-2.2 SDK(importlib 按 module.ClassName 重建)。
    #
    # 不变量(from_dict(to_dict(x))):
    #   - method/path/category/mutates_state:严格还原
    #   - bindings:严格还原(tuple 顺序固定为 from_dict 输入顺序)
    #   - request/responses/default_response/response_data_models:None(本 PR 范围)
    #   - tags:list 顺序按 to_dict 排序后的顺序
    #   - summary/description/auth_required:严格还原

    def to_dict(self) -> dict:
        """序列化为 dict。byte-equal 保证见 PR-2.0 §2.3。"""
        return {
            "method": self.method,
            "path": self.path,
            "category": self.category.value,
            "mutates_state": self.mutates_state,
            "bindings": [b.to_dict() for b in self.bindings],
            "request_ref": _model_ref(self.request),
            "responses_ref": _sorted_responses(self.responses),
            "default_response_ref": _model_ref(self.default_response),
            "response_data_models_ref": _sorted_responses(self.response_data_models),
            "summary": self.summary,
            "description": self.description,
            "tags": sorted(self.tags),
            "auth_required": self.auth_required,
            "response_union_ref": _sorted_response_union(self.response_union),
            "mock_hook_ref": _hook_ref(self.mock_hook),
            "validate_hook_ref": _hook_ref(self.validate_hook),
            "build_request_hook_ref": _hook_ref(self.build_request_hook),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EndpointSpec":
        """从 dict 反序列化。严格不容错。

        本 PR 范围(BaseModel 引用留 None):
          - ``request`` / ``responses`` / ``default_response`` /
            ``response_data_models`` / ``response_union`` / hooks → None
          - PR-2.2 SDK 负责 importlib 重建

        Raises:
            TypeError: 必填字段缺失或类型错
            ValueError: bindings 元素非 FieldBinding / category 不在 enum / etc.
        """
        if not isinstance(d, dict):
            raise TypeError(
                f"EndpointSpec.from_dict: 期望 dict,实际 {type(d).__name__}"
            )
        # 必填字段
        for required in ("method", "path", "category", "mutates_state"):
            if required not in d:
                raise KeyError(
                    f"EndpointSpec.from_dict: 缺失字段 {required!r}"
                )

        # category 反序列化
        try:
            category = EndpointCategory(d["category"])
        except ValueError as e:
            raise ValueError(
                f"EndpointSpec.from_dict: category={d['category']!r} 不在 "
                f"EndpointCategory 内: {e}"
            ) from e

        # bindings 反序列化(走 FieldBinding.from_dict)
        bindings_list: list[FieldBinding] = []
        for b_dict in d.get("bindings", []):
            bindings_list.append(FieldBinding.from_dict(b_dict))

        return cls(
            method=d["method"],
            path=d["path"],
            category=category,
            mutates_state=bool(d["mutates_state"]),
            bindings=tuple(bindings_list),
            # BaseModel 引用本 PR 范围留 None
            request=None,
            responses={},
            default_response=None,
            response_data_models={},
            summary=str(d.get("summary", "")),
            description=str(d.get("description", "")),
            tags=list(d.get("tags", [])),
            auth_required=bool(d.get("auth_required", False)),
            response_union={},
            mock_hook=None,
            validate_hook=None,
            build_request_hook=None,
        )


# ════════════════════════════════════════════════════════════════════════════
# 内部辅助
# ════════════════════════════════════════════════════════════════════════════

def _is_basemodel_subclass(obj: Any) -> bool:
    """判断 obj 是不是 BaseModel 子类(type 且 issubclass)。"""
    return isinstance(obj, type) and issubclass(obj, BaseModel)


def _get_model_config(cls: type[BaseModel]) -> Any:
    """安全获取 Pydantic 模型的 model_config,容忍未声明的情况。"""
    return getattr(cls, "model_config", None)


def _assert_safe_model(
    cls: type[BaseModel],
    role: str,
    role_kind: str = "response",
) -> None:
    """契约保真护栏:model 必须不会改写 wire 格式。

    角色区分(PR-C / D6 + D7):
      * ``role_kind='request'``: 客户端→服务端,允许 ``extra in ('forbid', 'ignore')``
        但**必须显式声明** ``model_config``(不能用 pydantic 默认值)。
        业务理由:真实 wire 中请求体常含未建模字段 + 字段类型漂移,强制 forbid
        会把宽容的客户端拒之门外。**禁用清单**仍全部生效(str_strip_whitespace
        等 wire 改写是双向问题)。
      * ``role_kind='response'``: 服务端→客户端的 wire 响应壳,必须 ``extra='forbid'``。
        业务理由:未知响应字段说明服务端改了 spec,必须 fail-fast 暴露。
      * ``role_kind='data'``: 响应壳内部 data 字段的精细化建模(D7),允许
        ``extra in ('forbid', 'ignore')`` 但**必须显式声明** ``model_config``。
        业务理由:data 是**服务端内部结构**(作者明确知道有哪些字段),
        不同于 wire 响应壳 —— 不是\"服务端在 wire 加新字段\"的问题,而是
        \"作者在 data 里允许宽容表达\"的设计选择。真实场景中 ES 文档
        (OrderDetailData 204+ 字段)用 ``ignore`` 表达\"我先建容器,
        后续按需补字段\"的演进策略。**禁用清单**仍全部生效。

    检查项:
      1. 必须声明 ``model_config``
      2. extra 策略:request/data 允许 forbid/ignore,response 必须 forbid
      3. 禁用清单(``str_strip_whitespace`` / ``coerce_numbers_to_str`` /
         ``use_enum_values``)必须全部为 False / None(双向)

    任一项不符则抛 TypeError,信息含:原因 + 修复建议 + 文档引用。
    """
    if role_kind not in ("request", "response", "data"):
        raise ValueError(
            f"_assert_safe_model: role_kind 必须是 'request'/'response'/'data',"
            f"实际 {role_kind!r}"
        )

    cfg = _get_model_config(cls)
    if cfg is None:
        raise TypeError(
            f"{cls.__name__}.{role}: 缺少 model_config。"
            f"契约模型必须显式声明 model_config = ConfigDict(extra='forbid', ...)。"
            f"详见 docs/modules/contract.md §契约保真。"
        )

    # extra 策略:按 role_kind 区分(PR-C / D6 + D7)
    extra = cfg.get("extra") if hasattr(cfg, "get") else None
    if role_kind == "response":
        if extra != "forbid":
            raise TypeError(
                f"{cls.__name__}.{role}: model_config['extra'] 必须为 'forbid',"
                f"契约模型不允许默默吞掉未知字段(避免字段被静默删除)。"
                f"当前值: {extra!r}。修复:在 model_config 中加 extra='forbid'。"
            )
    else:  # request / data
        if extra not in ("forbid", "ignore"):
            raise TypeError(
                f"{cls.__name__}.{role}: model_config['extra'] 必须是 'forbid' 或 'ignore',"
                f"{role_kind} 角色允许宽容未知字段但必须显式表态(不可走 pydantic 默认值)。"
                f"当前值: {extra!r}。修复:在 model_config 中显式声明 extra='forbid' 或 'ignore'。"
            )

    # 禁用清单(双向都生效 — wire 改写不分方向)
    for forbidden_key, why in _FORBIDDEN_CONFIG_KEYS:
        val = cfg.get(forbidden_key) if hasattr(cfg, "get") else None
        if val:  # True / 非 None 都算开启
            raise TypeError(
                f"{cls.__name__}.{role}: model_config['{forbidden_key}'] 必须关闭。"
                f"原因:{why}。当前值: {val!r}。"
            )


__all__ = [
    "EndpointSpec",
    "EndpointCategory",
    "FieldBinding",
    "MockHook",
    "ValidateHook",
    "BuildRequestHook",
]
