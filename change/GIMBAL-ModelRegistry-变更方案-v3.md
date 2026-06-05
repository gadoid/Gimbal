# GIMBAL 变更方案 v3（Final）:引入 ModelRegistry,以数据类 + EndpointSpec 双场景复用替代裸字典请求

**状态**:设计定稿 · 待实现
**版本**:v3（在 v2 基础上整合多轮讨论最终修订;v1=PathRegistry 方案,v2=单 EndpointSpec 方案,v3=双场景复用方案)
**影响版本**:v1.0 RC（**对存量 scenario 零 breaking change**,见 §9 与 §4.1 的 `contract_validation.mode` 渐进开关)
**核心目标**:把"被测系统的接口长什么样"从散落在各 scenario 的裸 dict,沉淀为可执行、可校验、可导出、可 mock 的**契约规范**,服务于 PHP→Java 迁移的接口与数据一致性验证,并为后续 SpringDoc 式接口文档 / 调试 / mock 打底。

---

## 0. 相对 v2 的关键修订(先读这一节)

v2 的方向正确,但多个机制在讨论中被推翻或细化。下面是**设计层面**的修订,具体到代码的改动点见文末 §10。

| v2 的做法 | v3 的修订 | 原因 |
|---|---|---|
| 模块名 `PathRegistry` | 改名 `ModelRegistry` | 实际按 service 组织,不按 path 索引;名字应表达"模型仓库" |
| api **不感知** model,框架按 `(service, method, path)` 反查 | **保留**,但明确**两个消费者、两套用途** | scenario 加载反查后取数据类做 body 字段检查;mock 反查后取整个 EndpointSpec 做路由 |
| 每个 endpoint = `EndpointSpec` 实例 | **数据类 + EndpointSpec 实例**共存于同一文件 | 数据类服务 scenario 的字段检查;EndpointSpec 服务 mock 的路由/响应/hook。一个文件,两套复用,一份真源 |
| （曾讨论）`SERVICE` 常量 + ast 扫描 | 全部砍掉:**service 名 = 目录名 = import 路径**;不合法 Python 标识走 `_aliases.py` 集中表 | 装饰器/ast 带来 import 副作用与按需加载的耦合;约定 + 集中 alias 表把这些问题都消除 |
| 信封持 `values` 字段 | **沿用 `body`**,信封仍是 `{ kind, body, headers }` | `body → values` 重命名是不必要的破坏;沿用原名,无 breaking |
| 信封持 `model_ref` | **删除**:信封不感知 model | model 由反查得到,信封无需知道 model 存在 |
| scenario 加载器强调 `resolve()` | **保留**,但用 `contract_validation.mode` 三态开关平滑过渡 | 存量 scenario 大量 endpoint 还没建 spec,strict 模式一夜全红;warn 模式先打 warning,strict 是终态 |
| 拉式收集无并发保护 | 加 `threading.Lock` | framework 已有并发执行能力,registry 不该成为隐性单点 |
| `responses: dict[int, type[BaseModel]]` 单一形态 | 加 `default_response` / `response_union` 预留 Optional 字段 | 204/未注册状态码/union 类型后期启用零 breaking |
| hook 仅 `Callable` 类型注解 | 改为 `runtime_checkable Protocol`,签名本期就定 | `Callable` 没有上下文 API;Protocol 给出 spec.method / spec.path 等可访问字段,IDE 也能补全 |
| `contract check` 与 mock 启动代码重复 | 抽出共用 `warm()` 函数,两边都走 | 后期 mock 子系统实装时不重构 core.py |
| 启动期校验清单含 §8.2 path 交叉校验 | **删除**:scenario ↔ spec 解耦,不做双向交叉 | 缺失 spec 在 resolve 时自然 fail-fast;spec 覆盖率报告走 `contract check --coverage`,只报告不阻塞 |
| `round-trip` 自检在加载期跑 | 本期不实装,流程文档化 | 没 baseline;`contract check --roundtrip` 配合 `tests/contract_baselines/` 后期启用 |

v2 中**未变**的部分（仍然有效,本版完整保留）:§3 契约保真全部要求、模板兼容策略、§5 三层 ref/内容/契约 总纲的精神（虽然 v3 不再显式画三层图,但"复用层 → 内容层 → 契约层"的串行顺序在 §4.2 Phase 时序里落实）。

---

## 1. 背景与动机

当前 step 定义里,请求体是裸 `request.body` 字典。在 PHP→Java 迁移对账场景下有两个根本问题:

1. **没有契约**:字段类型、空值语义、字段集合全靠手写,加载期发现不了结构错误,也无法作为两端验收标准。
2. **接口与数据耦合**:同一接口在不同 scenario 重复手写,接口定义无法集中维护、无法当文档用。

变更的本质:**为被测系统建立一份"可运行的契约规范"**。PHP 端与 Java 端都必须满足它,GIMBAL 用它在加载期做结构校验、执行期做对账、后期生成文档与 mock。

v3 的关键新认知:**这份契约有两个消费者**——scenario 加载器（轻量,只取数据类做字段检查）与 mock server（重量,取整个 spec 做路由/响应/hook）。**一份真源、两套用途**是 v3 的总纲。

---

## 2. 总纲:双场景复用架构

```
┌─ ModelRegistry/<service>/<endpoint>.py ────────────────────┐
│                                                            │
│   class OrderAddRequest(BaseModel):    # 数据类            │
│       ...                                                      │
│                                                            │
│   class OrderAddResponse(BaseModel):   # 数据类            │
│       ...                                                      │
│                                                            │
│   ORDER_ADD = EndpointSpec(            # 实例(mock 用)      │
│       method="POST",                                       │
│       path="/api/order/orderEntrust/orderAdd",             │
│       request=OrderAddRequest,                            │
│       responses={200: OrderAddResponse},                  │
│       summary="...", tags=[...],                          │
│       mock_hook=None,                                      │
│   )                                                       │
│                                                            │
└────────────────────────────────────────────────────────────┘
                       │
                       │ registry.resolve(service, method, path)
                       ▼
        ┌─────────────────────────────┐
        │       EndpointSpec          │
        └─────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
  Scenario 加载器                Mock server
  (轻量消费者)                   (重量消费者)
        │                             │
  spec.request                  spec.method
    .model_validate(body)       spec.path
                                spec.responses[status]
                                spec.mock_hook(...)
```

