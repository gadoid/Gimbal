# spec 模块(`Plate/spec.py`)

> 本文档详细描述 `Plate/spec.py` 中的**每一个公开/内部类、Protocol、函数、
> 方法、模块级常量**,以及"为什么这么设计"。读者在阅读完本文档后,应能完整
> 解释该模块的所有行为细节与设计动机。

---

## 1. 模块定位

`spec.py` 是 Plate 子系统的**契约模型本体**。它定义了:

1. `EndpointSpec` — 单个端点的完整描述(数据为主、hook 为辅)。
2. `EndpointCategory` — 业务角色分类的枚举。
3. 三个 `runtime_checkable Protocol` — 能力扩展点(MockHook / ValidateHook /
   BuildRequestHook),本期不实装但签名本期定。
4. 契约保真护栏的内部实现 — `_assert_safe_model` / `_FORBIDDEN_CONFIG_KEYS` /
   `_is_basemodel_subclass` / `_get_model_config`。

它是所有 service 子包(Plate.fin、Plate.未来xxx...)**唯一**需要 import 的
核心数据类。任何"端点描述"必须以 `EndpointSpec` 为载体。

---

## 2. 模块文档字符串(开发者注释原文翻译)

```text
EndpointSpec 与 hook Protocol 定义。

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
```

---

## 3. 依赖关系

```python
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
```

**为什么这么依赖:**
- `dataclasses.dataclass` / `field` — 构造 `EndpointSpec`,`field(default_factory=...)`
  用于可变默认值(dict / list)。
- `enum.Enum` — 定义 `EndpointCategory`。
- `typing.Protocol` / `final` / `runtime_checkable` — 构造三个 hook 协议
  + 给 `EndpointSpec` 加 `@final` 防继承。
- `pydantic.BaseModel` — 类型标注 + `_is_basemodel_subclass` 内部校验。
- `Plate.binding.FieldBinding` + `_KNOWN_TRANSFORMS` — bindings 字段类型
  + transform 白名单。
- `Plate.serialization._hook_ref` / `_model_ref` / `_sorted_responses` /
  `_sorted_response_union` — `to_dict` 把 Pydantic 类 / hook 实例转成
  `"module.ClassName"` 字符串(序列化需要)。

**重要的反向依赖约束:**
- `spec.py` **不** import `facade` / `server` / `api_doc` / 任何 service
  子包。
