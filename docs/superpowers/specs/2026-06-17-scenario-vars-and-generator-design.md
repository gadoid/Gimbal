# Scenario 变量注入与生成器设计

> **状态**：✅ 已批准（2026-06-17）
> **范围**：在 Scenario 级别声明变量（字面量 + 生成式），在预处理阶段一次性求值，复用现有 `${var.x}` 模板管线。

---

## 1. 背景与动机

当前 e2e.json 里有大量硬编码的"业务单号"型字段（`bl_no` / `voy` / `ship_name` / `order_no` 等），同一个值在 20+ 个 step 中重复出现：

```json
"bl_no": "codfishe2e24",
"voy":   "codfishe2e24",
"ship_name": "codfishe2e24",
"customer_order_sn": "codfishe2e24"
```

问题：

1. **重复维护**：改一个值要在 20 处同步
2. **可读性差**：分不清"哪些字段业务上必须一致"
3. **不真实**：测试环境很容易撞单号
4. **没有"声明式数据"**：业务字段值散落各处，无法集中管理

**目标**：让 scenario 能在 `config.vars` 集中声明"哪些字段是共享的、怎么生成"，step body 用 `${var.x}` 引用——复用现有模板管线，零模板语法改动。

---

## 2. 设计决策（已与用户确认）

| 维度 | 决策 |
|------|------|
| 变量作用域 | Scenario 级（同一 run 内所有 step 共享） |
| 触发时机 | Preprocessor 阶段一次性求值，注入 `root["var"]` |
| 声明位置 | `scenario.config.vars`（与 `services` / `users` 同级） |
| 字面量支持 | 容器内每一项运行时判定：dict（有 `kind`）→ 生成式；primitive → 字面量 |
| 优先级 | CLI `--var` 覆盖 `scenario.config.vars`（同名时 CLI 赢） |
| 重试/重跑 | 每次 run 独立生成新值，不引入 seed |
| 变量间引用 | 不支持（YAGNI；复杂表达由未来模板层承担） |
| 模板语法 | **零改动**，复用现有 `${var.x}` |
| 模块位置 | 新建 `gimbal/generator/` 顶层模块 |
| 模板层 | 现有 `jsonpath.py` 完整支持，**零改动** |

---

## 3. 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│  Scenario JSON 声明                                              │
│  config.vars: {                                                  │
│    bl_no:    { kind: random_str, length: 12, charset: alnum }   │
│    etd:      { kind: timestamp, format: epoch }                  │
│    order_no: { kind: seq, prefix: YWDD, width: 8 }               │
│    customer_id: 16                                              │
│  }                                                               │
│  steps[*].request.body.bl_no: "${var.bl_no}"                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  ScenarioPreprocessor (扩展)                                      │
│  Phase 0:   引用物化                                              │
│  Phase 1:   认证（已有）                                            │
│  Phase 1.5: ★ 变量生成（新增）                                    │
│             1. 合并：scenario.config.vars + BootstrapConfig.vars  │
│             2. CLI 赢（同名 key CLI 覆盖 scenario）               │
│             3. 生成式：VarSpec.model_validate + Generator.generate│
│             4. 字面量：原样保留                                    │
│             5. 产出 resolved_vars: dict[str, Any]                 │
│  Phase 2:   构建 root（注入 resolved_vars 到 root["var"]）        │
│  Phase 3:   模板展开（复用现有 _resolve_value / _get_nested）     │
│  Phase 4:   base_url 提取                                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  新模块 gimbal/generator/                                        │
│  ├── __init__.py                                                  │
│  ├── specs.py        7 个 Pydantic Spec + VarSpec 联合体          │
│  ├── registry.py     GeneratorRegistry（注册表 + 调度）          │
│  ├── functions.py    7 个内置生成函数（pure function）            │
│  ├── engine.py       Generator（求值入口）                       │
│  └── exceptions.py   GeneratorError, UnknownGeneratorError        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. 端到端调用链