- **数据类**用于 scenario 加载时对 body 做字段检查（Pydantic `model_validate`）
- **EndpointSpec 实例**用于 mock server 启动时做路由/响应/hook 装载
- **Registry 单一入口**:`registry.resolve(service, method, path) -> EndpointSpec`,两个消费者都走它,各取所需

**为什么是同一文件**:同源即同步。修改一处数据类的字段,EndpointSpec 引用的也是同一个 class 对象,Python 自动同步,不需要在两处维护。

---

## 3. ModelRegistry 模块设计

### 3.1 定位与目录结构

新建目录 `ModelRegistry`,集中存放被测系统所有接口的契约,按 service 组织。**约定:service 名 = 目录名 = import 路径**(若 service 名是合法 Python 标识符)。

```
ModelRegistry/
├── __init__.py            # 只 re-export registry 单例
├── core.py                # _Registry: collect / resolve / warm + threading.Lock
├── spec.py                # @final EndpointSpec + 三个 Protocol
├── _aliases.py            # service 名(可能含连字符)→ 合法 Python 目录名
├── settlement/            # 目录名 = 合法 Python service 名
│   ├── __init__.py
│   ├── order_add.py       # Request / Response 数据类 + ORDER_ADD = EndpointSpec(...)
│   └── order_page.py
└── order/
    └── order_detail.py
```

`ModelRegistry/__init__.py` 极简:

```python
from .core import registry  # 只 re-export 单例,不 import 任何子包
__all__ = ["registry"]
```

### 3.2 service 名规范与 alias 表

#### 3.2.1 主路径:合法 Python 标识

如果 service 名本身是合法 Python 标识符（字母数字下划线、不以数字开头、不是关键字）,**直接用**作为目录名。

#### 3.2.2 辅路径:集中 alias 表

当 service 名含连字符、点、数字开头等 Python 标识符不允许的字符时,走 `_aliases.py`:

```python
# ModelRegistry/_aliases.py
"""service 名 → 合法 Python 目录名 的反向映射。

本表是 service 命名不一致时的唯一兜底。任何 service 名变更,
先改这里(而不是改目录名 + 所有 scenario)。
"""
SERVICE_ALIASES: dict[str, str] = {
    "tidb-test-service": "tidb_test_service",  # 连字符 → 下划线
    # "3pl-service": "three_pl_service",       # 数字开头走 alias
    # "fin.tidb": "fin_tidb",                  # 含点走 alias
}

def resolve_dir_name(service: str) -> str:
    """解析 service 名 → 目录名。

    解析规则:
      1. 是合法 Python 标识符 → 直接用
      2. 在 SERVICE_ALIASES 中 → 用 alias
      3. 都不行 → fail-fast
    """
    if service.isidentifier() and not __import__("keyword").iskeyword(service):
        return service
    if service in SERVICE_ALIASES:
        return SERVICE_ALIASES[service]
    raise ValueError(
        f"[ModelRegistry] service 名 '{service}' 不符合 Python 包名规范,"
        f"也不在 SERVICE_ALIASES 中。请在 ModelRegistry/_aliases.py 添加映射后重试。"
    )
```

#### 3.2.3 维护成本

- **集中维护**:一个 dict,需要时加一行
- **集中式 vs 分散式**选择:集中式便于一次扫描所有别名,避免分散到各 subpackage 后还要遍历

### 3.3 Registry 核心(collect / resolve / warm + 线程安全)

```python
# ModelRegistry/core.py
import importlib
import threading
from dataclasses import dataclass

from ._aliases import resolve_dir_name
from .spec import EndpointSpec


@dataclass(frozen=True)
class EndpointKey:
    service: str
    method: str
    path: str


class _Registry:
    def __init__(self):
        self._index: dict[EndpointKey, EndpointSpec] = {}
        self._loaded: set[str] = set()
        self._lock = threading.Lock()  # 并发安全:framework 已有并发执行能力

    def _collect_locked(self, service: str) -> None:
        """内部方法:假设调用方已持锁。import service 包,拉式收集所有 EndpointSpec。"""
        if service in self._loaded:
            return
        pkg_name = resolve_dir_name(service)
        try:
            module = importlib.import_module(f"ModelRegistry.{pkg_name}")
        except ImportError as e:
            raise LookupError(
                f"[ModelRegistry] service '{service}' 对应的目录 "
                f"'ModelRegistry/{pkg_name}/' 不存在或导入失败: {e}"
            ) from e
        for attr in vars(module).values():
            # 严格 type 匹配,排除继承(EndpointSpec 是 @final)
            if type(attr) is EndpointSpec:
                key = EndpointKey(service, attr.method, attr.path)
                self._index[key] = attr
        self._loaded.add(service)

    def collect(self, service: str) -> None:
        """import 该 service 包,遍历命名空间,拉式收集所有 EndpointSpec 实例。幂等。"""
        with self._lock:
            self._collect_locked(service)

    def resolve(self, service: str, method: str, path: str) -> EndpointSpec:
        """按 (service, method, path) 拿 EndpointSpec。首次访问触发 collect。

        整个 collect + dict 读取都在同一把锁内:避免并发的 collect 修改 _index
        时,本线程在锁外迭代 _index 触发 RuntimeError("dictionary changed
        size during iteration")。EndpointSpec 是 frozen=True 的 dataclass,
        锁内取出后到锁外用是安全的(实例不可变,无 TOCTOU 风险)。
        """
        key = EndpointKey(service, method, path)
        with self._lock:
            self._collect_locked(service)
            if key not in self._index:
                registered = sorted(
                    f"  {k.method} {k.path}" for k in self._index if k.service == service
                )
                raise LookupError(
                    f"[ModelRegistry] 未找到 {service} {method} {path}。\n"
                    f"该 service 已注册端点:\n" + "\n".join(registered) +
                    (f"\n请在 ModelRegistry/{resolve_dir_name(service)}/ 下建对应 endpoint 文件,"
                     f"或修正 scenario 中 path 的拼写。")
                )
            return self._index[key]

    def warm(self, services: list[str]) -> list[EndpointSpec]:
        """共用的预热逻辑。contract check 与 mock server 都走这里。

        返回该批 service 收集到的全部 EndpointSpec 实例;
        收集过程中任一 service 失败,抛 BootstrapError 并附所有错误。
        """
        issues: list[str] = []
        collected_specs: list[EndpointSpec] = []
        with self._lock:
            # 整个 collect + 列表构造都在锁内,避免锁外迭代 _index 时
            # 被并发的 collect 触发 "dictionary changed size during iteration"
            for s in services:
                try:
                    self._collect_locked(s)
                except Exception as e:
                    issues.append(f"  - {s}: {e}")
            if issues:
                raise BootstrapError(
                    f"[ModelRegistry] 预热失败,以下 service 异常:\n" + "\n".join(issues)
                )
            for k, spec in self._index.items():
                if k.service in services:
                    collected_specs.append(spec)
        return collected_specs


class BootstrapError(RuntimeError):
    """warm() 失败时的聚合错误。"""


# 全局单例
registry = _Registry()
```

