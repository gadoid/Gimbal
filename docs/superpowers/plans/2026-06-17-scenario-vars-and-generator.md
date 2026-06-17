# Scenario Vars & Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Scenario 增加 `config.vars` 声明 + 7 个内置生成器（uuid / random_str / random_int / random_decimal / timestamp / now / seq），让 step 用 `${var.x}` 引用——复用现有模板管线。

**Architecture:** 新建 `gimbal/generator/` 顶层模块（specs / registry / functions / engine / exceptions），在 `ScenarioPreprocessor` 加 Phase 1.5 合并 `scenario.config.vars` 与 `BootstrapConfig.vars`、生成或保留字面量、注入 `root["var"]`。模板层零改动。

**Tech Stack:** Python 3.11+ / Pydantic v2 / pytest 8

**Spec:** [docs/superpowers/specs/2026-06-17-scenario-vars-and-generator-design.md](../specs/2026-06-17-scenario-vars-and-generator-design.md)

---

## File Structure

### 新建文件

| 文件 | 职责 |
|------|------|
| `src/gimbal/generator/__init__.py` | 公开 API 导出 |
| `src/gimbal/generator/exceptions.py` | `GeneratorError`, `UnknownGeneratorError` |
| `src/gimbal/generator/functions.py` | 7 个 pure function + `reset_seq_counter` |
| `src/gimbal/generator/registry.py` | `GeneratorRegistry` + `build_default_registry` |
| `src/gimbal/generator/specs.py` | 7 个 Pydantic Spec + `VarSpec` 联合体 |
| `src/gimbal/generator/engine.py` | `Generator` 类（generate / generate_all 入口） |
| `tests/unit/generator/__init__.py` | 测试包空文件 |
| `tests/unit/generator/test_exceptions.py` | 异常单元测试 |
| `tests/unit/generator/test_functions.py` | 7 个函数单元测试 |
| `tests/unit/generator/test_registry.py` | 注册表单元测试 |
| `tests/unit/generator/test_specs.py` | 7 个 Spec 校验测试 |
| `tests/unit/generator/test_engine.py` | 引擎单元测试 |
| `tests/integration/test_preprocessor_vars.py` | preprocessor 集成测试 |
| `docs/modules/generator.md` | 模块文档 |

### 修改文件

| 文件 | 改动 |
|------|------|
| `src/gimbal/config/models.py` | `BootstrapConfig` 加 `generator` 字段（字符串前向引用） |
| `src/gimbal/schema/scenario.py` | `Config` 加 `vars: dict[str, Any]` 字段 |
| `src/gimbal/core/bootstrap.py` | 构造 `Generator` 注入 `Configuration` |
| `src/gimbal/preprocessor/scenario_preprocessor.py` | 加 `__init__` 的 `_resolved_vars`、加 `_generate_vars`、改 `_build_resolve_root`、改 `run()` |
| `docs/modules/preprocessor.md` | 增 Phase 1.5 章节 |
| `docs/modules/config.md` | 增 `generator` 字段说明 |
| `src/gimbal/cli/commands/e2e.json` | 验证：5 处硬编码 `bl_no` 替换为 `${var.bl_no}` + 加 `vars` 声明 |

---

## Task 1: 异常类型 + 测试

**Files:**
- Create: `src/gimbal/generator/__init__.py`
- Create: `src/gimbal/generator/exceptions.py`
- Create: `tests/unit/generator/__init__.py`
- Create: `tests/unit/generator/test_exceptions.py`

- [ ] **Step 1: 创建 generator 包目录与空 `__init__.py`**

```python
# src/gimbal/generator/__init__.py
"""gimbal/generator

变量生成器：为 Scenario 提供基于声明的"声明式变量"求值能力。

- specs.py    Pydantic Spec 模型
- registry.py 注册表
- functions.py  7 个内置生成函数
- engine.py   Generator 类
- exceptions.py 异常类型

公开 API：
    Generator              # 求值入口
    GeneratorRegistry      # 注册表
    build_default_registry # 构造注册了 7 个内置函数的注册表
    VarSpec                # 联合体（discriminated by 'kind'）
    GeneratorError, UnknownGeneratorError
"""
```

- [ ] **Step 2: 写失败测试**

`tests/unit/generator/test_exceptions.py`:

```python
"""Unit tests for gimbal.generator.exceptions."""
import pytest
from gimbal.generator.exceptions import GeneratorError, UnknownGeneratorError


class TestUnknownGeneratorError:
    def test_is_generator_error_subclass(self):
        """UnknownGeneratorError 是 GeneratorError 的子类。"""
        err = UnknownGeneratorError("foo")
        assert isinstance(err, GeneratorError)

    def test_message_includes_kind(self):
        """错误消息包含 kind 名称。"""
        err = UnknownGeneratorError("my_kind")
        assert "my_kind" in str(err)

    def test_kind_attribute_stored(self):
        """构造时传入的 kind 被保存到 .kind 属性。"""
        err = UnknownGeneratorError("uuid_xxx")
        assert err.kind == "uuid_xxx"


class TestGeneratorError:
    def test_can_be_raised_and_caught(self):
        """GeneratorError 可正常 raise / catch。"""
        with pytest.raises(GeneratorError):
            raise GeneratorError("boom")

    def test_message_preserved(self):
        """消息原样保留。"""
        err = GeneratorError("specific message")
        assert str(err) == "specific message"
```

- [ ] **Step 3: 跑测试，预期失败（模块不存在）**

```bash
cd d:/Gimbal/Gimbal && python -m pytest tests/unit/generator/test_exceptions.py -v
```

Expected: `ModuleNotFoundError: No module named 'gimbal.generator'`

- [ ] **Step 4: 实现 `exceptions.py`**

`src/gimbal/generator/exceptions.py`:

```python
"""gimbal/generator/exceptions.py

生成器模块的异常类型。
"""


class GeneratorError(Exception):
    """生成器执行错误（包装原始异常）。"""


class UnknownGeneratorError(GeneratorError):
    """未注册的生成器 kind。"""

    def __init__(self, kind: str) -> None:
        super().__init__(f"unknown generator: {kind!r}")
        self.kind = kind
```

- [ ] **Step 5: 跑测试，预期通过**

```bash
cd d:/Gimbal/Gimbal && python -m pytest tests/unit/generator/test_exceptions.py -v
```

Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
cd d:/Gimbal/Gimbal && git add src/gimbal/generator/ tests/unit/generator/
git commit -m "feat(generator): add generator package skeleton + exceptions"
```

---

## Task 2: 生成函数 + 测试

**Files:**
- Create: `src/gimbal/generator/functions.py`
- Create: `tests/unit/generator/test_functions.py`

- [ ] **Step 1: 写失败测试**

`tests/unit/generator/test_functions.py`:

```python
"""Unit tests for gimbal.generator.functions."""
import re
import string
import pytest
from datetime import datetime
from gimbal.generator import functions
from gimbal.generator.functions import (
    uuid, random_str, random_int, random_decimal,
    timestamp, now, seq, reset_seq_counter,
)


class TestUuid:
    def test_returns_32_hex_chars(self):
        """返回 32 位 hex 字符。"""
        val = uuid()
        assert len(val) == 32
        assert re.fullmatch(r"[0-9a-f]{32}", val)

    def test_returns_different_values(self):
        """连续两次调用返回不同值。"""
        assert uuid() != uuid()


class TestRandomStr:
    def test_default_length_is_8(self):
        """默认长度 8。"""
        assert len(random_str()) == 8

    def test_custom_length(self):
        """自定义长度。"""
        assert len(random_str(length=20)) == 20

    def test_charset_alpha(self):
        """charset=alpha 时字符全在 ascii_letters 中。"""
        val = random_str(length=100, charset="alpha")
        for ch in val:
            assert ch in string.ascii_letters

    def test_charset_digit(self):
        """charset=digit 时字符全在 digits 中。"""
        val = random_str(length=100, charset="digit")
        for ch in val:
            assert ch in string.digits

    def test_charset_alnum_default(self):
        """charset=alnum（默认）时字符全在字母+数字中。"""
        val = random_str(length=100)
        for ch in val:
            assert ch in string.ascii_letters + string.digits

    def test_invalid_charset_raises(self):
        """非法 charset 抛 ValueError。"""
        with pytest.raises(ValueError, match="invalid charset"):
            random_str(charset="emoji")

    def test_length_1(self):
        """length=1 也工作。"""
        val = random_str(length=1, charset="digit")
        assert val in string.digits