```
bootstrap(cli_ctx)
  └─ Generator(default_registry())                  # 构造一次
        ↓
Configuration(cfg=..., generator=generator)         # 注入到 frozen cfg
        ↓
ScenarioPreprocessor(..., bootstrap_config=cfg)
  └─ self._generator = cfg.generator                # 取出
        ↓
preprocessor.run()
  └─ Phase 1.5 _generate_vars()
        ├─ merged = {**scenario_vars, **cli_vars}   # CLI 覆盖 scenario
        └─ for name, spec in merged.items():
              ├─ isinstance(spec, dict) and "kind" in spec:
              │    var_spec = VarSpec.model_validate(spec)
              │    result[name] = self._generator.generate(var_spec)
              │       └─ registry.get(spec.kind)(**params)
              │             └─ random_str(length=12, charset="alnum") → "Yk2H8..."
              └─ isinstance(spec, (str, int, float, bool, type(None))):
                   result[name] = spec              # 字面量
        ↓
  Phase 2 _build_resolve_root()
  └─ root["var"] = result                            # 注入模板查询根
        ↓
  Phase 3 _resolve_steps()
  └─ "${var.bl_no}" → _get_nested(root, "var.bl_no") → "Yk2H8..."
```

---

## 5. Pydantic Schema 设计

### 5.1 7 个生成器 Spec

```python
# gimbal/generator/specs.py
from __future__ import annotations
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field, ConfigDict


class UuidSpec(BaseModel):
    """kind=uuid：32 位 hex"""
    model_config = ConfigDict(extra="forbid")
    kind: Literal["uuid"] = "uuid"


class RandomStrSpec(BaseModel):
    """kind=random_str：随机字符串"""
    model_config = ConfigDict(extra="forbid")
    kind: Literal["random_str"] = "random_str"
    length: int = Field(default=8, ge=1, le=1024, description="字符串长度")
    charset: Literal["alpha", "digit", "alnum"] = Field(default="alnum", description="字符集")


class RandomIntSpec(BaseModel):
    """kind=random_int：闭区间整数"""
    model_config = ConfigDict(extra="forbid")
    kind: Literal["random_int"] = "random_int"
    min: int = Field(default=0, description="下界（包含）")
    max: int = Field(default=100, description="上界（包含）")


class RandomDecimalSpec(BaseModel):
    """kind=random_decimal：闭区间小数"""
    model_config = ConfigDict(extra="forbid")
    kind: Literal["random_decimal"] = "random_decimal"
    min: float = Field(default=0.0, description="下界")
    max: float = Field(default=100.0, description="上界")
    places: int = Field(default=2, ge=0, le=10, description="小数位数")


class TimestampSpec(BaseModel):
    """kind=timestamp：当前时间 + 偏移"""
    model_config = ConfigDict(extra="forbid")
    kind: Literal["timestamp"] = "timestamp"
    format: Literal["epoch", "iso", "compact"] = Field(default="iso")
    offset_seconds: int = Field(default=0, description="相对 now 的偏移（正=未来）")


class NowSpec(BaseModel):
    """kind=now：当前时间（无偏移）"""
    model_config = ConfigDict(extra="forbid")
    kind: Literal["now"] = "now"
    format: Literal["epoch", "iso", "compact"] = Field(default="iso")


class SeqSpec(BaseModel):
    """kind=seq：自增序号 + 业务前缀"""
    model_config = ConfigDict(extra="forbid")
    kind: Literal["seq"] = "seq"
    prefix: str = Field(default="", description="业务前缀，如 'YWDD'")
    width: int = Field(default=6, ge=1, le=20, description="序号位数（不足补 0）")
    start: int = Field(default=1, description="起始值")


# ── 联合体（discriminated by 'kind'）──

VarSpec = Annotated[
    Union[
        UuidSpec,
        RandomStrSpec,
        RandomIntSpec,
        RandomDecimalSpec,
        TimestampSpec,
        NowSpec,
        SeqSpec,
    ],
    Field(discriminator="kind"),
]
```

### 5.2 设计要点