**要点**:

- **拉式收集 + 严格 `type(attr) is EndpointSpec` 匹配**:零 import 副作用,排除任何继承(`@final` 配合)。
- **线程安全**:`threading.Lock` 保护 `_index` / `_loaded` 的修改。**关键纪律**:`collect` 拆为内部 `_collect_locked`(假设已持锁)和公开 `collect`(自带取锁),`resolve` 和 `warm` 必须在**同一把锁内**完成 "collect + 迭代/读取 `_index`",否则并发的 `collect` 会让本线程在锁外迭代时触发 `RuntimeError: dictionary changed size during iteration`。EndpointSpec 是 `frozen=True` 的 dataclass,锁内取出后到锁外用是安全的(实例不可变,无 TOCTOU 风险)。
- **共用 `warm()`**:`contract check` 与 mock server 启动**都用这一入口**,避免代码重复;mock 子系统实现时无需重构 core。
- **首次访问触发 collect**:scenario 加载器和 mock 启动都"按需",未引用的 service 一个字节都不 import。

### 3.4 EndpointSpec 形态:数据类 + 实例共存

每个 endpoint 文件里有两类东西:

```python
# ModelRegistry/settlement/order_add.py
from pydantic import BaseModel, ConfigDict, Field
from ModelRegistry.spec import EndpointSpec

# === 数据类:scenario 加载器用 ===
class OrderAddRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    customer_id: str = Field("", description="客户ID", examples=["16"])
    service_id:  str = Field("", description="销售ID", examples=["55"])
    # ... 其余字段按 §5 真实线格式定

class OrderAddResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    # ...

# === EndpointSpec 实例:mock server 用 ===
ORDER_ADD = EndpointSpec(
    method="POST",
    path="/api/order/orderEntrust/orderAdd",
    request=OrderAddRequest,
    responses={200: OrderAddResponse},
    summary="新增订单委托",
    description="...",
    tags=["订单"],
    auth_required=True,
    # mock_hook=None, validate_hook=None, build_request_hook=None  # 默认走通用行为
)
```

**关键性质**:
- 数据类与实例**引用同一个 class 对象**(Python 自动),改一处全改
- 数据类**不通过装饰器**注册,EndpointSpec 实例**也不通过装饰器**注册——**两者都是模块级普通定义**,拉式收集只挑 `EndpointSpec` 实例
- **两个消费者各取所需**:
  - Scenario 加载:`spec.request.model_validate(body)`
  - Mock 启动:遍历 spec 绑路由,用 `spec.responses[status]` 造数据

### 3.5 EndpointSpec 字段定稿

```python
# ModelRegistry/spec.py
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable, final
from pydantic import BaseModel


# ===== hook Protocol(本期不实装,签名本期定) =====

@runtime_checkable
class MockHook(Protocol):
    """被 mock 响应生成时调用,产出完整 response body dict。

    返回 None = 走通用 mock 逻辑(用 examples 填字段)。
    """
    def __call__(self, spec: "EndpointSpec", request_payload: dict) -> dict | None: ...


@runtime_checkable
class ValidateHook(Protocol):
    """被 response 校验时调用,在 extra=forbid 之后、断言策略之前。"""
    def __call__(
        self, spec: "EndpointSpec", response_payload: dict, status: int
    ) -> None: ...


@runtime_checkable
class BuildRequestHook(Protocol):
    """被请求构建时调用,在 model_validate 之后、httpx 发出之前。返回值替换原 body dict。"""
    def __call__(self, spec: "EndpointSpec", values: dict) -> dict: ...


# ===== EndpointSpec 本身 =====

@final
@dataclass(frozen=True)
class EndpointSpec:
    # —— 数据(必填)——
    method: str
    path: str
    request: type[BaseModel] | None = None          # None = 该 method 无 body(如部分 GET)
    responses: dict[int, type[BaseModel]] = field(default_factory=dict)

    # —— 文档元数据(喂 mock / 后期 OpenAPI 导出)——
    summary: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    auth_required: bool = False

    # —— 预留槽位(本期不实装,Optional=None,后期启用零破坏)——
    default_response: type[BaseModel] | None = None      # 兜底响应(未注册状态码走它)
    response_union: dict[int, tuple[type[BaseModel], ...]] = field(default_factory=dict)  # 同状态码多 schema

    # —— 能力 hook(本期不实装,None = 走通用行为)——
    mock_hook: MockHook | None = None
    validate_hook: ValidateHook | None = None
    build_request_hook: BuildRequestHook | None = None

    def __post_init__(self):
        # 必填字段类型校验
        if not (self.request is None or (
            isinstance(self.request, type) and issubclass(self.request, BaseModel)
        )):
            raise TypeError(f"{self.path}: request 必须是 BaseModel 子类或 None")
        for code, model in self.responses.items():
            if not isinstance(code, int):
                raise TypeError(f"{self.path}: responses 的 key 必须是 int 状态码,实际 {type(code).__name__}")
            if not (isinstance(model, type) and issubclass(model, BaseModel)):
                raise TypeError(f"{self.path}: responses[{code}] 必须是 BaseModel 子类")
        if self.default_response is not None:
            if not (isinstance(self.default_response, type) and issubclass(self.default_response, BaseModel)):
                raise TypeError(f"{self.path}: default_response 必须是 BaseModel 子类")
        # 契约保真护栏(对应 §3.6)
        self._assert_safe_model(self.request, "request") if self.request is not None else None
        for code, model in self.responses.items():
            self._assert_safe_model(model, f"response[{code}]")
        if self.default_response is not None:
            self._assert_safe_model(self.default_response, "default_response")

    @staticmethod
    def _assert_safe_model(cls: type[BaseModel], role: str) -> None:
        """契约保真护栏:model 必须不会改写 wire 格式。"""
        cfg = getattr(cls, "model_config", None)
        if cfg is None:
            raise TypeError(
                f"{cls.__name__}.{role}: 缺少 model_config。"
                f"契约模型必须显式声明 model_config = ConfigDict(extra='forbid', ...)。"
                f"详见 docs/modules/schema.md §契约保真。"
            )
        # 兼容 dict 与 ConfigDict 两种形态
        extra = cfg.get("extra") if isinstance(cfg, dict) else getattr(cfg, "extra", None)
        if extra != "forbid":
            raise TypeError(
                f"{cls.__name__}.{role}: model_config['extra'] 必须为 'forbid',"
                f"契约模型不允许默默吞掉未知字段(避免字段被静默删除)。"
                f"当前值: {extra!r}。"
            )
        # 禁用清单:任何会改写 wire 格式的 Pydantic 选项必须关闭
        for forbidden_key, why in [
            ("str_strip_whitespace", "会把 ' abc ' 改成 'abc',破坏 wire 格式"),
            ("coerce_numbers_to_str", "会把 55 / '55' 互转,影响类型判断"),
            ("use_enum_values", "会把 Enum 实例替换为字面值,改变 wire 表示"),
        ]:
            val = cfg.get(forbidden_key) if isinstance(cfg, dict) else getattr(cfg, forbidden_key, None)
            if val:  # True / 非 None 都算开启
                raise TypeError(
                    f"{cls.__name__}.{role}: model_config['{forbidden_key}'] 必须关闭。"
                    f"原因:{why}。当前值: {val!r}。"
                )
```

