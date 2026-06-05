"""Unit tests for ModelRegistry._aliases (service 名 → Python 包名 解析)。

覆盖场景:
  [1] 合法 Python 标识符 → 原样返回
  [2] 连字符 service 名 → 走 alias 表解析
  [3] 数字开头 / 含点 → 无 alias → ValueError
  [4] Python 关键字 → 走 alias 表(主路径不接受)
  [5] 空串 / 非字符串输入 → ValueError
  [6] alias 值不是合法 Python 包名 → ValueError
  [7] alias 表修改/恢复(测试间隔离)
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

print("=" * 60)
print("ALIASES TEST")
print("=" * 60)


from ModelRegistry import _aliases


# 备份原始 alias 表,所有改动测试结束后恢复
ORIGINAL_ALIASES = dict(_aliases.SERVICE_ALIASES)


def restore_aliases():
    _aliases.SERVICE_ALIASES.clear()
    _aliases.SERVICE_ALIASES.update(ORIGINAL_ALIASES)


# ════════════════════════════════════════════════════════════════════════════
# [1] 合法 Python 标识符 → 原样返回
# ════════════════════════════════════════════════════════════════════════════
print("\n[1] 合法 Python 标识符 → 原样返回(主路径)")
for name in ["settlement", "order", "user_service", "api_v2", "_private", "a1b2c3"]:
    got = _aliases.resolve_dir_name(name)
    assert got == name, f"'{name}' → expected {name!r}, got {got!r}"
print(f"  PASS — 测试了 6 个合法标识符,全部原样返回")


# ════════════════════════════════════════════════════════════════════════════
# [2] 连字符 service 名 → 走 alias 表
# ════════════════════════════════════════════════════════════════════════════
print("\n[2] 连字符 service 名 → 走 alias 表解析")
restore_aliases()
_aliases.SERVICE_ALIASES["tidb-test-service"] = "tidb_test_service"
try:
    got = _aliases.resolve_dir_name("tidb-test-service")
    assert got == "tidb_test_service", f"got {got!r}"
    print(f"  PASS — 'tidb-test-service' → {got!r}")
finally:
    restore_aliases()


# ════════════════════════════════════════════════════════════════════════════
# [3] 数字开头 / 含点 → 无 alias → ValueError
# ════════════════════════════════════════════════════════════════════════════
print("\n[3] 数字开头 / 含点 → ValueError")
for bad in ["3pl-service", "fin.tidb", "1", "a.b.c"]:
    try:
        _aliases.resolve_dir_name(bad)
        assert False, f"应抛 ValueError 但没抛: {bad!r}"
    except ValueError as e:
        assert "SERVICE_ALIASES" in str(e), f"错误信息应提到 SERVICE_ALIASES: {e}"
print("  PASS — 4 个非法名全部正确抛 ValueError")


# ════════════════════════════════════════════════════════════════════════════
# [4] Python 关键字 → 走 alias 表(主路径不接受)
# ════════════════════════════════════════════════════════════════════════════
print("\n[4] Python 关键字 → 走 alias 表")
restore_aliases()
# 主路径:虽然 'class' 是 isidentifier(),但 keyword.iskeyword() 应否决
try:
    got = _aliases.resolve_dir_name("class")
    # 若主路径误接受,会原样返回 "class"——这会失败后续 importlib
    assert False, f"关键字 'class' 应被主路径拒绝,实际返回 {got!r}"
except ValueError:
    print("  关键字 'class' 被主路径拒绝(走 alias 兜底)")

# 显式 alias 后可通过
_aliases.SERVICE_ALIASES["class"] = "klass_service"
try:
    got = _aliases.resolve_dir_name("class")
    assert got == "klass_service", f"got {got!r}"
    print(f"  alias 后 'class' → {got!r}")
finally:
    restore_aliases()
print("  PASS")


# ════════════════════════════════════════════════════════════════════════════
# [5] 空串 / 非字符串输入 → ValueError
# ════════════════════════════════════════════════════════════════════════════
print("\n[5] 空串 / 非字符串输入 → ValueError")
for bad in ["", None, 123, [], b"bytes"]:
    try:
        _aliases.resolve_dir_name(bad)
        assert False, f"应抛 ValueError 但没抛: {bad!r}"
    except ValueError:
        pass
print("  PASS — 5 个非法输入全部正确抛 ValueError")


# ════════════════════════════════════════════════════════════════════════════
# [6] alias 值不是合法 Python 包名 → ValueError
# ════════════════════════════════════════════════════════════════════════════
print("\n[6] alias 值不合法 → ValueError")
restore_aliases()
for bad_value in ["3bad", "has-dash", "has.dot", "class"]:
    _aliases.SERVICE_ALIASES["some-service"] = bad_value
    try:
        _aliases.resolve_dir_name("some-service")
        assert False, f"alias 值 {bad_value!r} 应被拒绝"
    except ValueError as e:
        # "class" 会被 keyword.iskeyword 拒绝,其他被 isidentifier 拒绝
        assert "isidentifier" in str(e) or "keyword" in str(e), \
            f"错误信息应说明 alias 值不合法: {e}"
print("  PASS — 4 个非法 alias 值全部被拒绝")
restore_aliases()


# ════════════════════════════════════════════════════════════════════════════
# [7] alias 表隔离(本测试修改不影响下一测试)
# ════════════════════════════════════════════════════════════════════════════
print("\n[7] alias 表测试间隔离")
restore_aliases()
assert "tidb-test-service" not in _aliases.SERVICE_ALIASES, "恢复后 alias 表应干净"
print("  PASS — 恢复后 alias 表无残留")


# ════════════════════════════════════════════════════════════════════════════
# 收尾
# ════════════════════════════════════════════════════════════════════════════
restore_aliases()
print("\n" + "=" * 60)
print("ALIASES TEST: ALL PASSED")
print("=" * 60)