| 决定 | 理由 |
|------|------|
| 7 个 Spec 各自独立 + discriminated union | 与项目现有 `StepUnion` / `ApiUnion` 风格一致（[architecture.md §7](architecture.md)） |
| `extra="forbid"` | 字段名拼写错误（`lenght` 而不是 `length`）立即报错 |
| `Literal["kind"] = "uuid"` | `kind` 有默认值，调用方写 `{"kind": "uuid"}` 等价于 `"uuid"` |
| `ge` / `le` 约束 | 越界值在加载时报错（`length=0` / `length=100000`） |
| `VarSpec` 联合体 | Pydantic 自动按 `kind` 分发到对应子类 |

### 5.3 字面量与生成式混合

`scenario.config.vars` 字段类型：

```python
vars: dict[str, Any] = Field(
    default_factory=dict,
    description="""变量声明：值为 dict（生成式，含 'kind'）或 primitive（字面量）。
    生成式：{"kind": "random_str", "length": 12, "charset": "alnum"}
    字面量：16、"fixed_value"、true、null
    优先级低于 CLI --var（同名时 CLI 赢）。""",
)
```

容器内每一项运行时判定：

```python
def _is_generator_spec(value: Any) -> bool:
    return isinstance(value, dict) and "kind" in value

def _is_literal(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool, type(None)))
```

**校验时机**：

- `vars: dict[str, Any]` 不在 schema 层做深度校验（避免破坏现有 scenario JSON 加载）
- Preprocessor 阶段调用 `VarSpec.model_validate(spec)` 触发校验
- 错误定位在"preprocessor 跑时"，报告"哪个 var、哪个 spec 不合法"

---

## 6. 相关字段扩展

### 6.1 `Scenario.config`

```python
# src/gimbal/schema/scenario.py
class Config(BaseModel):
    """scenario 的 config 块"""
    model_config = ConfigDict(extra="forbid")

    services: dict[str, Any] = Field(default_factory=dict)
    users: dict[str, Any] = Field(default_factory=dict)
    setup: list[Any] = Field(default_factory=list)
    teardown: list[Any] = Field(default_factory=list)
    retry: Any | None = None
    timePolicy: Any | None = None

    # ── 新增：scenario 级变量声明 ──
    vars: dict[str, Any] = Field(
        default_factory=dict,
        description="变量声明；字面量或生成式 spec；CLI --var 优先级更高",
    )
```

### 6.2 `BootstrapConfig`

```python
# src/gimbal/config/models.py
class BootstrapConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    # ... 现有字段保持不变 ...

    vars: dict[str, Any] = Field(
        default_factory=dict,
        description="CLI --var / --var-file 注入的 KV 变量，模板 ${var.*} 引用",
    )

    # ── 新增：generator 实例（由 bootstrap() 注入）──
    # 用字符串前向引用避免循环导入（config 不应依赖 generator，generator 不应依赖 config）。
    # Pydantic v2 + `from __future__ import annotations` 自动解析该前向引用；
    # 若用 Pydantic v1 或关闭 future annotations，则需在 model_rebuild() 时显式解析。
    generator: "Generator" = Field(
        ...,
        description="变量生成器实例（由 bootstrap() 构造并注入）",
    )
```

### 6.3 `bootstrap()` 改造

```python
# src/gimbal/core/bootstrap.py
def bootstrap(cli_ctx) -> Configuration:
    ...
    from gimbal.generator import Generator, build_default_registry
    generator = Generator(build_default_registry())
    ...
    return Configuration(
        cfg=BootstrapConfig(..., vars=cli_vars, generator=generator),
        ...
    )
```

### 6.4 `ScenarioPreprocessor` Phase 1.5