**关键性质**:
- `@final`:不允许继承(配合拉式收集的 `type(attr) is EndpointSpec` 严格匹配)
- `frozen=True`:实例不可变,杜绝"反查后被改"的隐性状态
- `__post_init__` 在 spec 注册瞬间强校 model 安全性
- `default_response` / `response_union` 是**预留槽位**,Optional / 空 dict,本期不实装,后期启用零 breaking

### 3.6 Protocol hook 签名(本期定,不实装)

```python
# 见 §3.5 的 Protocol 定义
```

**为什么必须现在定签名**:hook 内部需要访问 `spec.method` / `spec.path` / `spec.responses` 等上下文,这些是 EndpointSpec 的 dataclass 字段。后期实装 hook 时,若发现需要更多运行时上下文(scenario_id、user、time),**通过 closure 或全局 context manager 取**,不污染 spec。

### 3.7 错误信息包装(三类)

错误对作者友好是工程现实要求。**以下三类错误必须在抛出时包装**:

#### 3.7.1 ValidationError 包装(scenario 加载时)

```python
# ScenarioRunner._validate_step_body() 中
try:
    spec.request.model_validate(body)
except ValidationError as e:
    raise ScenarioLoadError(
        f"step[{step.id}]: {api.method} {api.path} 的 body 不满足契约\n"
        f"  契约模型: {spec.request.__name__}\n"
        f"  字段错误:\n" +
        "\n".join(f"    - {'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors())
    ) from e
```

#### 3.7.2 LookupError 包装(spec 缺失)

`registry.resolve()` 已自带"已注册的相近端点"提示(见 §3.3),无需额外包装,但要确保:
- 提示作者"在 `ModelRegistry/<service>/<endpoint>.py` 建 spec"
- 给出文件命名建议(例如 `/api/order/orderEntrust/orderAdd` → `order_add.py`)

#### 3.7.3 TypeError 包装(model 安全性校验失败)

`__post_init__` 中的 `_assert_safe_model` 已自带"原因 + 修复建议 + 文档链接",**直接在 raise 信息里写明**(见 §3.5)。

---

## 4. Scenario 加载器接入(零侵入 + 渐进)

### 4.1 `contract_validation.mode` 渐进开关

**问题**:存量 scenario 大量 endpoint 还没建 spec,如果 v3 一上来就 strict 校验,**所有存量 scenario 一夜全红**——这与"零 breaking change"承诺冲突。

**解决**:在 framework 配置(scenario config 或全局配置)引入三态开关:

```yaml
# scenario config 内,或全局 gimbal 配置
contract_validation:
  mode: warn   # strict | warn | off
```

| mode | 行为 | 适用阶段 |
|---|---|---|
| `off` | 不查 ModelRegistry,scenario 维持裸 dict 行为(完全不变) | 框架默认 / 未启用契约时 |
| `warn`(默认) | 反查失败 → log warning,跳过 `model_validate`;反查成功 → 跑 `model_validate`,失败报错 | 渐进期:边建 spec 边跑 scenario |
| `strict` | 反查失败 → fail;反查成功 → `model_validate` 必须过,失败 fail | 终态:ModelRegistry 覆盖所有 endpoint 后 |

**默认值 `warn`**——存量 scenario 继续跑,新建 spec 的 endpoint 自动获得校验,作者不需要批量改 scenario。

**切到 `strict` 的时机**:当 `gimbal contract check --coverage` 报告显示"spec 覆盖率 = 100%"时,可以切。

### 4.2 Phase 3.5 校验时序

Scenario 加载器的新校验插入到 Phase 3(模板替换)之后、Phase 4(构建 base_url)之前,作为**新 Phase 3.5**:

```
Phase 0: 引用物化(AssetMaterializer 还原 api_ref / request_ref / strategy_ref)
Phase 1: 认证(AuthManager → AuthRegistry)
Phase 2: 构建查询根(services + auth.snapshot)
Phase 3: 模板展开(${auth.*} ${service.*} ${var.*})
Phase 3.5: [新] 契约校验
          ├─ 调 registry.resolve(api.service, api.method, api.path) 拿 spec
          ├─ spec.request 非 None 时,做 spec.request.model_validate(body)
          └─ 失败 → ScenarioLoadError,fail-fast
Phase 4: 提取 base_url
Phase 5: HTTP 调用
```