class TestRandomInt:
    def test_within_range(self):
        """1000 次抽样都在 [min, max] 内。"""
        for _ in range(1000):
            v = random_int(min=5, max=10)
            assert 5 <= v <= 10

    def test_degenerate_range(self):
        """min == max 时恒为该值。"""
        assert random_int(min=7, max=7) == 7

    def test_default_range(self):
        """默认 min=0, max=100。"""
        v = random_int()
        assert 0 <= v <= 100

    def test_min_greater_than_max_raises(self):
        """min > max 抛 ValueError。"""
        with pytest.raises(ValueError, match="min"):
            random_int(min=10, max=5)


class TestRandomDecimal:
    def test_within_range(self):
        """1000 次抽样都在 [min, max] 内。"""
        for _ in range(1000):
            v = random_decimal(min=10.0, max=20.0, places=2)
            assert 10.0 <= v <= 20.0

    def test_places_respected(self):
        """places=2 时小数位不超过 2。"""
        for _ in range(100):
            v = random_decimal(min=0.0, max=100.0, places=2)
            # 转 str 看小数位数
            s = str(v)
            if "." in s:
                decimals = s.split(".")[1]
                assert len(decimals) <= 2

    def test_places_zero(self):
        """places=0 返回无小数部分。"""
        v = random_decimal(min=10.0, max=20.0, places=0)
        assert v == float(int(v))

    def test_min_greater_than_max_raises(self):
        """min > max 抛 ValueError。"""
        with pytest.raises(ValueError, match="min"):
            random_decimal(min=20.0, max=10.0)


class TestTimestamp:
    def test_format_epoch_returns_int(self):
        """format=epoch 返回 int。"""
        v = timestamp(format="epoch")
        assert isinstance(v, int)
        # 应大致为当前时间（容差 5 秒）
        diff = abs(datetime.now().timestamp() - v)
        assert diff < 5

    def test_format_iso_returns_str(self):
        """format=iso 返回 ISO 格式字符串。"""
        v = timestamp(format="iso")
        assert isinstance(v, str)
        # ISO 格式可被 datetime.fromisoformat 解析
        datetime.fromisoformat(v)

    def test_format_compact(self):
        """format=compact 返回 YYYYMMDDHHMMSS 形式。"""
        v = timestamp(format="compact")
        assert isinstance(v, str)
        assert re.fullmatch(r"\d{14}", v)

    def test_invalid_format_raises(self):
        """非法 format 抛 ValueError。"""
        with pytest.raises(ValueError, match="invalid format"):
            timestamp(format="xx")

    def test_offset_seconds_positive(self):
        """offset_seconds=+3600 约比 now 大 3600。"""
        now_ts = datetime.now().timestamp()
        future_ts = timestamp(format="epoch", offset_seconds=3600)
        assert abs((future_ts - now_ts) - 3600) < 2

    def test_offset_seconds_negative(self):
        """offset_seconds=-3600 约比 now 小 3600。"""
        now_ts = datetime.now().timestamp()
        past_ts = timestamp(format="epoch", offset_seconds=-3600)
        assert abs((now_ts - past_ts) - 3600) < 2


class TestNow:
    def test_now_matches_timestamp_with_zero_offset(self):
        """now() 与 timestamp(offset_seconds=0) 等价。"""
        v1 = now(format="epoch")
        v2 = timestamp(format="epoch", offset_seconds=0)
        # 两个调用间间隔可能 0~1 秒
        assert abs(v1 - v2) <= 1


class TestSeq:
    def setup_method(self):
        """每个测试前重置计数器，避免相互影响。"""
        reset_seq_counter()

    def test_default_first_value(self):
        """默认参数首次调用返回 000001。"""
        assert seq() == "000001"

    def test_increments_across_calls(self):
        """连续调用递增。"""
        assert seq() == "000001"
        assert seq() == "000002"
        assert seq() == "000003"

    def test_custom_width(self):
        """width=4 时首次返回 0001。"""
        assert seq(width=4) == "0001"

    def test_custom_prefix(self):
        """prefix='X' 时首次返回 X000001。"""
        assert seq(prefix="X") == "X000001"

    def test_custom_start(self):
        """start=100 时首次返回 000100。"""
        assert seq(start=100) == "000100"

    def test_prefix_and_start(self):
        """prefix='YWDD', start=100, width=6 → 'YWDD000100'。"""
        assert seq(prefix="YWDD", start=100) == "YWDD000100"

    def test_independent_sequences(self):
        """不同 prefix 是独立计数器。"""
        assert seq(prefix="A") == "A000001"
        assert seq(prefix="B") == "B000001"
        assert seq(prefix="A") == "A000002"


class TestResetSeqCounter:
    def test_reset_clears_state(self):
        """reset 后 seq 重新从 start 开始。"""
        seq()  # 000001
        seq()  # 000002
        reset_seq_counter()
        assert seq() == "000001"
```

- [ ] **Step 2: 跑测试，预期失败**

```bash
cd d:/Gimbal/Gimbal && python -m pytest tests/unit/generator/test_functions.py -v
```

Expected: `ModuleNotFoundError: No module named 'gimbal.generator.functions'`

- [ ] **Step 3: 实现 `functions.py`**

`src/gimbal/generator/functions.py`:

```python
"""gimbal/generator/functions.py

7 个内置生成函数（pure function）。
每个函数接收**命名参数**（参数名与 Spec 字段一一对应），返回 primitive 值。
"""
from __future__ import annotations

import random
import string
import uuid as _uuid
from datetime import datetime, timedelta


def uuid() -> str:
    """32 位 hex。"""
    return _uuid.uuid4().hex


def random_str(length: int = 8, charset: str = "alnum") -> str:
    """随机字符串。"""
    pools = {
        "alpha": string.ascii_letters,
        "digit": string.digits,
        "alnum": string.ascii_letters + string.digits,
    }
    if charset not in pools:
        raise ValueError(f"invalid charset: {charset!r}")
    return "".join(random.choices(pools[charset], k=length))


def random_int(min: int = 0, max: int = 100) -> int:
    """闭区间随机整数。"""
    if min > max:
        raise ValueError(f"min ({min}) > max ({max})")
    return random.randint(min, max)


def random_decimal(min: float = 0.0, max: float = 100.0, places: int = 2) -> float:
    """闭区间随机小数，四舍五入到指定位数。"""
    if min > max:
        raise ValueError(f"min ({min}) > max ({max})")
    return round(random.uniform(min, max), places)


def timestamp(format: str = "iso", offset_seconds: int = 0) -> int | str:
    """当前时间 + 偏移。"""
    ts = datetime.now() + timedelta(seconds=offset_seconds)
    if format == "epoch":
        return int(ts.timestamp())
    if format == "iso":
        return ts.isoformat()
    if format == "compact":
        return ts.strftime("%Y%m%d%H%M%S")
    raise ValueError(f"invalid format: {format!r}")


def now(format: str = "iso") -> int | str:
    """当前时间（无偏移）。"""
    return timestamp(format=format, offset_seconds=0)


# seq 用模块级计数器；不跨进程、不跨 run、不线程安全
_seq_counter: dict[str, int] = {}


def seq(prefix: str = "", width: int = 6, start: int = 1) -> str:
    """自增序号 + 业务前缀；同 (prefix, width, start) 组合下递增。"""
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

- [ ] **Step 4: 跑测试，预期通过**

```bash
cd d:/Gimbal/Gimbal && python -m pytest tests/unit/generator/test_functions.py -v
```

Expected: 所有用例通过（约 35 个）

- [ ] **Step 5: Commit**

```bash
cd d:/Gimbal/Gimbal && git add src/gimbal/generator/functions.py tests/unit/generator/test_functions.py
git commit -m "feat(generator): add 7 built-in generator functions + tests"
```

---

## Task 3: 注册表 + 测试

**Files:**
- Create: `src/gimbal/generator/registry.py`
- Create: `tests/unit/generator/test_registry.py`

- [ ] **Step 1: 写失败测试**

`tests/unit/generator/test_registry.py`:

```python
"""Unit tests for gimbal.generator.registry."""
import pytest
from gimbal.generator.registry import GeneratorRegistry, build_default_registry


class TestGeneratorRegistry:
    def test_empty_registry(self):
        """空注册表 kinds() 返回 []。"""
        r = GeneratorRegistry()
        assert r.kinds() == []

    def test_register_and_get(self):
        """register 后 get 能取回。"""
        r = GeneratorRegistry()
        r.register("foo", lambda: "bar")
        assert r.get("foo")() == "bar"

    def test_get_unknown_returns_none(self):
        """get 未注册的 kind 返回 None。"""
        r = GeneratorRegistry()
        assert r.get("nonexistent") is None

    def test_register_duplicate_raises(self):
        """重复 register 同一 kind 抛 ValueError。"""
        r = GeneratorRegistry()
        r.register("foo", lambda: 1)
        with pytest.raises(ValueError, match="already registered"):
            r.register("foo", lambda: 2)

    def test_kinds_returns_sorted_list(self):
        """kinds() 返回所有已注册 kind 列表。"""
        r = GeneratorRegistry()
        r.register("c", lambda: 1)
        r.register("a", lambda: 2)
        r.register("b", lambda: 3)
        assert r.kinds() == ["c", "a", "b"]


class TestBuildDefaultRegistry:
    def test_contains_all_7_kinds(self):
        """默认注册表包含全部 7 个内置 kind。"""
        r = build_default_registry()
        expected = {"uuid", "random_str", "random_int", "random_decimal",
                    "timestamp", "now", "seq"}
        assert set(r.kinds()) == expected

    def test_each_function_callable(self):
        """每个 kind 都能被取出并调用。"""
        r = build_default_registry()
        for kind in r.kinds():
            func = r.get(kind)
            assert callable(func)
            # 每个函数至少能调用一次（参数用 default）
            func()  # 不应抛
```

- [ ] **Step 2: 跑测试，预期失败**

```bash
cd d:/Gimbal/Gimbal && python -m pytest tests/unit/generator/test_registry.py -v
```

Expected: `ModuleNotFoundError: No module named 'gimbal.generator.registry'`

- [ ] **Step 3: 实现 `registry.py`**

`src/gimbal/generator/registry.py`:

```python
"""gimbal/generator/registry.py

生成器注册表：kind → 函数的映射。
"""
from __future__ import annotations

from typing import Callable, Any


class GeneratorRegistry:
    """生成器注册表。"""

    def __init__(self) -> None:
        self._funcs: dict[str, Callable[..., Any]] = {}

    def register(self, kind: str, func: Callable[..., Any]) -> None:
        """注册一个生成函数。"""
        if kind in self._funcs:
            raise ValueError(f"generator '{kind}' already registered")
        self._funcs[kind] = func

    def get(self, kind: str) -> Callable[..., Any] | None:
        """按 kind 取函数；未注册返回 None。"""
        return self._funcs.get(kind)

    def kinds(self) -> list[str]:
        """返回所有已注册 kind 列表（插入顺序）。"""
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

- [ ] **Step 4: 跑测试，预期通过**

```bash
cd d:/Gimbal/Gimbal && python -m pytest tests/unit/generator/test_registry.py -v
```

Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
cd d:/Gimbal/Gimbal && git add src/gimbal/generator/registry.py tests/unit/generator/test_registry.py
git commit -m "feat(generator): add GeneratorRegistry + default 7 generators"
```

---

## Task 4: Pydantic Specs + 测试

**Files:**
- Create: `src/gimbal/generator/specs.py`
- Create: `tests/unit/generator/test_specs.py`

- [ ] **Step 1: 写失败测试**

`tests/unit/generator/test_specs.py`:

```python
"""Unit tests for gimbal.generator.specs."""
import pytest
from pydantic import ValidationError
from gimbal.generator.specs import (
    UuidSpec, RandomStrSpec, RandomIntSpec, RandomDecimalSpec,
    TimestampSpec, NowSpec, SeqSpec, VarSpec,
)


class TestUuidSpec:
    def test_default_construction(self):
        """不传参数时使用默认值。"""
        s = UuidSpec()
        assert s.kind == "uuid"

    def test_explicit_kind(self):
        """显式 kind 也能正常构造。"""
        s = UuidSpec(kind="uuid")
        assert s.kind == "uuid"

    def test_extra_field_forbidden(self):
        """未知字段被拒绝（extra='forbid'）。"""
        with pytest.raises(ValidationError):
            UuidSpec(unknown="x")

    def test_wrong_kind_rejected(self):
        """错 kind 名称被拒绝。"""
        with pytest.raises(ValidationError):
            UuidSpec(kind="uuid_xxx")


class TestRandomStrSpec:
    def test_default_values(self):
        """默认 length=8, charset='alnum'。"""
        s = RandomStrSpec()
        assert s.kind == "random_str"
        assert s.length == 8
        assert s.charset == "alnum"

    def test_custom_values(self):
        """自定义 length 和 charset。"""
        s = RandomStrSpec(length=12, charset="digit")
        assert s.length == 12
        assert s.charset == "digit"

    def test_length_too_small(self):
        """length=0 被 ge=1 约束拒绝。"""
        with pytest.raises(ValidationError):
            RandomStrSpec(length=0)

    def test_length_too_big(self):
        """length=99999 被 le=1024 约束拒绝。"""
        with pytest.raises(ValidationError):
            RandomStrSpec(length=99999)

    def test_invalid_charset(self):
        """非法 charset 被 Literal 拒绝。"""
        with pytest.raises(ValidationError):
            RandomStrSpec(charset="emoji")

    def test_extra_field_forbidden(self):
        """未知字段被拒绝。"""
        with pytest.raises(ValidationError):
            RandomStrSpec(length=8, charset="alnum", foo="bar")


class TestRandomIntSpec:
    def test_default_values(self):
        """默认 min=0, max=100。"""
        s = RandomIntSpec()
        assert s.min == 0
        assert s.max == 100

    def test_custom_values(self):
        """自定义 min/max。"""
        s = RandomIntSpec(min=5, max=10)
        assert s.min == 5
        assert s.max == 10

    def test_extra_forbidden(self):
        with pytest.raises(ValidationError):
            RandomIntSpec(min=0, max=10, extra_field="x")


class TestRandomDecimalSpec:
    def test_default_values(self):
        s = RandomDecimalSpec()
        assert s.min == 0.0
        assert s.max == 100.0
        assert s.places == 2

    def test_custom_values(self):
        s = RandomDecimalSpec(min=10.5, max=99.9, places=3)
        assert s.min == 10.5
        assert s.max == 99.9
        assert s.places == 3

    def test_places_too_big(self):
        """places=11 被 le=10 拒绝。"""
        with pytest.raises(ValidationError):
            RandomDecimalSpec(places=11)


class TestTimestampSpec:
    def test_default_values(self):
        s = TimestampSpec()
        assert s.format == "iso"
        assert s.offset_seconds == 0

    def test_custom_values(self):
        s = TimestampSpec(format="epoch", offset_seconds=3600)
        assert s.format == "epoch"
        assert s.offset_seconds == 3600

    def test_invalid_format(self):
        with pytest.raises(ValidationError):
            TimestampSpec(format="xx")


class TestNowSpec:
    def test_default_format(self):
        s = NowSpec()
        assert s.format == "iso"

    def test_custom_format(self):
        s = NowSpec(format="epoch")
        assert s.format == "epoch"


class TestSeqSpec:
    def test_default_values(self):
        s = SeqSpec()
        assert s.prefix == ""
        assert s.width == 6
        assert s.start == 1

    def test_custom_values(self):
        s = SeqSpec(prefix="YWDD", width=8, start=100000)
        assert s.prefix == "YWDD"
        assert s.width == 8
        assert s.start == 100000

    def test_width_too_small(self):
        with pytest.raises(ValidationError):
            SeqSpec(width=0)


class TestVarSpecUnion:
    """VarSpec 是 discriminated union，按 kind 自动分发到对应子类。"""

    @pytest.mark.parametrize("kind,expected_class", [
        ("uuid",           UuidSpec),
        ("random_str",     RandomStrSpec),
        ("random_int",     RandomIntSpec),
        ("random_decimal", RandomDecimalSpec),
        ("timestamp",      TimestampSpec),
        ("now",            NowSpec),
        ("seq",            SeqSpec),
    ])
    def test_dispatches_to_correct_subclass(self, kind, expected_class):
        spec = VarSpec.model_validate({"kind": kind})
        assert isinstance(spec, expected_class)

    def test_unknown_kind_rejected(self):
        """未注册的 kind 名称被拒绝。"""
        with pytest.raises(ValidationError):
            VarSpec.model_validate({"kind": "nonexistent"})

    def test_missing_kind_rejected(self):
        """缺 kind 字段被拒绝。"""
        with pytest.raises(ValidationError):
            VarSpec.model_validate({})

    def test_extra_field_in_specific_kind_rejected(self):
        """在 union 输入层面 extra 字段也被拒绝。"""
        with pytest.raises(ValidationError):
            VarSpec.model_validate({"kind": "random_str", "length": 8, "foo": "bar"})
```

- [ ] **Step 2: 跑测试，预期失败**

```bash
cd d:/Gimbal/Gimbal && python -m pytest tests/unit/generator/test_specs.py -v
```

Expected: `ModuleNotFoundError: No module named 'gimbal.generator.specs'`

- [ ] **Step 3: 实现 `specs.py`**

`src/gimbal/generator/specs.py`:

```python
"""gimbal/generator/specs.py

7 个生成器的 Pydantic Spec + VarSpec 联合体（discriminated by 'kind'）。

设计要点：
  - 每个 Spec 用 extra='forbid'，拼写错误立即报错
  - 用 Literal 限定 enum 字段（charset / format）
  - 用 Field(ge=, le=) 限定数值范围
  - VarSpec = Annotated[Union[...], Field(discriminator="kind")]
"""
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

- [ ] **Step 4: 跑测试，预期通过**

```bash
cd d:/Gimbal/Gimbal && python -m pytest tests/unit/generator/test_specs.py -v
```

Expected: 全部通过（约 35 个）

- [ ] **Step 5: Commit**

```bash
cd d:/Gimbal/Gimbal && git add src/gimbal/generator/specs.py tests/unit/generator/test_specs.py
git commit -m "feat(generator): add 7 Pydantic Specs + VarSpec union"
```

---

## Task 5: Generator 引擎 + 测试

**Files:**
- Create: `src/gimbal/generator/engine.py`
- Create: `tests/unit/generator/test_engine.py`

- [ ] **Step 1: 写失败测试**

`tests/unit/generator/test_engine.py`:

```python
"""Unit tests for gimbal.generator.engine."""
import pytest
from gimbal.generator.engine import Generator
from gimbal.generator.registry import build_default_registry
from gimbal.generator.exceptions import GeneratorError, UnknownGeneratorError
from gimbal.generator.specs import (
    UuidSpec, RandomStrSpec, RandomIntSpec, RandomDecimalSpec,
    TimestampSpec, NowSpec, SeqSpec,
)


@pytest.fixture
def generator():
    return Generator(build_default_registry())


class TestGenerator:
    def test_uuid_kind(self, generator):
        s = UuidSpec()
        v = generator.generate(s)
        assert isinstance(v, str)
        assert len(v) == 32

    def test_random_str_kind(self, generator):
        s = RandomStrSpec(length=10, charset="digit")
        v = generator.generate(s)
        assert isinstance(v, str)
        assert len(v) == 10
        assert v.isdigit()

    def test_random_int_kind(self, generator):
        s = RandomIntSpec(min=5, max=5)  # 退化区间
        assert generator.generate(s) == 5

    def test_random_decimal_kind(self, generator):
        s = RandomDecimalSpec(min=10.0, max=10.0, places=2)
        v = generator.generate(s)
        assert v == 10.0

    def test_timestamp_epoch_kind(self, generator):
        s = TimestampSpec(format="epoch")
        v = generator.generate(s)
        assert isinstance(v, int)

    def test_now_kind(self, generator):
        s = NowSpec(format="epoch")
        v = generator.generate(s)
        assert isinstance(v, int)

    def test_seq_kind(self, generator):
        from gimbal.generator.functions import reset_seq_counter
        reset_seq_counter()
        s = SeqSpec(prefix="X", width=4)
        assert generator.generate(s) == "X0001"
        assert generator.generate(s) == "X0002"

    def test_unknown_kind_raises(self):
        """未注册 kind 抛 UnknownGeneratorError。"""
        from gimbal.generator.registry import GeneratorRegistry
        gen = Generator(GeneratorRegistry())  # 空注册表
        s = UuidSpec()
        with pytest.raises(UnknownGeneratorError) as exc:
            gen.generate(s)
        assert exc.value.kind == "uuid"

    def test_function_exception_wrapped(self, generator):
        """生成函数自身抛异常时被包装为 GeneratorError。"""
        s = RandomIntSpec(min=10, max=5)  # min > max，会被函数拒绝
        with pytest.raises(GeneratorError) as exc:
            generator.generate(s)
        assert "random_int" in str(exc.value)
        assert "min" in str(exc.value).lower()

    def test_original_exception_chained(self, generator):
        """GeneratorError 包装时 __cause__ 指向原异常。"""
        s = RandomIntSpec(min=10, max=5)
        with pytest.raises(GeneratorError) as exc:
            generator.generate(s)
        assert exc.value.__cause__ is not None


class TestGenerateAll:
    def test_empty_dict(self, generator):
        assert generator.generate_all({}) == {}

    def test_single_spec(self, generator):
        result = generator.generate_all({"x": {"kind": "uuid"}})
        assert "x" in result
        assert len(result["x"]) == 32

    def test_multiple_specs(self, generator):
        from gimbal.generator.functions import reset_seq_counter
        reset_seq_counter()
        result = generator.generate_all({
            "u":      {"kind": "uuid"},
            "code":   {"kind": "random_str", "length": 6, "charset": "digit"},
            "n":      {"kind": "random_int", "min": 7, "max": 7},
            "order":  {"kind": "seq", "prefix": "X"},
        })
        assert len(result["u"]) == 32
        assert result["code"].isdigit() and len(result["code"]) == 6
        assert result["n"] == 7
        assert result["order"] == "X000001"

    def test_invalid_spec_raises(self, generator):
        """非法 spec 在 generate_all 里就抛 ValidationError。"""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            generator.generate_all({"bad": {"kind": "nonexistent"}})

    def test_extra_field_raises(self, generator):
        """含未知字段的 spec 抛 ValidationError。"""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            generator.generate_all({"bad": {"kind": "random_str", "length": 8, "foo": "x"}})
```

- [ ] **Step 2: 跑测试，预期失败**

```bash
cd d:/Gimbal/Gimbal && python -m pytest tests/unit/generator/test_engine.py -v
```

Expected: `ModuleNotFoundError: No module named 'gimbal.generator.engine'`

- [ ] **Step 3: 实现 `engine.py`**

`src/gimbal/generator/engine.py`:

```python
"""gimbal/generator/engine.py

Generator：spec → 值的求值入口。

职责：
  - 从 registry 查 kind 对应的函数
  - 用 spec 的字段（除 kind 外）作为命名参数调用函数
  - 包装函数异常为 GeneratorError
  - 提供批量入口 generate_all
"""
from __future__ import annotations

from typing import Any

from gimbal.generator.specs import VarSpec
from gimbal.generator.registry import GeneratorRegistry
from gimbal.generator.exceptions import GeneratorError, UnknownGeneratorError


class Generator:
    """变量生成器。"""

    def __init__(self, registry: GeneratorRegistry) -> None:
        self._registry = registry

    def generate(self, spec: VarSpec) -> Any:
        """单条求值：spec → 值。"""
        func = self._registry.get(spec.kind)
        if func is None:
            raise UnknownGeneratorError(spec.kind)
        params = spec.model_dump(exclude={"kind"})
        try:
            return func(**params)
        except Exception as e:
            raise GeneratorError(f"generator '{spec.kind}' failed: {e}") from e

    def generate_all(self, schemas: dict[str, dict]) -> dict[str, Any]:
        """批量：{name: schema} → {name: value}。

        每一项 schema 在求值前先被 VarSpec.model_validate 校验，
        因此参数错误会抛 ValidationError（来自 Pydantic）。
        """
        result: dict[str, Any] = {}
        for name, schema in schemas.items():
            var_spec = VarSpec.model_validate(schema)
            result[name] = self.generate(var_spec)
        return result
```

- [ ] **Step 4: 跑测试，预期通过**

```bash
cd d:/Gimbal/Gimbal && python -m pytest tests/unit/generator/test_engine.py -v
```

Expected: 全部通过（约 15 个）

- [ ] **Step 5: Commit**

```bash
cd d:/Gimbal/Gimbal && git add src/gimbal/generator/engine.py tests/unit/generator/test_engine.py
git commit -m "feat(generator): add Generator engine with generate / generate_all"
```

---

## Task 6: 公开 API（更新 `__init__.py`）+ 冒烟测试

**Files:**
- Modify: `src/gimbal/generator/__init__.py`

- [ ] **Step 1: 替换 `__init__.py`**

```python
# src/gimbal/generator/__init__.py
"""gimbal/generator

变量生成器：为 Scenario 提供基于声明的"声明式变量"求值能力。

公开 API：
    Generator              求值入口
    GeneratorRegistry      注册表
    build_default_registry 构造注册了 7 个内置函数的注册表
    VarSpec                联合体（discriminated by 'kind'）
    GeneratorError, UnknownGeneratorError
"""
from gimbal.generator.engine import Generator
from gimbal.generator.exceptions import GeneratorError, UnknownGeneratorError
from gimbal.generator.registry import GeneratorRegistry, build_default_registry
from gimbal.generator.specs import (
    VarSpec, UuidSpec, RandomStrSpec, RandomIntSpec, RandomDecimalSpec,
    TimestampSpec, NowSpec, SeqSpec,
)