```python
# src/gimbal/preprocessor/scenario_preprocessor.py
class ScenarioPreprocessor:
    def __init__(
        self,
        scenario_schema: "Scenario",
        bootstrap_config: "BootstrapConfig",
        auth_registry: Optional["AuthRegistry"] = None,
        asset_store: Optional["AssetStore"] = None,
    ) -> None:
        # ... 现有字段 ...
        self._resolved_vars: dict[str, Any] = {}   # Phase 1.5 填充，Phase 2 读取

    def run(self) -> tuple[list["StepUnion"], str]:
        if self._asset_store is not None:
            self._materialize_refs()            # Phase 0
        self._setup_auth()                      # Phase 1
        self._generate_vars()                   # Phase 1.5  ★ 新增
        root = self._build_resolve_root()       # Phase 2
        resolved = self._resolve_steps(root)    # Phase 3
        base_url = self._pick_base_url()        # Phase 4
        return resolved, base_url

    def _generate_vars(self) -> None:
        """Phase 1.5: 合并 scenario + CLI vars，生成或保留字面量，注入 self._resolved_vars。

        self._resolved_vars 在 __init__ 中初始化为 {}，用于 Phase 2 注入 root。
        """
        cli_vars = self._cfg.vars or {}
        scenario_vars = getattr(self._schema.config, "vars", None) or {}
        merged: dict[str, Any] = {**scenario_vars, **cli_vars}    # CLI 赢

        result: dict[str, Any] = {}
        for name, spec in merged.items():
            if isinstance(spec, dict) and "kind" in spec:
                var_spec = VarSpec.model_validate(spec)            # 触发 Pydantic 校验
                result[name] = self._generator.generate(var_spec)
            elif isinstance(spec, (str, int, float, bool, type(None))):
                result[name] = spec
            else:
                raise ValueError(
                    f"[Preprocessor] invalid var spec for '{name}': {spec!r} "
                    f"(expected dict with 'kind' or a primitive literal)"
                )
        self._resolved_vars = result

    def _build_resolve_root(self) -> dict[str, Any]:
        root: dict[str, Any] = {"service": {}, "auth": self._auth_registry.snapshot()}
        # 注入生成的 vars（替换原来仅来自 BootstrapConfig.vars 的部分）
        if self._resolved_vars:
            root["var"] = dict(self._resolved_vars)
        return root
```

---

## 7. 新模块结构

```
src/gimbal/generator/
├── __init__.py            # 公开 API 导出
├── specs.py               # 7 个 Pydantic Spec + VarSpec 联合体
├── registry.py            # GeneratorRegistry（注册表 + 调度）
├── functions.py           # 7 个生成函数实现
├── engine.py              # Generator 类（generate / generate_all 入口）
└── exceptions.py          # GeneratorError, UnknownGeneratorError
```

### 7.1 `registry.py`

```python
class GeneratorRegistry:
    def __init__(self) -> None:
        self._funcs: dict[str, Callable[..., Any]] = {}

    def register(self, kind: str, func: Callable[..., Any]) -> None:
        if kind in self._funcs:
            raise ValueError(f"generator '{kind}' already registered")
        self._funcs[kind] = func

    def get(self, kind: str) -> Callable[..., Any] | None:
        return self._funcs.get(kind)

    def kinds(self) -> list[str]:
        return list(self._funcs.keys())


def build_default_registry() -> GeneratorRegistry:
    """构造注册了 7 个内置函数的注册表。"""
    from gimbal.generator import functions
    r = GeneratorRegistry()
    r.register("uuid",           functions.uuid)
    r.register("random_str",     functions.random_str)
    r.register("random_int",     functions.random_int)
    r.register("random_decimal", functions.random_decimal)
    r.register("timestamp",      functions.timestamp)
    r.register("now",            functions.now)
    r.register("seq",            functions.seq)
    return r
```

### 7.2 `engine.py`

```python
class Generator:
    def __init__(self, registry: GeneratorRegistry) -> None:
        self._registry = registry

    def generate(self, spec: VarSpec) -> Any:
        """单条求值。"""
        func = self._registry.get(spec.kind)
        if func is None:
            raise UnknownGeneratorError(spec.kind)
        params = spec.model_dump(exclude={"kind"})
        try:
            return func(**params)
        except Exception as e:
            raise GeneratorError(f"generator '{spec.kind}' failed: {e}") from e
```