**为什么是 Phase 3.5 而不是 Phase 0**:
- Phase 0 之后 `body` 才有具体值(ref 展开)
- Phase 3 之后 `${...}` 模板被替换为字面值
- extract 策略在 Phase 5 HTTP 调用**之后**才发生,extract 出来的值**写回** `body` 是下一个 step 的事,不影响当前 step 的校验

**对 ref 形态的支持**:`request_ref` 展开后,`step.request.body` 才有值;Phase 3.5 的校验对**展开后的 body** 做 model_validate,ref 机制不变。

### 4.3 scenario body 校验的实现

```python
# 在 ScenarioRunner 的 Phase 3.5(在 §4.2 描述的位置)
def _validate_step_body(step, mode: str) -> None:
    if mode == "off":
        return
    api = step.api
    try:
        spec = registry.resolve(api.service, api.method, api.path)
    except LookupError as e:
        if mode == "warn":
            logger.warning(f"[contract] {e}\n  → 跳过 model_validate,请考虑建 spec")
            return
        raise ScenarioLoadError(str(e)) from e
    if spec.request is None:
        return  # GET 类无 body,跳过
    try:
        spec.request.model_validate(step.request.body)
    except ValidationError as e:
        if mode == "warn":
            # 严格说,warn 模式下也该报错——但为了"渐进"体验,先 warning
            logger.warning(
                f"[contract] step[{step.id}]: {api.method} {api.path} body 不满足契约\n" +
                "\n".join(f"  - {'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors())
            )
            return
        raise ScenarioLoadError(
            f"step[{step.id}]: {api.method} {api.path} body 不满足契约\n"
            f"  契约模型: {spec.request.__name__}\n"
            f"  字段错误:\n" +
            "\n".join(f"    - {'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors())
        ) from e
```

**注意**:`warn` 模式下 model_validate 失败也只 warning 而不报错,目的是"作者可能正在改 scenario,先跑起来再说"。

---

## 5. 契约保真要求(从 v1/v2 完整保留 · 全方案最关键的工程约束)

迁移对账的价值完全建立在"模型不悄悄改写 payload"之上。模型一旦默默把 `""` 规整成 null、丢字段、把字符串转整数,就可能**恰好抹掉正要抓的那个 bug**。硬性约束:

### 5.1 字段类型按 PHP 实际线格式定义,不图省事

body 中 `service_id:"55"`、`customer_id:"16"`、`status:"1"`、`supplier_id:"8"`、`main_ids:"31,1"` **均为字符串**。标成 `int` 会让 Pydantic 在实例化阶段把 `"55"` 转成整数(发生在 httpx 之前,httpx 只忠实发整数),而 PHP 当初收的是字符串——这个差异**正是要 diff 的对象**。**规则:是字符串就写 `str`**,类型按被测系统真实线格式定。

### 5.2 null 处理:禁用 `exclude_none`

httpx 会把 `None` 忠实序列化为 `null` 发出。`gross_weight:null`、`bulk:null` 等三态中的 null 支,只要**不用 `model_dump(exclude_none=True)`** 即可干净保真。

### 5.3 空串默认值对齐 PHP "未填"语义

危险仅在于"作者省略某字段、而模型默认值是 `None`"——此时 PHP 期望的 `""` 会塌成 null。**字段默认值必须与 PHP "未填"语义一致**(该 `""` 就默认 `""`)。

### 5.4 加载期硬护栏:`extra="forbid"` + round-trip 无损自检

不靠人脑逐字段推理,用两条机器护栏兜住:

- **`extra="forbid"`**:作者 dict 有、模型没有的字段直接报错,不被默默吞掉。
- **round-trip 等价自检**——本套契约模型"无损"的**定义**:

```python
assert Model.model_validate(raw).model_dump(by_alias=True) == raw
```

任何序列化偏差(类型被强制、字段被丢、key 重排、空值被改写)都在**启动期炸出**,而非对账时才发现 payload 被改过。

**v3 的实现位置**:
- `extra="forbid"` 在 `__post_init__._assert_safe_model` 中强校(§3.5)
- round-trip 自检**本期不实装**,流程文档化,见 §7.3

### 5.5 文档 / mock 的 examples 也要用真实线格式

自动生成的 mock / example 会带 `"55"`、`""` 这类"不漂亮但真实"的值,**这是对的,别美化**——文档的价值正是展示真实线格式。`Field(examples=...)` 写示例时务必用真实形态(`"55"` 而非 `55`),否则文档示例与契约模型自相矛盾。

---

## 6. 模板兼容(从 v1/v2 完整保留 · 当前可行,后续按需扩展)

`@{}` / `${}` 模板目前**全部落在 `body` 内**,且仅落在 `str` 字段(如 `bl_no`、`pol`),与 §4.2 Phase 3.5 校验**无冲突**(模板替换在 Phase 3 完成,Phase 3.5 校验的是替换后的值),本期无需特殊处理。

**已识别但推迟**:当模板需塞进 `int` / `float` / `list` 字段(`teu` / `gross_weight` / `container`)时,Phase 3.5 校验会绊住。届时为相关字段开 `Annotated[int | TemplateExpr, ...]` 占位口子,采用两段校验(Phase 3.5 只校结构与静态字段;模板替换后再跑完整校验)。**本期不预先实现**。

> 这与 §4.2 的"ref 展开 + 模板替换后才校验"是同一套机制:运行期 extract 产生的值加载期不存在,与模板替换一样,完整校验都推迟到"解析完成之后"。

---

## 7. `gimbal contract check` 命令

### 7.1 子命令设计

```
gimbal contract check [--services <list>] [--coverage] [--roundtrip <baseline_dir>]
```

| 选项 | 行为 |
|---|---|
| (无) | 检查 ModelRegistry 子系统内部健康(见下) |
| `--services S1,S2,...` | 限定预热的 service 列表(否则预热所有已注册 service) |
| `--coverage` | 附加报告:扫所有 scenario,统计 spec 覆盖率(见 §7.2) |
| `--roundtrip <dir>` | 附加报告:与 baseline payload 做 round-trip 对比(见 §7.3) |

**内部健康检查**(必跑):

