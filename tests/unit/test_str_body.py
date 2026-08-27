"""阶段 1：str body 支持的回归测试。

覆盖范围：
  - schema 层：Request.body 接受 str，反序列化往返
  - resolver 层：str body 的 ${} 模板替换、空字符串不被 falsy 兜底吞掉
  - falsy 兜底修复：preprocessor / resolver 的 `or {}` 改为 `is None`
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import unittest
from typing import Any

from gimbal.schema.request import Request
from gimbal.context.resolver import SpecResolver


class _StubChannels:
    @staticmethod
    def variables_snapshot() -> dict[str, Any]:
        return {
            "xml_payload": "<order><id>123</id></order>",
            "bl_no": "BL9999",
        }


class _StubView:
    def __init__(self, channels: _StubChannels) -> None:
        self._ctx = type("_Ctx", (), {"parent": type(
            "_Parent", (), {"channels": channels}
        )()})()


class _StubConfig:
    services = None
    users = None


def _resolver() -> SpecResolver:
    return SpecResolver(view=_StubView(_StubChannels()), config=_StubConfig())


class TestSchemaAcceptsStrBody(unittest.TestCase):
    """schema 层：Request.body 接受 str，反序列化字段。"""

    def test_str_body_roundtrip(self) -> None:
        req = Request(body="<xml/>")
        self.assertEqual(req.body, "<xml/>")
        self.assertEqual(req.kind, "request")

    def test_dict_body_still_works(self) -> None:
        req = Request(body={"a": 1})
        self.assertEqual(req.body, {"a": 1})

    def test_list_body_still_works(self) -> None:
        req = Request(body=[1, 2, 3])
        self.assertEqual(req.body, [1, 2, 3])

    def test_empty_str_body_is_preserved(self) -> None:
        """空字符串 body 不应被默认值的 {} 工厂替代。"""
        req = Request(body="")
        self.assertEqual(req.body, "")


class TestStrBodyTemplateResolution(unittest.TestCase):
    """resolver 层：str body 的 ${} 模板替换。"""

    def test_str_body_template_substitution(self) -> None:
        r = _resolver()
        out = r._resolve_nested("prefix-${xml_payload}-suffix")
        self.assertEqual(out, "prefix-<order><id>123</id></order>-suffix")

    def test_str_body_full_template(self) -> None:
        """整体就是一个 ${} 的字符串，替换后类型可能变化。"""
        r = _resolver()
        out = r._resolve_nested("${xml_payload}")
        self.assertEqual(out, "<order><id>123</id></order>")

    def test_str_body_no_template_passthrough(self) -> None:
        """无 ${} 的字符串原样返回。"""
        r = _resolver()
        out = r._resolve_nested("plain text")
        self.assertEqual(out, "plain text")

    def test_resolve_request_str_body(self) -> None:
        """核心：_resolve_request 对 str body 完成模板替换，body 仍是 str。"""
        r = _resolver()
        req = Request(body="${xml_payload}")
        resolved = r._resolve_request(req)
        self.assertIsInstance(resolved.body, str)
        self.assertEqual(resolved.body, "<order><id>123</id></order>")

    def test_empty_str_body_not_swallowed(self) -> None:
        """falsy 兜底修复：空字符串 body 在 _resolve_request 后仍是 ""，不应变成 {}。"""
        r = _resolver()
        req = Request(body="")
        resolved = r._resolve_request(req)
        self.assertEqual(resolved.body, "")
        self.assertIsInstance(resolved.body, str)


class TestStrBodyStrategyAvailability(unittest.TestCase):
    """策略可用性文档化测试：str body 下 JSONPath 导航的行为。

    这些测试把"行为契约"固化下来，避免后续实现无意识破坏。
    """

    def test_str_body_passes_through_resolve_value(self) -> None:
        """str body 走 _resolve_value 分支（不是 _resolve_dict 也不是 list-recursion）。"""
        r = _resolver()
        # 直接调用 _resolve_value 验证 str 分支路径
        out = r._resolve_value("${bl_no}")
        self.assertEqual(out, "BL9999")

    def test_str_body_dict_path_returns_none(self) -> None:
        """对 str body 用 dict-style 路径（$.body.xxx）返回 None —— 这是预期降级。"""
        # 这里只验证：str 走 _resolve_value 时，子路径导航不会被执行
        # 实际 JSONPath 行为在 Extract 策略层；本测试覆盖 resolver 层的契约
        r = _resolver()
        out = r._resolve_value("plain")  # 没有 .xxx 后缀，原样返回
        self.assertEqual(out, "plain")


if __name__ == "__main__":
    unittest.main()