### 7.3 `functions.py`（7 个 pure function）

```python
import random
import string
import uuid as _uuid
from datetime import datetime, timedelta, timezone


def uuid() -> str:
    return _uuid.uuid4().hex


def random_str(length: int = 8, charset: str = "alnum") -> str:
    pools = {
        "alpha": string.ascii_letters,
        "digit": string.digits,
        "alnum": string.ascii_letters + string.digits,
    }
    if charset not in pools:
        raise ValueError(f"invalid charset: {charset!r}")
    return "".join(random.choices(pools[charset], k=length))


def random_int(min: int = 0, max: int = 100) -> int:
    if min > max:
        raise ValueError(f"min ({min}) > max ({max})")
    return random.randint(min, max)


def random_decimal(min: float = 0.0, max: float = 100.0, places: int = 2) -> float:
    if min > max:
        raise ValueError(f"min ({min}) > max ({max})")
    val = random.uniform(min, max)
    return round(val, places)


def timestamp(format: str = "iso", offset_seconds: int = 0) -> int | str:
    ts = datetime.now() + timedelta(seconds=offset_seconds)
    if format == "epoch":
        return int(ts.timestamp())
    if format == "iso":
        return ts.isoformat()
    if format == "compact":
        return ts.strftime("%Y%m%d%H%M%S")
    raise ValueError(f"invalid format: {format!r}")


def now(format: str = "iso") -> int | str:
    return timestamp(format=format, offset_seconds=0)


# seq 用模块级计数器；每次 run 一次进程内有效
# 注意：模块级 dict 不跨进程、不跨 run、不线程安全。
# 跨进程场景（如 concurrent suite 跑同 scenario 多次）会让多个 worker 拿到相同的序号；
# 跑前先 `gimbal.generator.functions.reset_seq_counter()` 可重置。
# 多线程场景不常见；如需，加 threading.Lock 即可。
_seq_counter: dict[str, int] = {}


def seq(prefix: str = "", width: int = 6, start: int = 1) -> str:
    key = f"{prefix}|{width}|{start}"
    if key not in _seq_counter:
        _seq_counter[key] = start
    else:
        _seq_counter[key] += 1
    return f"{prefix}{_seq_counter[key]:0{width}d}"


def reset_seq_counter() -> None:
    """重置 seq 计数器（多进程跑前 / 测试隔离用）。"""
    _seq_counter.clear()
```

### 7.4 `exceptions.py`

```python
class GeneratorError(Exception):
    """生成器执行错误（包装原始异常）。"""


class UnknownGeneratorError(GeneratorError):
    """未注册的生成器 kind。"""

    def __init__(self, kind: str) -> None:
        super().__init__(f"unknown generator: {kind!r}")
        self.kind = kind
```

---

## 8. 模板层兼容性验证

### 8.1 为什么不需要改模板层

`${var.x}` 语法由现有 [`gimbal/utils/jsonpath.py`](../../utils/jsonpath.py) 的 `_get_nested` + `resolve_template_strict` 完整支持。它做的只是：

```python
def _get_nested(variables, var_name):
    parts = var_name.split(".")
    current = variables
    for part in parts:
        if isinstance(current, dict):
            if part not in current:
                return _MISSING
            current = current[part]
    return current
```

`variables` 就是 `root["var"]` 字典。我们只是往这个 dict 多塞些 key 而已，模板解析器不关心 key 是 CLI 来的还是 generator 来的。

### 8.2 类型保真

`_resolve_value` 对"整体是单个 `${}`"保留原类型：

| 场景 | `${var.etd}` 解析 | 放入 body 后 |
|------|------------------|------------|
| `int 1781020800` | `int 1781020800` | `"etd": 1781020800` ✓ |
| `str "Yk2H8nQp3aZx"` | `str` | `"bl_no": "Yk2H8nQp3aZx"` ✓ |
| `float 173.42` | `float` | `"weight": 173.42` ✓ |
| `bool false` | `bool` | `"is_special": false` ✓ |

