"""Unit tests for gimbal.generator.registry."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

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
    def test_contains_all_9_kinds(self):
        """默认注册表包含全部 9 个内置 kind。"""
        r = build_default_registry()
        expected = {"uuid", "random_str", "random_int", "random_decimal",
                    "timestamp", "now", "seq",
                    "random_decorated", "time_offset"}
        assert set(r.kinds()) == expected

    def test_each_function_callable(self):
        """每个 kind 都能被取出并调用。"""
        r = build_default_registry()
        for kind in r.kinds():
            func = r.get(kind)
            assert callable(func)
            # 每个函数至少能调用一次（参数用 default）
            func()  # 不应抛