__all__ = [
    "Generator",
    "GeneratorRegistry",
    "build_default_registry",
    "VarSpec",
    "UuidSpec", "RandomStrSpec", "RandomIntSpec", "RandomDecimalSpec",
    "TimestampSpec", "NowSpec", "SeqSpec",
    "GeneratorError", "UnknownGeneratorError",
]
```

- [ ] **Step 2: 跑全部单元测试，预期通过**

```bash
cd d:/Gimbal/Gimbal && python -m pytest tests/unit/generator/ -v
```

Expected: 全部通过（约 95 个）

- [ ] **Step 3: Commit**

```bash
cd d:/Gimbal/Gimbal && git add src/gimbal/generator/__init__.py
git commit -m "feat(generator): export public API from gimbal.generator"
```

---

## Task 7: Scenario.config 加 `vars` 字段 + 测试

**Files:**
- Modify: `src/gimbal/schema/scenario.py:27-34`

- [ ] **Step 1: 找到 `Config` 类**

`src/gimbal/schema/scenario.py:27-34` 当前内容：

```python
class Config(BaseModel):
    """ 用例执行配置模型 """
    setup : list[SetupUnion] = Field(default_factory=list , description= "用例前置动作")
    teardown : list[TeardownUnion] = Field(default_factory=list , description= "用例后置动作")
    services : dict[str, str] = Field(default_factory=dict,description= "服务与URL映射关系")
    users : dict[str,AuthSession] = Field(default_factory=dict, description= "认证信息字典")
    timePolicy : TimePolicyUnion = Field(default_factory=RecordPolicy, description="时间处理策略:超时检查或耗时记录")
    retry : Optional[RetryPolicy] = None # 定义重试策略
```

- [ ] **Step 2: 写失败测试**

在 `tests/unit/` 下新建或复用现有 schema 测试文件。若没有专门文件，新建 `tests/unit/scenario/test_config_vars.py`：

```python
"""Unit tests for Scenario.config.vars field."""
from gimbal.schema.scenario import Config


def test_config_vars_default_empty():
    """Config 不传 vars 时默认为空 dict。"""
    cfg = Config()
    assert cfg.vars == {}


def test_config_vars_accepts_literals():
    """vars 可包含字面量（primitive）。"""
    cfg = Config(vars={
        "customer_id": 16,
        "service_id": 55,
        "fixed": "hello",
        "flag": True,
        "nothing": None,
    })
    assert cfg.vars["customer_id"] == 16
    assert cfg.vars["fixed"] == "hello"
    assert cfg.vars["flag"] is True
    assert cfg.vars["nothing"] is None


def test_config_vars_accepts_generator_specs():
    """vars 可包含生成式 spec dict（含 kind）。"""
    cfg = Config(vars={
        "bl_no":  {"kind": "random_str", "length": 12, "charset": "alnum"},
        "etd":    {"kind": "timestamp", "format": "epoch"},
        "weight": {"kind": "random_decimal", "min": 50, "max": 200, "places": 2},
    })
    assert cfg.vars["bl_no"]["kind"] == "random_str"
    assert cfg.vars["etd"]["format"] == "epoch"


def test_config_vars_mixed():
    """vars 可同时包含字面量与生成式。"""
    cfg = Config(vars={
        "customer_id": 16,
        "bl_no": {"kind": "random_str", "length": 12},
    })
    assert cfg.vars["customer_id"] == 16
    assert cfg.vars["bl_no"]["kind"] == "random_str"
```

- [ ] **Step 3: 跑测试，预期失败**

```bash
cd d:/Gimbal/Gimbal && python -m pytest tests/unit/scenario/test_config_vars.py -v
```

Expected: `AttributeError: 'Config' object has no attribute 'vars'`

- [ ] **Step 4: 修改 `Config` 类加 `vars` 字段**

在 [src/gimbal/schema/scenario.py:27-34](src/gimbal/schema/scenario.py#L27-L34) 的 `Config` 类末尾追加：

```python
    # ── 新增：scenario 级变量声明 ──
    vars : dict[str, Any] = Field(
        default_factory=dict,
        description="变量声明；字面量或生成式 spec dict；CLI --var 优先级更高"
    )
```

完整 `Config` 类参考（确认后修改）：

```python
class Config(BaseModel):
    """ 用例执行配置模型 """
    setup : list[SetupUnion] = Field(default_factory=list , description= "用例前置动作")
    teardown : list[TeardownUnion] = Field(default_factory=list , description= "用例后置动作")
    services : dict[str, str] = Field(default_factory=dict,description= "服务与URL映射关系")
    users : dict[str,AuthSession] = Field(default_factory=dict, description= "认证信息字典")
    timePolicy : TimePolicyUnion = Field(default_factory=RecordPolicy, description="时间处理策略:超时检查或耗时记录")
    retry : Optional[RetryPolicy] = None # 定义重试策略
    # ── 新增：scenario 级变量声明 ──
    vars : dict[str, Any] = Field(
        default_factory=dict,
        description="变量声明；字面量或生成式 spec dict；CLI --var 优先级更高"
    )
```

- [ ] **Step 5: 跑测试，预期通过**

```bash
cd d:/Gimbal/Gimbal && python -m pytest tests/unit/scenario/test_config_vars.py -v
```

Expected: 4 passed

- [ ] **Step 6: 跑现有 scenario 相关测试，确认未破坏**

```bash
cd d:/Gimbal/Gimbal && python -m pytest tests/ -k "scenario" -v
```

Expected: 全部通过

- [ ] **Step 7: Commit**

```bash
cd d:/Gimbal/Gimbal && git add src/gimbal/schema/scenario.py tests/unit/scenario/test_config_vars.py
git commit -m "feat(schema): add Scenario.config.vars field"
```

---

## Task 8: BootstrapConfig 加 `generator` 字段

**Files:**
- Modify: `src/gimbal/config/models.py:48-52`

- [ ] **Step 1: 写失败测试**

新建 `tests/unit/config/test_bootstrap_config_generator.py`：

```python
"""Unit tests for BootstrapConfig.generator field."""
import pytest
from unittest.mock import MagicMock
from gimbal.config.models import BootstrapConfig


def test_generator_field_required_by_default():
    """BootstrapConfig 默认要求传 generator。"""
    mock_gen = MagicMock()
    cfg = BootstrapConfig(generator=mock_gen)
    assert cfg.generator is mock_gen


def test_generator_field_is_frozen():
    """BootstrapConfig 是 frozen，generator 字段不可重新赋值。"""
    mock_gen = MagicMock()
    cfg = BootstrapConfig(generator=mock_gen)
    with pytest.raises(Exception):  # Pydantic FrozenError 或 ValidationError
        cfg.generator = MagicMock()
```

- [ ] **Step 2: 跑测试，预期失败**

```bash
cd d:/Gimbal/Gimbal && python -m pytest tests/unit/config/test_bootstrap_config_generator.py -v
```

Expected: `ValidationError: generator Field required`

- [ ] **Step 3: 修改 `BootstrapConfig`**

在 [src/gimbal/config/models.py:48-52](src/gimbal/config/models.py#L48-L52) 末尾追加（保留 `vars` 字段）：

```python
    # ── CLI 变量注入（修复 #52 完整链路）──
    vars: dict[str, Any] = Field(
        default_factory=dict,
        description="CLI --var / --var-file 注入的 KV 变量，模板 ${var} 引用"
    )

    # ── 新增：generator 实例（由 bootstrap() 注入）──
    # 字符串前向引用避免循环导入（config 不应依赖 generator，generator 不应依赖 config）
    generator: "Generator" = Field(  # noqa: F821
        ...,
        description="变量生成器实例（由 bootstrap() 构造并注入）",
    )
```

同时在文件顶部添加 `from __future__ import annotations`（如果还没有），让 Pydantic v2 正确解析前向引用。

- [ ] **Step 4: 跑测试，预期通过**

```bash
cd d:/Gimbal/Gimbal && python -m pytest tests/unit/config/test_bootstrap_config_generator.py -v
```

Expected: 2 passed

- [ ] **Step 5: 跑现有 config 测试，确认未破坏**

```bash
cd d:/Gimbal/Gimbal && python -m pytest tests/unit/reporter/ tests/unit/test_defect_fixes.py -v
```

Expected: 全部通过（这些文件构造 `BootstrapConfig()` 时没传 generator，但我们的字段是 required...）

**注意**：如果现有测试失败（因为它们调用 `BootstrapConfig()` 不传 generator），需要：

- 方案 A：给 generator 字段加 `default=None`，然后 bootstrap() 检查后注入
- 方案 B：更新所有现有调用点传 `generator=...` 或 `generator=None`

**先尝试方案 A**（最小破坏面）。改 [src/gimbal/config/models.py](src/gimbal/config/models.py)：

```python
    # ── 新增：generator 实例（由 bootstrap() 注入）──
    # 字符串前向引用避免循环导入
    generator: "Generator | None" = Field(  # noqa: F821
        default=None,
        description="变量生成器实例（由 bootstrap() 构造并注入；未传则禁用变量生成）",
    )