### 8.3 边缘情况

| 场景 | 结果 | 原因 |
|------|------|------|
| 变量名含连字符 `bl-no` | ✓ | `_get_nested` 只按 `.` 切分 |
| 变量名含下划线 `customer_id` | ✓ | Python dict key 兼容 |
| 变量名是数字 `123` | ✓ | JSON 字符串作 dict key 合法 |
| 生成值含特殊字符（`/`, `+`, `=`） | ✓ | 模板解析是单向的：模板→值；不会反向 |
| 生成值本身含 `${` | ✓ | 同上 |
| `${var.X}` 引用了未声明的 `X` | ✓ fail-fast | 返回 `_MISSING`，preprocessor 抛 `ValueError` |
| 嵌入式 `"prefix-${var.x}-suffix"` | ✓ | 字符串拼接路径 |
| 嵌入式变量缺失 | ✓ fail-fast | `resolve_template_strict` 返回 `_MISSING` |
| 单 `${var.x}` 解析为 None | ✓ | 合法 None（key 存在但值就是 None） |

---

## 9. 完整声明示例

```json
{
  "config": {
    "vars": {
      "bl_no":          { "kind": "random_str",    "length": 12, "charset": "alnum" },
      "voy":            { "kind": "random_str",    "length": 8,  "charset": "alpha" },
      "weight":         { "kind": "random_decimal","min": 50,    "max": 200,  "places": 2 },
      "count":          { "kind": "random_int",    "min": 1,     "max": 10 },
      "etd":            { "kind": "timestamp",     "format": "epoch" },
      "etd_str":        { "kind": "timestamp",     "format": "compact" },
      "created_at":     { "kind": "now",           "format": "iso" },
      "order_no":       { "kind": "seq",           "prefix": "YWDD", "width": 8 },
      "trace_id":       { "kind": "uuid" },
      
      "customer_id":    16,
      "service_id":     55,
      "policy_id":      112,
      "is_special":     false
    }
  },
  "steps": [
    {
      "request": {
        "body": {
          "bl_no":             "${var.bl_no}",
          "voy":               "${var.voy}",
          "etd":               "${var.etd}",
          "gross_weight":      "${var.weight}",
          "customer_order_sn": "${var.order_no}",
          "trace_id":          "${var.trace_id}"
        }
      }
    }
  ]
}
```

执行后 `root["var"]` 形如：

```python
{
    "bl_no":       "Yk2H8nQp3aZx",   # 随机
    "voy":         "AaBbCcDd",       # 随机
    "weight":      173.42,            # 随机
    "count":       5,                 # 随机
    "etd":         1781020800,        # 当前时间 epoch
    "etd_str":     "20260617143055",  # 当前时间 compact
    "created_at":  "2026-06-17T14:30:55.123456",  # 当前时间 iso
    "order_no":    "YWDD00000001",    # seq
    "trace_id":    "5a3b...",         # uuid

    "customer_id": 16,                # 字面量
    "service_id":  55,                # 字面量
    "policy_id":   112,               # 字面量
    "is_special":  False,             # 字面量
}
```

---

## 10. 异常与错误处理

| 触发条件 | 异常 | 失败时机 |
|---------|------|---------|
| `kind` 不在注册表 | `UnknownGeneratorError` | preprocessor Phase 1.5 |
| Spec 字段拼写错误 / 越界 | `pydantic.ValidationError` | preprocessor Phase 1.5（`VarSpec.model_validate`） |
| Spec 字段类型错 | `pydantic.ValidationError` | 同上 |
| 生成函数内部异常（`min > max` 等） | `GeneratorError`（包装原异常） | preprocessor Phase 1.5 |
| 字面量值不是合法 primitive | `ValueError` | preprocessor Phase 1.5 |
| `${var.X}` 引用未声明 X | `ValueError`（`_MISSING` → fail-fast） | preprocessor Phase 3 |
| 嵌入式变量缺失 | `ValueError`（同上） | preprocessor Phase 3 |