1. **spec 收集健康**:`registry.warm(services)` 全部 spec 实例 `__post_init__` 通过(model 安全性校验全过)
2. **service 名可达**:warm 列表中每个 service 都能解析到合法目录,且目录存在
3. **内部一致性**:同一 service 内 `(method, path)` 唯一(避免一个目录里两个 spec 撞 path)

**退出码**:有错误 → exit code != 0,适合 CI 接入。

### 7.2 spec 覆盖率报告(`--coverage`)

**不报错,只报告**——服务于:
- 作者写完 spec,想知道"这个 spec 真的被用到了吗?"
- 清理过期 spec

```
[contract check] spec coverage:
  ✓ 17 specs referenced by scenarios (在用)
  ⚠ 2 specs registered but unused (死契约):
    - ModelRegistry.settlement.order_page
    - ModelRegistry.order.order_detail
  ✗ 3 endpoints referenced by scenarios but no spec (缺失契约):
    - tidb-test-service POST /api/order/orderEntrust/orderAdd  ← 实际有,可能是路径 typo
    - ...
```

**`✗` 项不阻塞**——`--coverage` 是报告,不是断言。但**作者应**根据报告决定是否建 spec 或修正路径。

**触发 `strict` 模式的判定条件**:当 `✗` 项数量为 0 时,推荐切到 `strict` 模式。

### 7.3 round-trip baseline 流程(`--roundtrip`,本期文档化、不实装)

虽然本期不实装,但流程要文档化,后期真要做迁移对账时不需要再发明:

```
# 1. 作者写完 OrderAddRequest
# 2. 从存量 scenario 抓所有该 endpoint 的 body(可能来自 test1.json 那个大 body)
# 3. 跑一次 round-trip:
spec.request.model_validate(body).model_dump(by_alias=True) == body
# 4. 把通过的 body 存为 tests/contract_baselines/settlement/order_add.json
# 5. CI 跑 gimbal contract check --roundtrip tests/contract_baselines/
```

**基线 bootstrap 是一次性工作**,bootstrap 完成后 CI 跑 `contract check --roundtrip` 即可持续监控 model 是否改写 wire 格式。

**本期不实装这个流程**,但 v3 文档明确"这条路径存在,真需要时启用"。

---

## 8. 后期演进

### 8.1 mock server(主消费者)

EndpointSpec 的设计已为 mock server 留好全部结构化空间:

```
mock server 启动:
  1. 接收声明要 mock 的 service 列表(services=[...])
  2. registry.warm(services)  # 走 §3.3 共用 warm,收集 EndpointSpec
  3. 遍历收集到的 spec
  4. 按 (method, path) 注册到 mock 前端路由
  5. handler 用 spec.responses[status] 的 model + examples 造数据返回
                  (若该实例提供 mock_hook,则走 hook)
```

**与 reverse / warm / collect 完全自洽**——mock 启动 = 一次 `warm()` 调用,后面是 routing 层的事。

**框架选型**(本期不实装,后期决策):FastAPI / aiohttp / Flask 任选,只取决于 framework 偏好。EndpointSpec 与框架解耦。

### 8.2 OpenAPI 导出

遍历所有 `EndpointSpec`,每个吐 `method` / `path` / `summary` / `tags` + 各 response 的 `model_json_schema()`,拼成 OpenAPI spec:

```python
def export_openapi(services: list[str]) -> dict:
    specs = registry.warm(services)
    paths = {}
    for spec in specs:
        # OpenAPI 3.0 pathItem 形态
        paths[spec.path] = {
            spec.method.lower(): {
                "summary": spec.summary,
                "tags": spec.tags,
                "responses": {
                    str(code): {"content": {"application/json": {"schema": model.model_json_schema()}}}
                    for code, model in spec.responses.items()
                },
                # ... requestBody 等
            }
        }
    return {"openapi": "3.0.0", "paths": paths}
```

**字段级文档**来自 `Field(description=, examples=)`,是 §5 严格建模的免费红利。

### 8.3 hook 实装

仅当真实碰到系统特异语义、通用 mock 造不出合理数据时,在具体 EndpointSpec 实例上实装对应 hook(§3.5 的 Protocol)。

**纪律**:
- hook 只承载"跟这一个接口的契约内在相关、且可能因系统而异"的行为
- 跨 endpoint 的编排、reverse 索引、event bus、状态机、报告等框架骨架,绝不下沉到 endpoint
- 否则 EndpointSpec 会膨胀成上帝对象

---

## 9. 落地清单(实现时可独立提交的改动)

按依赖顺序排列。

### A. 目录与基础设施

- [ ] **A1** 新建 `ModelRegistry/` 目录(`__init__.py` 只 re-export `registry`)。
- [ ] **A2** 写 `ModelRegistry/core.py`:`_Registry` + `EndpointKey` + `resolve` + `warm` + `threading.Lock` + `BootstrapError`,导出单例 `registry`。
- [ ] **A3** 写 `ModelRegistry/_aliases.py`:`SERVICE_ALIASES` dict + `resolve_dir_name()` 函数。文件顶部加注释说明本表是 service 命名不一致时的唯一兜底。
- [ ] **A4** 写 `ModelRegistry/spec.py`:`@final` + `frozen=True` 的 `EndpointSpec` + 三个 `runtime_checkable Protocol`(MockHook / ValidateHook / BuildRequestHook)+ `__post_init__` 含 `_assert_safe_model` 强校验。
- [ ] **A5** `ModelRegistry/__init__.py` 只 `from .core import registry`,**不 import 任何子包**。

### A.5 [新] 空 stub 验证阶段

- [ ] **A5.1** 在 `ModelRegistry/` 目录下保持空:无任何 service 子目录。
- [ ] **A5.2** 跑现有 scenario(如 `examples/login_and_query/` 下任何用例),确认:
  - `import ModelRegistry` 不破坏任何东西
  - scenario 加载时 `contract_validation.mode=off`(默认)行为不变
  - `gimbal contract check` 在无 service 时优雅退出(exit 0 或有"无 service 注册"提示)
- [ ] **A5.3** 验证"零侵入"承诺:**这是 v3 的核心承诺,必须先证后建**。

### B. 契约模型(试点先行)