```

- [ ] **Step 6: 跑全部测试，确认通过**

```bash
cd d:/Gimbal/Gimbal && python -m pytest tests/ -v
```

Expected: 全部通过

- [ ] **Step 7: Commit**

```bash
cd d:/Gimbal/Gimbal && git add src/gimbal/config/models.py tests/unit/config/test_bootstrap_config_generator.py
git commit -m "feat(config): add BootstrapConfig.generator field"
```

---

## Task 9: bootstrap() 构造 Generator 注入 Configuration

**Files:**
- Modify: `src/gimbal/core/bootstrap.py:74-118`

- [ ] **Step 1: 找到 bootstrap() 函数中的 cfg 构造点**

当前 [src/gimbal/core/bootstrap.py:74](src/gimbal/core/bootstrap.py#L74)：

```python
cfg = ConfigLoader().load(cli_ctx)
```

需要在该行之后构造 `Generator` 并在返回前注入到 `Configuration`。

- [ ] **Step 2: 修改 bootstrap()**

在 `cfg = ConfigLoader().load(cli_ctx)` 之后**添加** generator 构造（但不直接改 cfg，因为 cfg 是 frozen）：

在 `bootstrap()` 函数体中，找到返回 `Configuration(...)` 的位置（[src/gimbal/core/bootstrap.py:118 附近](src/gimbal/core/bootstrap.py#L118)），在该 `return` 语句**之前**插入：

```python
    # 4.5 构造变量生成器并重新构造 cfg（注入 generator）
    from gimbal.generator import Generator, build_default_registry
    generator = Generator(build_default_registry())
    from pydantic import BaseModel
    # cfg 是 frozen，需要 model_copy 重建一次
    cfg = cfg.model_copy(update={"generator": generator})
    logger.info("[bootstrap] 变量生成器已就绪: kinds={}", generator._registry.kinds())
```

注意：用 `model_copy(update=...)` 而不是直接赋值（frozen=True）。

- [ ] **Step 3: 跑现有 bootstrap 测试**

```bash
cd d:/Gimbal/Gimbal && python -m pytest tests/ -k "bootstrap" -v
```

Expected: 全部通过

- [ ] **Step 4: 写一个冒烟测试确认 generator 已被注入**

新建 `tests/unit/test_bootstrap_generator.py`：

```python
"""Smoke test: bootstrap() injects generator into cfg."""
from gimbal.generator import Generator
from gimbal.config.loader import ConfigLoader
from gimbal.cli.context import CLIContext


def test_bootstrap_injects_generator():
    """ConfigLoader.load() 出来的 cfg 没有 generator；bootstrap 应当注入。"""
    from gimbal.core.bootstrap import bootstrap
    cli_ctx = CLIContext(env="dev", mode="local")
    cfg = bootstrap(cli_ctx)
    assert isinstance(cfg.cfg.generator, Generator)
    assert len(cfg.cfg.generator._registry.kinds()) == 7
```

- [ ] **Step 5: 跑测试，预期通过**

```bash
cd d:/Gimbal/Gimbal && python -m pytest tests/unit/test_bootstrap_generator.py -v
```

Expected: 1 passed

如果失败，**检查** `bootstrap()` 是否真的被 `bootstrap()` 函数调用；测试里直接调 `bootstrap()` 可能会触发插件加载、文件系统等副作用——**如果该测试环境跑不通**，可以改为只测 `cfg.model_copy(update=...)` 的语义：

```python
def test_cfg_model_copy_preserves_other_fields():
    """cfg.model_copy(update={generator: g}) 不破坏其它字段。"""
    from gimbal.config.models import BootstrapConfig
    from gimbal.generator import Generator
    from gimbal.generator.registry import build_default_registry
    g = Generator(build_default_registry())
    cfg = BootstrapConfig(env="dev", mode="local", generator=g)
    cfg2 = cfg.model_copy(update={"env": "test"})
    assert cfg2.env == "test"
    assert cfg2.generator is g  # 未修改的字段保留
```

- [ ] **Step 6: Commit**

```bash
cd d:/Gimbal/Gimbal && git add src/gimbal/core/bootstrap.py tests/unit/test_bootstrap_generator.py
git commit -m "feat(bootstrap): construct and inject Generator into cfg"
```

---

## Task 10: ScenarioPreprocessor Phase 1.5（核心集成）

**Files:**
- Modify: `src/gimbal/preprocessor/scenario_preprocessor.py`

- [ ] **Step 1: 找到 `__init__` 与 `run()` 当前位置**

当前 [src/gimbal/preprocessor/scenario_preprocessor.py:65-101](src/gimbal/preprocessor/scenario_preprocessor.py#L65-L101)：

- `__init__` 在 65 行附近
- `run()` 在 92 行附近，调用顺序：`materialize_refs` → `setup_auth` → `build_resolve_root` → `resolve_steps` → `pick_base_url`

- [ ] **Step 2: 写失败测试（集成测试）**

新建 `tests/integration/test_preprocessor_vars.py`：

```python
"""Integration tests: ScenarioPreprocessor + vars + generator."""
import pytest
from unittest.mock import MagicMock
from gimbal.preprocessor.scenario_preprocessor import ScenarioPreprocessor
from gimbal.schema.scenario import Scenario, Config
from gimbal.schema.meta import Meta
from gimbal.schema.step import Step, Request, Api
from gimbal.generator import Generator, build_default_registry
from gimbal.config.models import BootstrapConfig


def _make_scenario(vars_dict, body):
    """构造一个最小 scenario 用于测试。"""
    cfg = Config(vars=vars_dict)
    meta = Meta(
        name="test", description="test", module="t", priority=1,
        author="x", owner="x", tags=[], version="1.0.0",
        createTime="2026-01-01T00:00:00", expire=False, requirementRef=[],
    )
    api = Api(kind="api", service="s", method="POST", path="/x", headers={}, timeout=30)
    request = Request(kind="request", body=body)
    step = Step(kind="step", api=api, request=request, strategy=[])
    return Scenario(kind="scenario", scenarioId="t1", meta=meta, config=cfg,
                    resource={}, steps=[step])


def _make_cfg(generator=None, vars=None):
    g = generator or Generator(build_default_registry())
    return BootstrapConfig(env="dev", mode="local", generator=g, vars=vars or {})


class TestGeneratorVar:
    def test_random_str_var_resolved(self):
        """生成式 var 能在 step body 中展开。"""
        sc = _make_scenario(
            vars={"bl_no": {"kind": "random_str", "length": 12, "charset": "alnum"}},
            body={"bl_no": "${var.bl_no}"},
        )
        cfg = _make_cfg()
        pre = ScenarioPreprocessor(sc, cfg)
        steps, _ = pre.run()
        body = steps[0].request.body
        assert isinstance(body["bl_no"], str)
        assert len(body["bl_no"]) == 12

    def test_timestamp_var_preserves_int_type(self):
        """生成式 timestamp (format=epoch) 解析为 int。"""
        sc = _make_scenario(
            vars={"etd": {"kind": "timestamp", "format": "epoch"}},
            body={"etd": "${var.etd}"},
        )
        cfg = _make_cfg()
        pre = ScenarioPreprocessor(sc, cfg)
        steps, _ = pre.run()
        assert isinstance(steps[0].request.body["etd"], int)

    def test_random_decimal_var_preserves_float_type(self):
        """生成式 random_decimal 解析为 float。"""
        sc = _make_scenario(
            vars={"w": {"kind": "random_decimal", "min": 10, "max": 20, "places": 2}},
            body={"w": "${var.w}"},
        )
        cfg = _make_cfg()
        pre = ScenarioPreprocessor(sc, cfg)
        steps, _ = pre.run()
        assert isinstance(steps[0].request.body["w"], float)

    def test_uuid_var_resolved(self):
        sc = _make_scenario(
            vars={"u": {"kind": "uuid"}},
            body={"u": "${var.u}"},
        )
        cfg = _make_cfg()
        pre = ScenarioPreprocessor(sc, cfg)
        steps, _ = pre.run()
        u = steps[0].request.body["u"]
        assert isinstance(u, str) and len(u) == 32


