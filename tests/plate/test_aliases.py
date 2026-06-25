"""Unit tests for Plate._aliases (service 名 → Python 包名 解析)。

覆盖场景:
  [1] 合法 Python 标识符 → 原样返回
  [2] 连字符 service 名 → 走 alias 表解析
  [3] 数字开头 / 含点 → 无 alias → ValueError
  [4] Python 关键字 → 走 alias 表(主路径不接受)
  [5] 空串 / 非字符串输入 → ValueError
  [6] alias 值不是合法 Python 包名 → ValueError
  [7] alias 表修改/恢复(测试间隔离)
"""
from __future__ import annotations

import pytest

from Plate import _aliases


# 备份原始 alias 表(模块级 fixture,autouse 保证每个测试前后隔离)
@pytest.fixture(autouse=True)
def _isolate_aliases():
    """测试间隔离:每个测试前后都恢复 SERVICE_ALIASES。

    对应设计:§"单元测试不变量" — alias 是模块级可变状态,任何修改会污染后续测试。
    业务影响:不隔离 = 后续测试拿到上一个测试残留的 alias,误判行为。
    """
    original = dict(_aliases.SERVICE_ALIASES)
    yield
    _aliases.SERVICE_ALIASES.clear()
    _aliases.SERVICE_ALIASES.update(original)


# ════════════════════════════════════════════════════════════════════════════
# [1] 合法 Python 标识符 → 原样返回
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("name", [
    "settlement", "order", "user_service", "api_v2", "_private", "a1b2c3",
])
def test_legal_identifier_returned_as_is(name: str) -> None:
    """业务需求:合法 Python 标识符 → 原样返回(主路径)。

    对应设计:§_aliases 解析规则 #1。
    业务影响:违反 = 简单 service 名也要走 alias 表,浪费一次 dict lookup;
             更严重的是直接破坏"service 名即目录名"约定。
    """
    got = _aliases.resolve_dir_name(name)
    assert got == name, f"'{name}' → expected {name!r}, got {got!r}"


# ════════════════════════════════════════════════════════════════════════════
# [2] 连字符 service 名 → 走 alias 表
# ════════════════════════════════════════════════════════════════════════════

def test_hyphen_service_name_via_alias() -> None:
    """业务需求:连字符 service 名 → 走 alias 表解析(辅路径)。

    对应设计:§_aliases 解析规则 #2。
    业务影响:违反 = 无法支持"含连字符的真实 service"(如 tidb-test-service),
             scenario 侧 service 字段被迫重命名,破坏业务命名。
    """
    _aliases.SERVICE_ALIASES["tidb-test-service"] = "tidb_test_service"
    got = _aliases.resolve_dir_name("tidb-test-service")
    assert got == "tidb_test_service", f"got {got!r}"


# ════════════════════════════════════════════════════════════════════════════
# [3] 数字开头 / 含点 → 无 alias → ValueError
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("bad_name", ["3pl-service", "fin.tidb", "1", "a.b.c"])
def test_invalid_service_name_raises_value_error(bad_name: str) -> None:
    """业务需求:数字开头/含点 service 名 → ValueError(无 alias 兜底)。

    对应设计:§_aliases 解析规则 #3。
    业务影响:违反 = 静默接受不可 import 的 service 名,运行时 importlib 报错延迟到
             collect 阶段,堆栈深,定位难。fail-fast 让作者在写 scenario 时就修。
    """
    with pytest.raises(ValueError) as exc:
        _aliases.resolve_dir_name(bad_name)
    assert "SERVICE_ALIASES" in str(exc.value), (
        f"错误信息应提示添加到 SERVICE_ALIASES: {exc.value}"
    )


# ════════════════════════════════════════════════════════════════════════════
# [4] Python 关键字 → 走 alias 表
# ════════════════════════════════════════════════════════════════════════════