- `spec.py` 不依赖 `core` — `core` 反过来 import `spec`(`EndpointKey`
  需要 `EndpointSpec` 做 type hint)。这是**单向依赖**: spec 是数据
  描述层,core 是注册中心层;core 依赖 spec 是合理的(它需要"知道 spec
  是什么")。

---

## 4. 公开类型:`EndpointCategory`

```python
class EndpointCategory(str, Enum):
    """接口在业务体系中的角色分类。给人 / AI 理解和决策用,不构成强约束。

    对应设计:PLATE_DESIGN.md §2.1
    选择 ``str, Enum`` 是为了让 category 可序列化(JSON / YAML),
    与外部系统(MCP / API doc)互通。
    """

    BUSINESS = "business"   # 主业务流程接口(有业务意义的状态变更)
    QUERY = "query"         # 查询接口(返回具体业务实体数据,无业务状态变更)
    TOOL = "tool"           # 工具型接口(系统级能力,与具体业务实体无关)
```

**三个值的语义:**
- `BUSINESS = "business"` — 主业务流程接口。下单、改票、确认收款等"动
  业务状态"的接口。
- `QUERY = "query"` — 查询接口。返回数据但不修改业务状态。分页查询、
  详情查询、列表查询都属此类。
- `TOOL = "tool"` — 工具型接口。系统级能力,与具体业务实体无关(目前
  fin 服务里没有 TOOL 类型的端点;后续接入底层 SDK / 通用能力时会用到)。

**为什么 `str, Enum`(双继承):**
- `Enum` 成员是单例,可在 `==` / `is` 比较中保证一致。
- `str` 继承让 `category.value` / `str(category)` / JSON 序列化都能直
  接用字符串值,无需自定义 `__str__`。
- 序列化时 `json.dumps(category)` 走 `str` 的序列化路径,产出 `"business"`
  而不是 `{"BUSINESS": "business"}` 的 enum 反射结构。

**"不构成强约束"** — 意思是 category 是**业务标签**,不是访问控制。
- 一个标注为 BUSINESS 的端点,**仍然**可以被任何 scenario 调用。
- category 真正的硬约束只有一条:`QUERY/TOOL` 必须 `mutates_state=False`
  (防止 CT 主动探活触发业务写入,见 `__post_init__` 章节)。

---

## 5. 三个 Hook Protocol(本期不实装,签名本期定)

### 5.1 `MockHook`

```python
@runtime_checkable
class MockHook(Protocol):
    """被 mock 响应生成时调用,产出完整 response body dict。

    返回 ``None`` = 走通用 mock 逻辑(用 spec.responses[status] + Field(examples=) 填字段)。
    返回 ``dict`` = 用该 dict 作为响应 body,跳过通用填充。
    """

    def __call__(self, spec: "EndpointSpec", request_payload: dict) -> dict | None: ...
```

**语义:**
- 入参:`spec` (被 mock 的端点 spec) + `request_payload` (调用方发来的
  请求体 dict)。
- 返回值:
  - `None` — 走通用 mock 逻辑:用 `spec.responses[200]` 对应的 Pydantic
    模型 + `Field(examples=...)` 填字段。
  - `dict` — 用该 dict 作为响应 body,跳过通用填充(给"按业务规则生成
    响应"的 hook 留口)。

**为什么用 Protocol 而不是 ABC:** Protocol 是"鸭子类型"约束,不需要
显式继承。mock 服务的作者可以直接 `def my_hook(spec, request_payload):
...`,无需 `class MyHook(MockHook)`。`@runtime_checkable` 让 `isinstance(
obj, MockHook)` 检查成为可能,让"在 spec 里挂一个 hook 引用"成为可校
验的契约。

### 5.2 `ValidateHook`

```python
@runtime_checkable
class ValidateHook(Protocol):
    """被 response 校验时调用,在 extra=forbid 之后、断言策略之前。

    hook 内 raise 即视为该次响应校验失败。
    """

    def __call__(
        self, spec: "EndpointSpec", response_payload: dict, status: int
    ) -> None: ...
```

**语义:**
- 入参:`spec` + `response_payload` (从真实服务 / mock 拿到的响应 body
  dict) + `status` (HTTP 状态码)。
- 返回值:`None`(校验通过)或 raise 异常(校验失败)。

**调用时机:** 在 Pydantic `model_validate`(即 `extra=forbid` 检查)之
**后**、断言策略之**前**。这个时机的含义:hook 看到的是"已经被契约
schema 验证过结构"的 payload,可以在此基础上做"业务级断言"(如"订单
状态必须是已支付才能返回 success")。

### 5.3 `BuildRequestHook`

```python
@runtime_checkable
class BuildRequestHook(Protocol):
    """被请求构建时调用,在 model_validate 之后、httpx 发出之前。

    返回值替换原 body dict,让 hook 可以做"按系统特异规则"重组 body。
    """

    def __call__(self, spec: "EndpointSpec", values: dict) -> dict: ...
```

**语义:**
- 入参:`spec` + `values` (Pydantic `model_validate` 之后、dump 之前的
  字段值 dict)。
- 返回值:替换原 body 的新 dict(让 hook 可以做"按系统特异规则"重组
  body — 例如某些接口要按"客户类型"重新排列字段顺序,或注入签名头)。

**为什么 hook 返回 `dict` 而不是 `None`:** 让 hook 明确表态"我已经
处理过这个 body";调用方不需要"hook 是否改过"的判断逻辑。

### 5.4 三个 Protocol 的共同设计

**为什么本期不实装但签名本期定:**
- 实装依赖 mock server / client 的更多设计;但**接口契约**可以先稳定
  下来,让"挂 hook"成为 spec 字段,而非后期再加。
- 本期 `EndpointSpec.mock_hook` / `validate_hook` / `build_request_hook`
  三个字段都默认 `None`,等真要实装时无需改 spec 数据形状(向后兼容)。

**为什么用 `runtime_checkable`:**
- `runtime_checkable` 让 `isinstance(obj, MockHook)` 在运行时可用。
- 业务代码可以"防御性判断":`if isinstance(spec.mock_hook, MockHook):
  ...`,无需 try/except AttributeError。

---

## 6. 契约保真禁用清单

```python
_FORBIDDEN_CONFIG_KEYS: tuple[tuple[str, str], ...] = (
    ("str_strip_whitespace", "会把 ' abc ' 改成 'abc',破坏 wire 格式"),
    ("coerce_numbers_to_str", "会在 55 / '55' 之间互转,影响类型判断"),
    ("use_enum_values", "会把 Enum 实例替换为字面值,改变 wire 表示"),
)
```

**字段含义:**
- 这是一个 `(key, reason)` 元组列表,每个 key 是 Pydantic `model_config`
  中**必须关闭**的字段,reason 是"为什么必须关闭"的人类可读解释。
- 在 `_assert_safe_model` 中被遍历检查。

**为什么禁用这三个:**
- `str_strip_whitespace=True` — 会让 `" abc "` 被悄悄改成 `"abc"`,破坏
  wire 格式。契约测试里这种"被悄悄改"的字段是**最致命的漂移源**。
- `coerce_numbers_to_str=True` — 会让 `55` 变 `"55"` 或反向,影响类型
  判断。Wire 里 `"id": 55` 和 `"id": "55"` 语义可能完全不同(尤其在
  弱类型后端里)。
- `use_enum_values=True` — 会让 `Enum` 实例在序列化时变成字面值。如果
  wire 里期望的是 `"status": "PAID"` 字面值,这是好事;但如果后端用
  `Enum` 做 wire 区分(少见但存在),就破坏了保真。

**为什么"双向都生效"** — 在 `__post_init__` 里 `request` 和 `response`
都会跑同一个禁用清单检查。`str_strip_whitespace` 不区分方向 — 任何
"被悄悄改"的字段都会破坏 wire 字节。

---

## 7. 核心数据类:`EndpointSpec`

### 7.1 类装饰与声明

```python
@final
@dataclass(frozen=True)
class EndpointSpec:
    """单个 endpoint 的契约描述。数据为主、hook 为辅,默认走通用行为。"""
```

**为什么 `@final`:**
- `core._collect_locked` 用 `type(attr).__name__ == "EndpointSpec"` 匹
  配,需要保证"所有叫 EndpointSpec 的对象都是这一个类" — 不允许继承
  链污染(否则 `__name__` 匹配会拿到继承类的实例)。
- `@final` 在 `typing.final` 装饰器层面禁止继承,违反会报 `TypeError`
  (在静态检查器里) 或在运行时由 `final` 装饰器拦截(取决于是否启用了
  `__init_subclass__` 检查)。

**为什么 `@dataclass(frozen=True)`:**
- 自动生成 `__init__` / `__repr__` / `__eq__`,省样板。
- `frozen=True` 让实例不可变,等价于"namedtuple + dict 的混合":
  - 不可变 → 可哈希 → 可作 `dict` key。
  - 不可变 → 锁内取出后到锁外用安全(无 TOCTOU 风险,见 `core.md` 5.5 节)。
  - 不可变 → 多线程读无锁冲突。

### 7.2 字段分组详解

#### 7.2.1 数据(必填)

```python
method: str
path: str
```

- `method: str` — HTTP 方法(如 `"POST"`)。不强制大写,由调用方保证。
- `path: str` — 端点路径(如 `"/api/order/order/orderDetail"`)。**必填**,
  空字符串会在 `__post_init__` 里 raise。

**为什么必填:** 这两个字段组成 `EndpointKey` 的 `method` 和 `path`
部分,缺失了 registry 索引就缺一不可。

#### 7.2.2 分类(PR-B 新增)

```python
category: EndpointCategory = EndpointCategory.BUSINESS
mutates_state: bool = True
```

- `category` — 默认 `BUSINESS`(向后兼容:旧 spec 没显式写 category
  也视为业务接口)。
- `mutates_state` — 默认 `True`(与 `BUSINESS` 默认对齐)。

**这两个字段的强校验在 `__post_init__` 章节详述。**

#### 7.2.3 跨端点依赖(PR-D2 新增)

```python
bindings: tuple[FieldBinding, ...] = ()
```

- 默认空 tuple。
- `tuple` 而非 `list` — frozen 兼容。
- 校验:见 `__post_init__` 章节。

详见 `binding.md`。

#### 7.2.4 数据(可选)

```python
request: type[BaseModel] | None = None
responses: dict[int, type[BaseModel]] = field(default_factory=dict)
response_data_models: dict[int, type[BaseModel]] = field(default_factory=dict)
```

- `request` — 请求体 Pydantic 模型,GET 类允许 `None`(无 body)。必
  须是 `BaseModel` 的**子类**(`type[BaseModel]`),不是实例。
- `responses` — `{状态码: 响应壳 Pydantic 模型}`。key 必须是 `int`。
  允许空 dict(GET 类 204 No Content 等场景)。
- `response_data_models` — `{状态码: 响应壳内部 data 字段的精细化
  Pydantic 模型}`。本字段是 D7 新增 — 见 `__post_init__` 章节。

**为什么用 `field(default_factory=dict)` 而不是 `field(default=
{})`:** `default={}` 是"可变默认值陷阱" — 多个实例会共享同一份 dict。
`default_factory` 每次构造新实例时调用,产出新 dict。

#### 7.2.5 文档元数据

```python
summary: str = ""
description: str = ""
tags: list[str] = field(default_factory=list)
auth_required: bool = False
```

- `summary` — 一句话用途(≤ 120 字符;`EndpointDoc` 强校,本字段
  不强校)。喂 mock / AI skill 上下文查询。
- `description` — 详细描述(Markdown / 纯文本均可)。
- `tags` — 标签列表(如 `["order", "write"]`),用于搜索 / 分组。
- `auth_required` — 是否需要鉴权。仅文档用途,不影响调用方行为(调用
  方自己决定是否注入 token)。

#### 7.2.6 预留槽位(本期不实装)

```python
default_response: type[BaseModel] | None = None
response_union: dict[int, tuple[type[BaseModel], ...]] = field(default_factory=dict)
```

- `default_response` — 通用响应(用于"任何状态码"场景)。本期不用。
- `response_union` — `{状态码: 多个响应模型的元组}`(用于"该状态码下
  可能是多种 body 之一"场景,类似 TypeScript union type)。本期不用。

**为什么保留:** Phase 后续(实装 mock server)会用到;**预留字段不
破坏现有数据** — `frozen=True` 的 dataclass 加新字段在反序列化时只
要 `from_dict` 容错即可,旧 JSON 数据也能正常 load。

#### 7.2.7 能力 hook(本期不实装)

```python
mock_hook: MockHook | None = None
validate_hook: ValidateHook | None = None
build_request_hook: BuildRequestHook | None = None
```

- 三个 hook 字段。`None` = 走通用行为。详见 §5 三个 Protocol。

### 7.3 `__post_init__` — 构造期校验

`EndpointSpec` 的"强校验心脏"。按四个区块执行:

#### 7.3.1 区块 (a): 必填字段类型校验

```python
# method / path 必须是非空 str
if not isinstance(self.method, str) or not self.method:
    raise TypeError(...)
# path 必须是非空 str
if not isinstance(self.path, str) or not self.path:
    raise TypeError(...)
# request 必须是 BaseModel 子类或 None
if self.request is not None and not _is_basemodel_subclass(self.request):
    raise TypeError(...)
# responses 字典的 key 必须是 int, value 必须是 BaseModel 子类
for code, model in self.responses.items():
    if not isinstance(code, int):
        raise TypeError(...)
    if not _is_basemodel_subclass(model):
        raise TypeError(...)
# default_response 必须是 BaseModel 子类或 None
# response_union 字典的 key 必须是 int, value 必须是 (BaseModel 子类, ...) tuple
```

**为什么 `request` / `responses` / `default_response` 的 value 必须是
`type[BaseModel]`:** registry 收集的是"类对象",不是实例。`model_validate`
时调用方才会 `request(...)` 实例化。`type[...]` 类型标注强制这一点。

**为什么抛 `TypeError` 而不是 `ValueError`:** Python 惯例 — 类型错
(`isinstance` 失败)用 `TypeError`,值错(类型对但内容错)用 `ValueError`。

#### 7.3.2 区块 (b): category × mutates_state 交叉校验

```python
if self.category in (EndpointCategory.QUERY, EndpointCategory.TOOL):
    if self.mutates_state is not False:
        raise ValueError(
            f"EndpointSpec({self.path!r}): category={self.category.value} "
            f"必须 mutates_state=False(否则 CT 主动探测会触发业务写入)。"
            f"实际 mutates_state={self.mutates_state!r}。"
            f"对应设计:PLATE_DESIGN.md §3.2"
        )
```

**业务动机:**
> CT(契约保活)主动探测必须避免触发业务写入。category 是给消费者用的
> 分类标签,mutates_state 是给 category 背书的可验证事实。
> 允许 QUERY/TOOL 类携带 `mutates_state=True` = 探测脚本可能在生产意外
> 触发业务写入(真实事故风险),所以这里 fail-fast。

**为什么 `is False` 而不是 `not`:**

```text
用 ``is False`` 而非 ``not``,防 ``None`` 滑过:
  - ``not None`` 是 True,会让 None 被当成 "符合要求",留下静默不一致
  - ``None is False`` 是 False,会拒绝 None 强制作者显式表态
```

`mutates_state` 字段有默认值 `True`,但如果某个旧 spec 写成 `mutates_state=None`
(手工 dataclass 实例化),用 `not` 会让 `None` 滑过。`is False` 严格
要求"必须是 `False`"才放行,迫使作者显式表态。

**为什么只对 QUERY / TOOL 强校,BUSINESS 不强校:**
- `BUSINESS` 是默认 category,业务写入是定义;`mutates_state=True`
  是天然配合,无需校验。
- `QUERY / TOOL` 是"被动语义",`mutates_state=True` 会与"业务分类"冲
  突,需要作者明确"我就是要写,虽然语义上是查询"(很少见,如果有,业
  务应该用 BUSINESS)。

#### 7.3.3 区块 (c): 契约保真护栏

```python
if self.request is not None:
    _assert_safe_model(self.request, ..., role_kind="request")
for code, model in self.responses.items():
    _assert_safe_model(model, ..., role_kind="response")
if self.default_response is not None:
    _assert_safe_model(self.default_response, ..., role_kind="response")
for code, model in self.response_data_models.items():
    _assert_safe_model(model, ..., role_kind="data")
```

**调用 `_assert_safe_model`** — 详见 §8。

**为什么 response_data_models 用 `role_kind="data"` 而不是 `response`:** D7
语义 — `response_data_models` 描述的是"响应壳内部 `data` 字段的精细化
模型",它**不是** wire 响应壳(响应壳是 envelope,data 是 envelope 的一个
子字段)。`role_kind="data"` 允许 `extra in ('forbid', 'ignore')`,允许
"先建容器、后续按需补字段"的演进策略。

#### 7.3.4 区块 (d): bindings 校验

```python
if self.bindings:
    for i, b in enumerate(self.bindings):
        if not isinstance(b, FieldBinding):
            raise TypeError(...)
        if not b.to_path:
            raise ValueError(...)
        if b.transform is not None and b.transform not in _KNOWN_TRANSFORMS:
            raise ValueError(...)
```

详见 `binding.md`。**自环检查(本 binding 的 from_path 不能指向本
endpoint)留在 `test_invariants.py` 聚合** — 因为精确反向索引是 PR-D4
的事,本期不在 `__post_init__` 做。

### 7.4 `response_models() -> dict[int, type[BaseModel]]`

```python
def response_models(self) -> dict[int, type[BaseModel]]:
    """返回 ``{status: model}``,与 ``self.responses`` 同形(浅拷贝)。"""
    return dict(self.responses)
```

**用途:** mock server / contract check 工具的 introspection。
**为什么浅拷贝:** 防调用方误改 `responses` 字典(虽然 `frozen=True` 仍
允许改 `self.responses[key] = new_model`,浅拷贝可阻挡这种误改)。

### 7.5 `has_request() -> bool`

```python
def has_request(self) -> bool:
    return self.request is not None
```

**用途:** mock server 决定"是否要 dump request body"(GET 类没 body)。
**为什么不直接用 `bool(spec.request)`:** `bool(BaseModel_subclass)`
是 True,但 `bool(None)` 是 False,看似等价。但若有人误传一个
`BaseModel` 实例进来(而非类),`bool()` 也会 True,而 `is not None` 不
会 — 后者更严格。但实际场景不太会传错,所以本质是为了**可读性**。

### 7.6 `to_dict() -> dict` — 序列化

```python
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
```

**字段命名约定:**
- 后缀 `_ref` 表示"这是一个引用字符串,不是对象本身"(对应
  `serialization._model_ref` / `_hook_ref`)。
- `bindings` 列表里每个元素是 `FieldBinding.to_dict()` 后的 dict。
- `tags` 走 `sorted(...)` — 防 list 顺序漂移导致 byte-equal 失效。

**byte-equal 承诺:** PR-2.0 §2.3 文档化了这个保证(同 spec 多次
`to_dict` 产物一致),实现在于:
- `dict` key 顺序无关(`json.dumps(sort_keys=True)` 兜底)。
- `list` 顺序由显式 `sorted(...)` 抹平。
- `_sorted_responses` / `_sorted_response_union` 内置排序。

### 7.7 `from_dict(d: dict) -> "EndpointSpec"` — 反序列化

```python
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
```

**反序列化策略:**
- 必填字段 `method` / `path` / `category` / `mutates_state` 缺失 →
  `KeyError`。
- `category` 用 `EndpointCategory(d["category"])` 反枚举化;失败
  → `ValueError`。
- `bindings` 走 `FieldBinding.from_dict` 链式反序列化。
- 所有 `BaseModel` / hook 引用 — 本期**留 None**,由 PR-2.2 SDK 负责
  importlib 重建。

**为什么"严格不容错":** 序列化产物是契约。容错 = 接受坏契约 = 让
漂移悄悄发生。

**为什么本期反序列化不留 BaseModel 引用:** importlib 重建涉及"哪个
service 的哪个子模块"等知识,放在 SDK 层(PR-2.2)统一处理。本 PR
只负责"to_dict 不挂" + "from_dict 字段全 + 类型严"。

---

## 8. 内部辅助

### 8.1 `_is_basemodel_subclass(obj: Any) -> bool`

```python
def _is_basemodel_subclass(obj: Any) -> bool:
    """判断 obj 是不是 BaseModel 子类(type 且 issubclass)。"""
    return isinstance(obj, type) and issubclass(obj, BaseModel)
```

**为什么不用 `isinstance(obj, type) and issubclass(...)` 的其他写法:**
- `isinstance(obj, type)` — 必须先确认 `obj` 是个类(因为 `issubclass`
  对非类对象会抛 `TypeError`)。
- `issubclass(obj, BaseModel)` — 标准的"是不是子类"判定。

**为什么这个函数重要:** `request` / `responses` 等字段的类型是
`type[BaseModel] | None` — 业务代码可能传:
- ✅ `MyRequest`(Pydantic BaseModel 子类)
- ❌ `MyRequest()`(实例 — 业务代码笔误)
- ❌ `dict`(手写 dict — 业务代码"想偷懒")
- ❌ `None`(显式 None — 允许,代表"无 request body")

`isinstance(obj, type) and issubclass(obj, BaseModel)` 只对 ✅ 返 True,
其他全部 False。

### 8.2 `_get_model_config(cls: type[BaseModel]) -> Any`

```python
def _get_model_config(cls: type[BaseModel]) -> Any:
    """安全获取 Pydantic 模型的 model_config,容忍未声明的情况。"""
    return getattr(cls, "model_config", None)
```

**为什么需要"容忍未声明":** Pydantic 模型**默认不要求**声明
`model_config`(v2 是可选的)。`getattr` 设 default 为 `None` 让
`_assert_safe_model` 可以判断"未声明"。

### 8.3 `_assert_safe_model(cls, role, role_kind)` — 契约保真护栏主体

```python
def _assert_safe_model(
    cls: type[BaseModel],
    role: str,
    role_kind: str = "response",
) -> None:
    """契约保真护栏:model 必须不会改写 wire 格式。

    角色区分(PR-C / D6 + D7):
      * ``role_kind='request'``: 客户端→服务端,允许 ``extra in ('forbid', 'ignore')``
        但**必须显式声明** ``model_config``(不能用 pydantic 默认值)。
      * ``role_kind='response'``: 服务端→客户端的 wire 响应壳,必须 ``extra='forbid'``。
      * ``role_kind='data'``: 响应壳内部 data 字段的精细化建模(D7),允许
        ``extra in ('forbid', 'ignore')`` 但**必须显式声明** ``model_config``。

    检查项:
      1. 必须声明 ``model_config``
      2. extra 策略:request/data 允许 forbid/ignore,response 必须 forbid
      3. 禁用清单(``str_strip_whitespace`` / ``coerce_numbers_to_str`` /
         ``use_enum_values``)必须全部为 False / None(双向)

    任一项不符则抛 TypeError,信息含:原因 + 修复建议 + 文档引用。
    """
```

**算法步骤:**

1. **`role_kind` 校验**:必须是 `"request"` / `"response"` / `"data"`
   之一,否则 `ValueError`(防内部调用笔误)。
2. **cfg 校验**:必须声明 `model_config`,否则 `TypeError`(带修复
   建议 + 文档引用)。
3. **extra 策略校验**(按 role_kind 分支):
   - `response`:`extra != "forbid"` → 报错。
   - `request` / `data`:`extra not in ("forbid", "ignore")` → 报错。
4. **禁用清单校验**:遍历 `_FORBIDDEN_CONFIG_KEYS`,任何 key 的值
   truthy → 报错。

**为什么 `response` 必须 `extra="forbid"`:**
> 未知响应字段说明服务端改了 spec,必须 fail-fast 暴露。

**为什么 `request` 允许 `extra="ignore"`:**
> 真实 wire 中请求体常含未建模字段 + 字段类型漂移,强制 forbid 会把宽
> 容的客户端拒之门外。

**为什么 `data` 角色允许 `extra="ignore"`:**
> data 是服务端内部结构,非 wire 响应壳;常见 200+ 字段(ES 文档),
> 演进中用 ignore 表达"先建容器,后续按需补字段"。

**为什么"必须显式声明 model_config":**
> Pydantic v2 默认 `extra="ignore"`(宽容),如果 spec 不显式声明
> `model_config`,契约保真就**默认不通过**。强制显式声明是"逼作者想
> 一想"。

**为什么 `if val:` 而不是 `if val is True:`:**
- `str_strip_whitespace` 等 Pydantic 配置项的真值是 `bool`(允许
  `True` / `False`),但有的字段可能是 `None` / `"all"` 等扩展值。
- `if val:` 把"任何 truthy"都视作开启 — 更严格,符合"凡是可能改写
  wire 的都禁止"的精神。

---

## 9. 公开 API 一览

| 名称 | 类型 | 用途 |
|---|---|---|
| `EndpointSpec` | `@final @dataclass(frozen=True)` | 单个端点契约描述(数据为主) |
| `EndpointCategory` | `str, Enum` | 业务角色分类 |
| `FieldBinding` | (从 `Plate.binding` 导入) | 声明性字段绑定 |
| `MockHook` | `@runtime_checkable Protocol` | mock hook 协议 |
| `ValidateHook` | `@runtime_checkable Protocol` | 校验 hook 协议 |
| `BuildRequestHook` | `@runtime_checkable Protocol` | 请求构建 hook 协议 |

模块底部 `__all__`:

```python
__all__ = [
    "EndpointSpec",
    "EndpointCategory",
    "FieldBinding",
    "MockHook",
    "ValidateHook",
    "BuildRequestHook",
]
```

---

## 10. 调用方典型代码示例

```python
# 1. 构造一个简单 spec
from Plate.spec import EndpointSpec, EndpointCategory
from pydantic import BaseModel, ConfigDict

class MyReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str

class MyResp(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str

spec = EndpointSpec(
    method="POST",
    path="/api/x",
    request=MyReq,
    responses={200: MyResp},
)

# 2. 构造一个 QUERY(spec 自动校验 mutates_state=False)
spec = EndpointSpec(
    method="GET",
    path="/api/list",
    request=None,
    responses={200: MyResp},
    category=EndpointCategory.QUERY,
    # mutates_state 默认 True → __post_init__ 会 raise
)
# 修复:
spec = EndpointSpec(
    method="GET",
    path="/api/list",
    request=None,
    responses={200: MyResp},
    category=EndpointCategory.QUERY,
    mutates_state=False,  # 显式表态
)

# 3. 序列化
d = spec.to_dict()
import json
print(json.dumps(d, sort_keys=True))  # byte-equal

# 4. 反序列化
spec2 = EndpointSpec.from_dict(d)
assert spec2.method == spec.method
assert spec2.category == spec.category
# 注意:spec2.request / spec2.responses 是空的(BaseModel 引用留 None)
```

---

## 11. 不变量总结(本模块承诺的不变式)

1. **不可继承**:`@final` 装饰器禁止任何类继承 `EndpointSpec`。
2. **不可变**:`frozen=True` 让所有实例在构造后无法被修改(防 TOCTOU)。
3. **类型严格**:`__post_init__` 强校所有字段类型,业务代码无法绕过。
4. **角色正确**:`__post_init__` 强校 `category × mutates_state` 交叉一致。
5. **契约保真**:每个 Pydantic 模型都跑 `_assert_safe_model`,禁止 wire
   改写。
6. **byte-equal 序列化**:`to_dict` 产物排序无关,`from_dict` 严格容错。
7. **三 hook 协议可校验**:`@runtime_checkable` 让 `isinstance` 防御性
   检查成为可能。