- [ ] **B1** 选 `settlement` 为第一个 service,在 `ModelRegistry/settlement/__init__.py` 声明:`# service: settlement(目录名即 service 名)`(注释即可,无需 `SERVICE` 常量)。
- [ ] **B2** 写 `ModelRegistry/settlement/order_add.py`:
  - `OrderAddRequest` 数据类:按 §5 真实线格式定义字段(数字串保持 `str`、空串默认 `""`、`extra="forbid"`、`populate_by_name=True`、每个字段 `Field(description=, examples=)`,examples 用真实形态)
  - `OrderAddResponse` 数据类:同上
  - `ORDER_ADD = EndpointSpec(method=..., path=..., request=OrderAddRequest, responses={200: OrderAddResponse}, summary=..., tags=[...], auth_required=True)`
- [ ] **B3** 跑 §A5.2 同样的验证,确认 `warm(["settlement"])` 能正确收集到 `ORDER_ADD`,且 `__post_init__` 通过。
- [ ] **B4** 写一个 Python 脚本(`scripts/contract_roundtrip.py`)手动跑 §5.4 round-trip,验证 B2 写的 model 不改写 wire 格式。**这是 §7.3 流程的手动版本**。

### C. Scenario 加载器接入

- [ ] **C1** 在 framework 配置引入 `contract_validation.mode` 字段(`off` / `warn` / `strict`),默认 `off`(向后兼容;后期再改 `warn`)。**注意:v3 文档示例中是 `warn` 为默认,但实现时先 `off`,避免存量 scenario 行为变化**。
- [ ] **C2** 在 ScenarioRunner 引入 Phase 3.5 钩子(ref 展开 + 模板替换之后、HTTP 调用之前)。
- [ ] **C3** Phase 3.5 实现 `§4.3 _validate_step_body()`:按 mode 决定行为。
- [ ] **C4** 三类错误包装(§3.7):`ValidationError` / `LookupError` / `TypeError` 全部包装为对作者友好的信息。
- [ ] **C5** 在 `docs/modules/schema.md` 加一节"ModelRegistry 契约真源",说明:
  - scenario body 必须满足 `EndpointSpec.request`(strict 模式)
  - `request_ref` 展开后,Phase 3.5 对展开后的 body 校验
  - GET 类接口允许 `request=None`

### D. 校验时机

- [ ] **D1** spec 注册期:`__post_init__` 强校 model 安全性(§3.5)
- [ ] **D2** scenario 加载期:Phase 3.5 model_validate(§4.2)
- [ ] **D3** contract check 期:`warm()` 触发所有 spec 注册期校验(§7.1)
- [ ] **D4** round-trip 期(本期不实装):见 §7.3 流程文档

### E. 启动期校验

- [ ] **E1** 实现 `gimbal contract check` 子命令(§7.1 内部健康检查 3 条)
- [ ] **E2** 实现 `--coverage` 报告(§7.2)
- [ ] **E3** CI 接入:`contract check` 必跑;`--coverage` 报告归档
- [ ] **E4** **并发压测**(对应 §10.2 易错点):`tests/concurrency/test_registry_race.py` —— N 线程并发 `resolve()` 同一组 `(service, method, path)`,跑 1000 轮无 `RuntimeError`。后续若有人把"读"挪到锁外,CI 立刻爆。
- [ ] **E5** (后期)实现 `--roundtrip` 选项(§7.3)

### F. 后续(本期不实装,仅预留)

- [ ] **F1** mock server 启动(§8.1)
- [ ] **F2** OpenAPI 导出(§8.2)
- [ ] **F3** hook 实装(§8.3)
- [ ] **F4** JSON Schema 导出供 IDE 编辑 scenario 使用
- [ ] **F5** `request_ref` 内的 body 校验(Phase 3.5 已有,本期不专门测)

### G. 文档与 CI

- [ ] **G1** `docs/modules/schema.md` 加"ModelRegistry 契约真源"节(C5 同步)
- [ ] **G2** `docs/modules/contract.md`(新文件)详述 §5 契约保真要求、`__init_subclass__` 禁用清单、Protocol hook 签名
- [ ] **G3** CI workflow 加 `gimbal contract check` 步骤(E3)
- [ ] **G4** `docs/contributing/adding-endpoint.md`(新文件)给作者一个"新增 endpoint 必做清单"——写数据类、写 EndpointSpec、跑 contract check、写 baseline

---

## 10. 风险与边界

### 10.1 强耦合:每个 endpoint 都必须有 spec(strict 模式)

v3 的设计意味着 strict 模式下,scenario 不能引用 ModelRegistry 还没建的 endpoint。这是**设计选择的强耦合,不是 bug**——是契约系统的本质。

**应对**:§4.1 `contract_validation.mode` 三态开关是过渡方案。`off` → `warn` → `strict` 是渐进步骤。

### 10.2 并发安全

`registry` 是单例,`collect()` 修改 `_index` / `_loaded`。§3.3 已加 `threading.Lock` 保护。`resolve` 内部递归调 `collect` 不会死锁(锁是可重入的会更好,但 Python 的 `threading.Lock` 不可重入,所以 `collect` 内部不再调 `collect` 即可——目前实现就是这样的,安全)。

**易错点(已修)**:v3 初稿 `resolve` / `warm` 把 "collect + 读" 拆成两步——`self.collect(service)` 取锁释放锁后,再到锁外迭代 `self._index`。这在并发场景下会触发 `RuntimeError: dictionary changed size during iteration`:线程 A 正在锁外迭代 `self._index`,线程 B 同时 `collect` 在持锁时往 `self._index` 塞 key,CPython 抛错。**修复方式**:`collect` 拆出内部 `_collect_locked`(假设已持锁),`resolve` 和 `warm` 把"collect + dict 读取/迭代"包进同一个 `with self._lock:`。EndpointSpec 是 `frozen=True` 的 dataclass,锁内取出后到锁外用是安全的(实例不可变,无 TOCTOU 风险)。

**CI 防御**:`tests/` 加一个并发压测 case——N 个线程并发 `resolve()` 同一组 `(service, method, path)`,跑 1000 轮不出 RuntimeError 才算修对。这条 case 写在 `tests/concurrency/test_registry_race.py`,与 `pytest -x` 一起跑,后续若有人不小心又把"读"挪到锁外,CI 会立刻爆。