**Fail-fast 原则**：所有异常在 preprocessor 阶段抛出，**不会**在执行期出现"expected=None"这类误导性失败。

---

## 11. 测试计划

### 11.1 单元测试（`tests/unit/generator/`）

| 文件 | 测试目标 | 关键用例 |
|------|---------|---------|
| `test_specs.py` | 7 个 Spec 的 Pydantic 校验 | `extra="forbid"` 拼写错误 / `ge`/`le` 越界 / 联合体按 `kind` 分发 |
| `test_functions.py` | 7 个生成函数的纯函数行为 | 长度恒定 / 字符集正确 / 1000 次抽样在区间内 / format 正确 |
| `test_registry.py` | 注册表 register / get / 不存在报错 | 重复 register 报错 / `get("nonexistent")` 返回 None |
| `test_engine.py` | Generator.generate / generate_all / 错误透传 | 错误包装保留 traceback / 批量求值独立 |
| `test_exceptions.py` | 异常类型 | `UnknownGeneratorError.kind` 属性 / `GeneratorError` 包装 |

**`test_functions.py` 详细用例**：

- `uuid` 返回 32 位 hex（pattern `^[0-9a-f]{32}$`）
- `random_str(length=10)` 长度恒为 10
- `random_str(charset="digit")` 全部为数字
- `random_str(charset="alpha")` 全为字母
- `random_int(5, 10)` 1000 次抽样都在 [5, 10] 内
- `random_int(min=5, max=5)` 恒为 5
- `random_decimal(places=2)` 小数位 ≤ 2
- `random_decimal(min=10, max=5)` 抛 `ValueError`
- `timestamp(format="epoch")` 返回 int
- `timestamp(format="iso")` 匹配 ISO 8601 pattern
- `timestamp(offset_seconds=-3600)` 比 `offset_seconds=0` 小 3600
- `now()` 忽略 offset（与 `timestamp(offset=0)` 等价）
- `seq(start=1, width=4)` 第一次返回 `"0001"`，第二次返回 `"0002"`
- `seq(prefix="X", start=100)` 第一次返回 `"X000100"`（width 默认 6）

### 11.2 集成测试（`tests/integration/test_preprocessor_vars.py`）

| 场景 | 验证点 |
|------|--------|
| Scenario 含 `vars` 声明（生成式） | 解析后 `${var.x}` 拿到生成值 |
| Scenario 含 `vars` 字面量 | 解析后 `${var.x}` 等于字面量 |
| Scenario 与 CLI 都定义同名 var | CLI 赢 |
| Scenario 含不合法的 spec | 抛 `GeneratorError` / `ValidationError`（fail-fast） |
| 字面量与生成式混用 | 各自正确处理 |
| 多次执行同一 scenario | 每次生成新值（独立性） |
| `vars` 字段在 scenario JSON 中省略 | 不影响其他阶段，root["var"] 为空 |
| `${var.x}` 类型保真 | int/float/bool/str 在 body 中保持类型 |

### 11.3 E2E 验证

修改 [`src/gimbal/cli/commands/e2e.json`](../../cli/commands/e2e.json)：把至少 5 处硬编码 `"bl_no":"codfishe2e24"` 替换为 `"${var.bl_no}"`，并加：

```json
"config": {
  "vars": {
    "bl_no":  { "kind": "random_str",    "length": 12, "charset": "alnum" },
    "etd":    { "kind": "timestamp",     "format": "epoch" },
    "weight": { "kind": "random_decimal","min": 50,    "max": 200,  "places": 2 }
  }
}
```

跑 `gimbal run scenario e2e.json`，确认：

- 5 处 bl_no 都展开为同一随机串
- etd 是 int（不是 string）
- weight 是 float
- 5 处 bl_no 与 voy / ship_name / customer_order_sn 等其他共享字段值一致

---

## 12. 实施影响范围