def test_python_keyword_rejected_by_main_path() -> None:
    """业务需求:Python 关键字(如 'class')在主路径被拒。

    对应设计:§_aliases 解析规则 #1 "不是关键字"。
    业务影响:违反 = 直接返回 'class' → importlib.import_module('Plate.class') 失败,
             错误信息(ModuleNotFoundError)与"service 配置错"语义不一致。
    """
    with pytest.raises(ValueError):
        _aliases.resolve_dir_name("class")


def test_python_keyword_via_alias() -> None:
    """业务需求:Python 关键字显式 alias 后可通过。

    对应设计:§_aliases 解析规则 #2。
    业务影响:违反 = 真实业务有"以关键字为 service 名"的需求(罕见但存在)时无解。
    """
    _aliases.SERVICE_ALIASES["class"] = "klass_service"
    got = _aliases.resolve_dir_name("class")
    assert got == "klass_service", f"got {got!r}"


# ════════════════════════════════════════════════════════════════════════════
# [5] 空串 / 非字符串输入 → ValueError
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("bad_input", ["", None, 123, [], b"bytes"])
def test_non_string_or_empty_input_raises(bad_input: object) -> None:
    """业务需求:空串/非字符串输入 → ValueError(强类型输入校验)。

    对应设计:§_aliases "service 名必须是非空字符串"。
    业务影响:违反 = None/bytes 走 attribute lookup,运行时 AttributeError 难定位。
    """
    with pytest.raises(ValueError):
        _aliases.resolve_dir_name(bad_input)  # type: ignore[arg-type]


# ════════════════════════════════════════════════════════════════════════════
# [6] alias 值不是合法 Python 包名 → ValueError
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("bad_value", ["3bad", "has-dash", "has.dot", "class"])
def test_invalid_alias_value_raises(bad_value: str) -> None:
    """业务需求:alias 值必须是合法 Python 包名 → 否则 ValueError。

    对应设计:§_aliases "alias 值必须满足 isidentifier() 且不是关键字"。
    业务影响:违反 = SERVICE_ALIASES 配错 → 后续 importlib.import_module 失败,
             错误指向 Plate.<bad_value> 而不是作者填错 alias 的源头,定位慢。
    """
    _aliases.SERVICE_ALIASES["some-service"] = bad_value
    with pytest.raises(ValueError) as exc:
        _aliases.resolve_dir_name("some-service")
    # "class" 会被 keyword.iskeyword 拒绝,其他被 isidentifier 拒绝
    assert "isidentifier" in str(exc.value) or "keyword" in str(exc.value), (
        f"错误信息应说明 alias 值不合法: {exc.value}"
    )


# ════════════════════════════════════════════════════════════════════════════
# [7] alias 表测试间隔离(autouse fixture 验证)
# ════════════════════════════════════════════════════════════════════════════

def test_alias_table_isolated_after_modification() -> None:
    """业务需求:测试改 SERVICE_ALIASES 不影响后续测试。

    对应设计:§_aliases 单元测试约定。
    业务影响:违反 = 后续测试拿到上一个测试残留的 alias,行为不可预测。
    """
    _aliases.SERVICE_ALIASES["tidb-test-service"] = "tidb_test_service"
    # fixture 会在测试结束后自动恢复
    assert "tidb-test-service" in _aliases.SERVICE_ALIASES
    # 注:autouse fixture 会在此函数返回后自动清空 _DOCS,
    # 下一个测试启动时会看到干净状态(由 test_alias_table_clean 验证)
    # 这里不再加额外断言,避免冗余


def test_alias_table_clean_at_test_start() -> None:
    """业务需求:测试启动时 SERVICE_ALIASES 应是空(默认状态)。

    对应设计:§_aliases 单元测试约定(与上一个测试互证)。
    业务影响:违反 = 上一个测试的残留 alias 误导本测试,误判"无 alias 必失败"行为。
    """
    # 在 [7] 之前的测试,autouse fixture 已保证 alias 表被恢复
    assert "tidb-test-service" not in _aliases.SERVICE_ALIASES, (
        "测试间隔离失败:残留 alias 'tidb-test-service'"
    )