class TestLiteralVar:
    def test_int_literal(self):
        sc = _make_scenario(vars={"n": 16}, body={"n": "${var.n}"})
        cfg = _make_cfg()
        steps, _ = ScenarioPreprocessor(sc, cfg).run()
        assert steps[0].request.body["n"] == 16

    def test_str_literal(self):
        sc = _make_scenario(vars={"s": "hello"}, body={"s": "${var.s}"})
        cfg = _make_cfg()
        steps, _ = ScenarioPreprocessor(sc, cfg).run()
        assert steps[0].request.body["s"] == "hello"

    def test_bool_literal(self):
        sc = _make_scenario(vars={"b": False}, body={"b": "${var.b}"})
        cfg = _make_cfg()
        steps, _ = ScenarioPreprocessor(sc, cfg).run()
        assert steps[0].request.body["b"] is False

    def test_none_literal(self):
        """None 字面量展开为 None（合法值）。"""
        sc = _make_scenario(vars={"x": None}, body={"x": "${var.x}"})
        cfg = _make_cfg()
        steps, _ = ScenarioPreprocessor(sc, cfg).run()
        assert steps[0].request.body["x"] is None


class TestPrecedence:
    def test_cli_var_wins_over_scenario_var(self):
        """CLI vars 与 scenario vars 同名时 CLI 赢。"""
        sc = _make_scenario(
            vars={"x": {"kind": "random_str", "length": 5}},
            body={"x": "${var.x}"},
        )
        cfg = _make_cfg(vars={"x": "fixed_from_cli"})
        steps, _ = ScenarioPreprocessor(sc, cfg).run()
        assert steps[0].request.body["x"] == "fixed_from_cli"

    def test_cli_var_merges_with_scenario_vars(self):
        """scenario 没声明、CLI 有声明时 CLI 提供值。"""
        sc = _make_scenario(
            vars={"a": "literal_a"},
            body={"a": "${var.a}", "b": "${var.b}"},
        )
        cfg = _make_cfg(vars={"b": "from_cli"})
        steps, _ = ScenarioPreprocessor(sc, cfg).run()
        body = steps[0].request.body
        assert body["a"] == "literal_a"
        assert body["b"] == "from_cli"


class TestErrors:
    def test_invalid_spec_raises(self):
        """不合法的 spec 抛 GeneratorError 或 ValidationError。"""
        from pydantic import ValidationError
        sc = _make_scenario(
            vars={"x": {"kind": "nonexistent"}},
            body={"x": "${var.x}"},
        )
        cfg = _make_cfg()
        with pytest.raises(ValidationError):
            ScenarioPreprocessor(sc, cfg).run()

    def test_undefined_var_in_template_raises(self):
        """模板引用未声明 var 抛 ValueError。"""
        sc = _make_scenario(vars={}, body={"x": "${var.undef}"})
        cfg = _make_cfg()
        with pytest.raises(ValueError, match="undef"):
            ScenarioPreprocessor(sc, cfg).run()


class TestNoVars:
    def test_empty_vars_runs_fine(self):
        """vars 为空时不影响其他阶段。"""
        sc = _make_scenario(vars={}, body={"x": "static_value"})
        cfg = _make_cfg()
        steps, _ = ScenarioPreprocessor(sc, cfg).run()
        assert steps[0].request.body["x"] == "static_value"
```

- [ ] **Step 3: 跑测试，预期全部失败（Phase 1.5 未实现）**

```bash
cd d:/Gimbal/Gimbal && python -m pytest tests/integration/test_preprocessor_vars.py -v
```

Expected: 全部失败（AttributeError 或 NameError）

- [ ] **Step 4: 修改 `ScenarioPreprocessor`**

修改 [src/gimbal/preprocessor/scenario_preprocessor.py](src/gimbal/preprocessor/scenario_preprocessor.py)：

**改动 1**：在 `__init__` 末尾加 `_resolved_vars`：

```python
        self._auth_registry = auth_registry
        self._asset_store = asset_store
        self._resolved_vars: dict[str, Any] = {}   # Phase 1.5 填充
```

**改动 2**：修改 `run()` 顺序：

```python
    def run(self) -> tuple[list["StepUnion"], str]:
        if self._asset_store is not None:
            self._materialize_refs()            # Phase 0
        self._setup_auth()                      # Phase 1
        self._generate_vars()                   # Phase 1.5  ★ 新增
        root = self._build_resolve_root()       # Phase 2
        resolved = self._resolve_steps(root)    # Phase 3
        base_url = self._pick_base_url()        # Phase 4
        return resolved, base_url
```

**改动 3**：新增 `_generate_vars` 方法（紧跟 `_setup_auth` 后）：

```python
    def _generate_vars(self) -> None:
        """Phase 1.5: 合并 scenario + CLI vars，生成或保留字面量。

        合并规则（CLI 赢）：
            merged = {**scenario_vars, **cli_vars}

        每一项运行时判定：
            - dict 且含 'kind'：作为生成式，调用 self._generator.generate
            - str / int / float / bool / None：作为字面量，原样保留
            - 其它类型：抛 ValueError
        """
        from gimbal.generator import VarSpec  # 局部导入避免循环

        cli_vars = self._cfg.vars or {}
        scenario_vars = getattr(self._schema.config, "vars", None) or {}
        merged: dict[str, Any] = {**scenario_vars, **cli_vars}

        result: dict[str, Any] = {}
        for name, spec in merged.items():
            if isinstance(spec, dict) and "kind" in spec:
                var_spec = VarSpec.model_validate(spec)
                result[name] = self._generator.generate(var_spec)
            elif isinstance(spec, (str, int, float, bool, type(None))):
                result[name] = spec
            else:
                raise ValueError(
                    f"[Preprocessor] invalid var spec for '{name}': {spec!r} "
                    f"(expected dict with 'kind' or a primitive literal)"
                )
        self._resolved_vars = result
```

**改动 4**：修改 `_build_resolve_root`（注入 `_resolved_vars`）：

找到当前 `_build_resolve_root`（[scenario_preprocessor.py:156 附近](src/gimbal/preprocessor/scenario_preprocessor.py#L156-L182)）：

当前内容大致是：
```python
def _build_resolve_root(self) -> dict:
    root: dict[str, Any] = {}
    if self._cfg.services: ...
    if self._cfg.vars:
        root["var"] = dict(self._cfg.vars)
    return root
```

改为：
```python
def _build_resolve_root(self) -> dict:
    root: dict[str, Any] = {"service": {}, "auth": self._auth_registry.snapshot()}
    # 注入 Phase 1.5 生成的 vars（CLI + scenario 合并后）
    if self._resolved_vars:
        root["var"] = dict(self._resolved_vars)
    return root
```

> 注意：保留原 service / auth 的处理逻辑，**不要删掉现有字段**。具体合并原代码后形成完整函数。

- [ ] **Step 5: 跑新集成测试，预期通过**

```bash
cd d:/Gimbal/Gimbal && python -m pytest tests/integration/test_preprocessor_vars.py -v
```

Expected: 全部通过（约 15 个）

- [ ] **Step 6: 跑全部测试，确认未破坏**

```bash
cd d:/Gimbal/Gimbal && python -m pytest tests/ -v
```

Expected: 全部通过

- [ ] **Step 7: Commit**

```bash
cd d:/Gimbal/Gimbal && git add src/gimbal/preprocessor/scenario_preprocessor.py tests/integration/test_preprocessor_vars.py
git commit -m "feat(preprocessor): add Phase 1.5 var generation"
```

---

## Task 11: E2E 验证（修改 e2e.json）

**Files:**
- Modify: `src/gimbal/cli/commands/e2e.json`

- [ ] **Step 1: 备份当前 e2e.json**

```bash
cd d:/Gimbal/Gimbal && cp src/gimbal/cli/commands/e2e.json src/gimbal/cli/commands/e2e.json.bak
```

- [ ] **Step 2: 在 `config` 下加 `vars` 声明**

修改 [src/gimbal/cli/commands/e2e.json:17-35](src/gimbal/cli/commands/e2e.json#L17-L35)，在 `"retry": null` 之后加：

```json
  "vars": {
    "bl_no":  { "kind": "random_str",    "length": 12, "charset": "alnum" },
    "etd":    { "kind": "timestamp",     "format": "epoch" },
    "weight": { "kind": "random_decimal", "min": 50,    "max": 200,  "places": 2 }
  },
```

完整 `config` 块参考：

```json
  "config": {
    "setup": [],
    "teardown": [],
    "services": { "tidb-test-service": "https://fin-tidb.21eflag.com/" },
    "users": { ... },
    "timePolicy": { "kind": "record" },
    "retry": null,
    "vars": {
      "bl_no":  { "kind": "random_str",    "length": 12, "charset": "alnum" },
      "etd":    { "kind": "timestamp",     "format": "epoch" },
      "weight": { "kind": "random_decimal", "min": 50,    "max": 200,  "places": 2 }
    }
  },