### 10.3 `_aliases.py` 加载顺序

`_aliases.py` 在 `ModelRegistry/__init__.py` 导入时被 `core.py` 引用,因此 `import ModelRegistry` 时 alias 表已就绪。**注意**:`_aliases.py` 必须是**纯数据 dict**,不允许 import 业务模块。

### 10.4 `Request.body: dict[str, Any]` 的 schema 没改

v3 的 `Request` Pydantic 模型**没改**,scenario JSON 文件结构上仍可以是任意 dict(schema 不卡),校验发生在**运行期**(Phase 3.5)。

**代价**:作者在 IDE 里写 scenario JSON 时没有 schema 提示。**F4 后期**用 JSON Schema 导出弥补。

### 10.5 round-trip baseline 流程本期不实装

v3 的 §7.3 流程文档化但本期不实装。**理由**:没 baseline 就跑不了 round-trip,而 baseline bootstrap 需要从存量 scenario 抓 body,在存量 scenario 还没大规模通过 Phase 3.5 校验时 bootstrap 没意义。

**触发实装的时机**:存量 scenario 大部分跑通(模式切到 `warn` 后期),开始做迁移对账时,启用 F4 + round-trip。

### 10.6 三个 hook 本期不实装

Protocol 签名本期定,实现 G1 后再实装。**风险**:如果实装时发现 hook 需要更多 spec 上下文(spec 现有字段不够用),要改 Protocol——破坏现有 spec 实例。

**应对**:Protocol 当前签名只访问 `spec.method` / `spec.path` / `spec.responses` / `spec.summary` / `spec.tags` / `spec.auth_required`,都是 EndpointSpec 已有字段。**运行时上下文**(scenario_id / user / time)**不通过 spec 传**,hook 内部用 closure 或 framework 全局 context 取。

---

## 决策摘要(v3)

| 项 | 决策 |
|---|---|
| 模块命名 | ✅ `ModelRegistry`(v1 的 `PathRegistry` 改名) |
| service 组织 | ✅ service 名 = 目录名 = import 路径;不合法 Python 标识走 `_aliases.py` 集中表 |
| 复用形态 | ✅ **双场景复用**:数据类(scenario 用)+ EndpointSpec 实例(mock 用)共存于同一文件 |
| 接口 ↔ model 绑定 | ✅ **反查** `(service, method, path) → EndpointSpec`;scenario 取 `spec.request`,mock 取整个 spec |
| 拉式收集 | ✅ `type(attr) is EndpointSpec` 严格匹配;零 import 副作用,幂等;加 `threading.Lock` |
| `EndpointSpec` 形态 | ✅ `@final` + `frozen=True`;Protocol hook 签名本期定;`responses` / `default_response` / `response_union` / hook 都是预留槽位 |
| 注册期校验 | ✅ `__post_init__` 强校 model 安全性(`extra="forbid"`、禁用清单) |
| scenario 加载 | ✅ Phase 3.5(ref 展开 + 模板替换之后)调 `resolve` + `model_validate`;GET 类 `request=None` 跳过 |
| 渐进开关 | ✅ `contract_validation.mode` 三态:`off` / `warn` / `strict`,默认 `off`(实现初期)→ `warn`(渐进)→ `strict`(终态) |
| 信封 | ✅ 沿用 `{ kind, body, headers }`,**无重命名** |
| 错误信息 | ✅ `ValidationError` / `LookupError` / `TypeError` 三类全部包装为作者可读信息 |
| `gimbal contract check` | ✅ 本期实现:内部健康检查 3 条 + `--coverage` 报告 |
| round-trip | ✅ 流程文档化(§7.3),本期不实装;baseline bootstrap 是后期工作 |
| 模板在 int/list 字段 | ⏸ 推迟,届时 `Annotated[int \| TemplateExpr, ...]` + 两段校验 |
| mock server | 🔵 后期 F1,主消费者;启动走 `warm()` 共用入口 |
| OpenAPI 导出 | 🔵 后期 F2 |
| hook 实装 | ⏸ 后期 F3,仅在真实碰到系统特异语义时实装 |
| JSON Schema 导出 | 💡 后期 F4,供 IDE 编辑 scenario 时提示 |
| 迁移策略 | ✅ **无**——v3 对存量 scenario 零 breaking change |
| breaking change | ✅ **无**(配合 `mode=off` 默认) |

---

## 附:从 v1 到 v3 的演化总览

| 维度 | v1 (PathRegistry) | v2 (单 EndpointSpec) | v3 (双场景复用) |
|---|---|---|---|
| 命名 | PathRegistry | ModelRegistry | ModelRegistry |
| 绑定方式 | api 持 `request_model` 显式引用 | 反查 `(service, method, path)` | 反查(同 v2) |
| 数据类 / 实例 | 不区分 | EndpointSpec 为主,数据类隐含 | **数据类 + EndpointSpec 实例共存** |
| Decorator 机制 | 装饰器 push | 装饰器+ast → 全砍,改拉式收集 | 拉式收集(同 v2)+ 严格 `type(...)` 匹配 + 锁 |
| 信封 | `request: { model_ref, values, headers }` | 同 v1 | **`request: { kind, body, headers }`**(原状) |
| 校验时机 | 加载期 | 加载期 + 启动期清单 6 条 | Phase 3.5 + 启动期 `contract check` |
| 渐进开关 | 无 | 无 | **`contract_validation.mode` 三态** |
| 钩子签名 | 无 | `Callable` 占位 | **`runtime_checkable Protocol` 本期定** |
| 迁移策略 | deprecation alias 或脚本 | 同 v1 | **无** |
| breaking change | 有 | 有 | **无** |
| 反查 vs 显式引用 | 显式引用 | 反查 | 反查 |
| 实际意义 | 演示方向 | 锁定架构 | **可落地** |

**v3 = v2 的架构 + 你这版"双场景复用"的具体形态 + 多轮 review 沉淀的工程细节。** 它对存量零侵入,把契约保真的全部约束(`extra="forbid"`、禁用清单、round-trip)放在 spec 注册期(`__post_init__`),把 scenario 加载期校验放在 Phase 3.5,把 mock 启动预热放在共用 `warm()`。每一层都有明确的失败时机和错误信息,没有"静默放过"的口子。