| 文件 | 改动类型 | 估算行数 |
|------|---------|---------|
| **新增** `src/gimbal/generator/__init__.py` | 新建 | ~10 |
| **新增** `src/gimbal/generator/specs.py` | 新建 | ~75 |
| **新增** `src/gimbal/generator/registry.py` | 新建 | ~40 |
| **新增** `src/gimbal/generator/functions.py` | 新建 | ~80 |
| **新增** `src/gimbal/generator/engine.py` | 新建 | ~50 |
| **新增** `src/gimbal/generator/exceptions.py` | 新建 | ~15 |
| **新增** `tests/unit/generator/test_specs.py` | 新建 | ~150 |
| **新增** `tests/unit/generator/test_functions.py` | 新建 | ~200 |
| **新增** `tests/unit/generator/test_registry.py` | 新建 | ~50 |
| **新增** `tests/unit/generator/test_engine.py` | 新建 | ~80 |
| **新增** `tests/integration/test_preprocessor_vars.py` | 新建 | ~150 |
| [src/gimbal/config/models.py](../../config/models.py) | 改 | +5 |
| [src/gimbal/schema/scenario.py](../../schema/scenario.py) | 改 | +10 |
| [src/gimbal/core/bootstrap.py](../../core/bootstrap.py) | 改 | +5 |
| [src/gimbal/preprocessor/scenario_preprocessor.py](../../preprocessor/scenario_preprocessor.py) | 改 | +40（Phase 1.5 + root 合并） |
| [docs/modules/preprocessor.md](../../modules/preprocessor.md) | 改 | +30（Phase 1.5 描述） |
| **新增** `docs/modules/generator.md` | 新建 | ~80 |
| `e2e.json` 验证 | 改 | ~10 处替换 |

**总计**：新建 ~10 个文件、修改 5 个文件。

---

## 13. 关键设计取舍小结

| 决定 | 理由 |
|------|------|
| 7 个 Spec 各自独立 + discriminated union | 与项目现有 `StepUnion` / `ApiUnion` 风格一致 |
| `extra="forbid"` | 拼写错误立即报错，避免"加了字段不生效"的 debug 痛苦 |
| `vars` 字段类型 `dict[str, Any]` | 容器内每一项运行时判定（生成式/字面量），不在 schema 层做深度校验 |
| `BootstrapConfig.generator` 引用实例 | 构造一次、preprocessor 只用不创建，便于将来扩展 |
| Generator 接收 `VarSpec`（已校验）实例 | 职责单一：specs 负责校验，engine 负责求值 |
| 字面量不进 Spec | 字面量是 Pydantic 已支持的 primitive，不需要包成"kind=literal" |
| 错误透传 + 包装 | 函数原始异常被 `GeneratorError` 包装，保留 traceback |
| 不引入种子 | 每次 run 独立；YAGNI |
| `seq` 用模块级 dict 作计数器 | 简单、run 内单进程足够；多进程/分布式场景留未来 |
| `${var.x}` 模板语法零改动 | 复用现有 `_get_nested` + `resolve_template_strict`，最小爆炸半径 |

---

## 14. 未来扩展（不在本次范围）

- 模板层函数式语法（`${var.x | func(args)}`）—— 通过重构模板解析器实现
- 变量间引用（`bl_no = "${prefix}-${suffix}"`）—— 依赖图求解
- seed 机制（确定性重试 / 复现 bug）
- 外部 faker 库集成（`faker.profile()` 等）
- 自定义 generator 通过插件注册
- var 在 reporter 中可视化展示

---

## 15. 参考

- [docs/architecture.md §3 Schema 数据模型](../../architecture.md)
- [docs/architecture.md §7 Discriminated Union](../../architecture.md)
- [docs/modules/preprocessor.md Phase 3 模板展开](../../modules/preprocessor.md)
- [src/gimbal/utils/jsonpath.py resolve_template_strict](../../utils/jsonpath.py)
- [src/gimbal/preprocessor/scenario_preprocessor.py](../../preprocessor/scenario_preprocessor.py)
- [src/gimbal/config/models.py BootstrapConfig](../../config/models.py)