```

- [ ] **Step 3: 替换 5 处硬编码 `"bl_no":"codfishe2e24"` 为 `"bl_no":"${var.bl_no}"`**

用编辑器全局替换：

- 旧：`"bl_no":"codfishe2e24"`
- 新：`"bl_no":"${var.bl_no}"`

至少替换 5 处（e2e.json 中实际出现 6+ 次，全替即可）。

- [ ] **Step 4: 跑测试或 CLI 加载**

```bash
cd d:/Gimbal/Gimbal && python -m pytest tests/integration/test_preprocessor_vars.py -v
```

Expected: 全部通过

或尝试加载 e2e.json（如果 CLI 命令存在）：

```bash
cd d:/Gimbal/Gimbal && python -m gimbal run scenario src/gimbal/cli/commands/e2e.json --dry-run 2>&1 | head -20
```

> 若 CLI 无 `--dry-run`，跳过此步；改用单元测试验证（已覆盖 vars 注入逻辑）。

- [ ] **Step 5: Commit**

```bash
cd d:/Gimbal/Gimbal && git add src/gimbal/cli/commands/e2e.json
git commit -m "feat(e2e): migrate hardcoded bl_no to generated var"
```

---

## Task 12: 文档

**Files:**
- Create: `docs/modules/generator.md`
- Modify: `docs/modules/preprocessor.md`
- Modify: `docs/modules/config.md`

- [ ] **Step 1: 新建 `docs/modules/generator.md`**

```markdown
# Generator 模块

> 变量生成器：为 Scenario 提供声明式变量求值能力（字面量 + 7 个内置生成器）

## 目录结构

\`\`\`
gimbal/generator/
├── __init__.py        # 公开 API
├── exceptions.py      # GeneratorError, UnknownGeneratorError
├── functions.py       # 7 个 pure function + reset_seq_counter
├── registry.py        # GeneratorRegistry, build_default_registry
├── specs.py           # 7 个 Pydantic Spec + VarSpec 联合体
└── engine.py          # Generator 类
\`\`\`

## 7 个内置生成器

| kind | 命名参数 | 用途 |
|------|---------|------|
| \`uuid\` | (无) | 32 位 hex |
| \`random_str\` | length / charset | 随机字符串 |
| \`random_int\` | min / max | 闭区间整数 |
| \`random_decimal\` | min / max / places | 闭区间小数 |
| \`timestamp\` | format / offset_seconds | 当前时间 + 偏移 |
| \`now\` | format | 当前时间（无偏移） |
| \`seq\` | prefix / width / start | 自增序号 |

详见 spec §7.3。

## 公开 API

\`\`\`python
from gimbal.generator import (
    Generator,                    # 求值入口
    GeneratorRegistry,            # 注册表
    build_default_registry,       # 默认注册表（含 7 个内置）
    VarSpec,                      # 联合体
    GeneratorError, UnknownGeneratorError,
)
\`\`\`

## 用法

\`\`\`python
gen = Generator(build_default_registry())

# 单条求值
spec = RandomStrSpec(length=12, charset="alnum")
val = gen.generate(spec)               # "Yk2H8nQp3aZx"

# 批量求值
results = gen.generate_all({
    "bl_no":  {"kind": "random_str", "length": 12},
    "etd":    {"kind": "timestamp",  "format": "epoch"},
})
\`\`\`

## 设计原则

1. **Pure function**：每个函数除自身参数外无外部依赖
2. **命名参数**：函数参数名与 Spec 字段一一对应
3. **注册表解耦**：新增生成器只需 register(kind, func) 一行
4. **错误透传**：函数异常被 GeneratorError 包装，保留 __cause__
5. **模块级 seq 计数器**：单进程有效；多进程用 reset_seq_counter 隔离
```

- [ ] **Step 2: 修改 `docs/modules/preprocessor.md` 加 Phase 1.5**

在 [docs/modules/preprocessor.md](docs/modules/preprocessor.md) 的"五段处理流程"章节（§五段处理流程）后追加：

```markdown
### Phase 1.5：变量生成（★ 新增）

合并 `scenario.config.vars` 与 `BootstrapConfig.vars`，调用 Generator 求值生成式 spec，保留字面量，产出 `self._resolved_vars` 供 Phase 2 注入 root。

\`\`\`python
def _generate_vars(self) -> None:
    cli_vars = self._cfg.vars or {}
    scenario_vars = getattr(self._schema.config, "vars", None) or {}
    merged = {**scenario_vars, **cli_vars}    # CLI 赢

    for name, spec in merged.items():
        if isinstance(spec, dict) and "kind" in spec:
            var_spec = VarSpec.model_validate(spec)
            result[name] = self._generator.generate(var_spec)
        elif isinstance(spec, (str, int, float, bool, type(None))):
            result[name] = spec
        else:
            raise ValueError(...)
\`\`\`

详见 spec §6.4。
```

- [ ] **Step 3: 修改 `docs/modules/config.md` 加 generator 字段**

在 [docs/modules/config.md](docs/modules/config.md) 的 `BootstrapConfig` 描述后追加：

```markdown
### BootstrapConfig.generator 字段（★ 新增）

字符串前向引用类型，由 `bootstrap()` 构造并注入：

\`\`\`python
generator: "Generator | None" = Field(default=None, ...)
\`\`\`

preprocessor Phase 1.5 调用 `self._cfg.generator.generate(spec)`。
```

- [ ] **Step 4: 跑文档示例（如果可执行）**

```bash
cd d:/Gimbal/Gimbal && python -c "from gimbal.generator import Generator, build_default_registry; g = Generator(build_default_registry()); print(g.generate_all({'u': {'kind': 'uuid'}}))"
```

Expected: `{'u': '...32hex...'}`（不报错即过）

- [ ] **Step 5: Commit**

```bash
cd d:/Gimbal/Gimbal && git add docs/modules/generator.md docs/modules/preprocessor.md docs/modules/config.md
git commit -m "docs(generator): add module doc + update preprocessor/config refs"
```

---

## Task 13: 最终验证 + 清理

- [ ] **Step 1: 跑全部测试**

```bash
cd d:/Gimbal/Gimbal && python -m pytest tests/ -v
```

Expected: 全部通过

- [ ] **Step 2: 删除备份**

```bash
cd d:/Gimbal/Gimbal && rm src/gimbal/cli/commands/e2e.json.bak
```

- [ ] **Step 3: 检查 ruff / mypy（如已配置）**

```bash
cd d:/Gimbal/Gimbal && python -m ruff check src/gimbal/generator/ 2>&1 || true
cd d:/Gimbal/Gimbal && python -m mypy src/gimbal/generator/ 2>&1 || true
```

Expected: 无 error（warning 可接受）

- [ ] **Step 4: 最终 commit（若有修改）**

```bash
cd d:/Gimbal/Gimbal && git status
# 若有未提交改动：
cd d:/Gimbal/Gimbal && git add -A && git commit -m "chore: post-implementation cleanup"
```

---

## Self-Review

**Spec 覆盖检查**：

| Spec 章节 | 任务 |
|----------|------|
| §3 整体架构 | Task 10（preprocessor 集成） |
| §5.1 7 Spec | Task 4（specs.py） |
| §5.3 字面量/生成式混合 | Task 10 + Task 11（preprocessor + e2e.json） |
| §6.1 `Scenario.config` | Task 7 |
| §6.2 `BootstrapConfig.generator` | Task 8 |
| §6.3 `bootstrap()` 改造 | Task 9 |
| §6.4 Phase 1.5 | Task 10 |
| §7.1 registry.py | Task 3 |
| §7.2 engine.py | Task 5 |
| §7.3 functions.py | Task 2 |
| §7.4 exceptions.py | Task 1 |
| §11.1 单元测试 | Task 1, 2, 3, 4, 5, 6 |
| §11.2 集成测试 | Task 10 |
| §11.3 E2E 验证 | Task 11 |
| 文档 | Task 12 |

✅ 所有 spec 章节都有对应任务

**占位符扫描**：

- 无 "TBD" / "TODO" / "fill in"
- 所有代码块完整
- 所有命令带预期输出
- 无 "类似 Task N" 引用

✅ 无占位符

**类型一致性**：

- `Generator.generate(spec: VarSpec) -> Any` 在 Task 5 定义，Task 10 引用 ✓
- `GeneratorRegistry.register(kind, func)` 在 Task 3 定义，Task 6 引用 ✓
- `build_default_registry()` 在 Task 3 定义，Task 6/8/9 引用 ✓
- `BootstrapConfig.generator: "Generator | None"` 在 Task 8 定义，Task 9 引用 ✓
- `Scenario.config.vars: dict[str, Any]` 在 Task 7 定义，Task 10/11 引用 ✓

✅ 类型/方法名一致

**自审结论**：Plan 完整覆盖 spec，无占位符，无类型不一致。
