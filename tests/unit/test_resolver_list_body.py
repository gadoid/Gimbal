"""Regression tests: SpecResolver 对 list body 的模板替换。

Schema 在 request.py 把 Request.body 类型从 Dict[str, Any] 扩展为
Union[Dict[str, Any], List[Any]] 后，运行期 SpecResolver 必须：
  - dict body: 行为不变（向后兼容）
  - list body: 递归到每个 list 元素，对元素内嵌的 ${} 模板做替换，
    并保留 list 的结构（不要把 list 整体替换成 dict）

注意：本测试只覆盖 SpecResolver 的递归解析路径，不依赖 Step 状态机。
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
            "bl_no": "BL1234567890",
            "qty": 42,
            "name": "alpha",
        }


class _StubView:
    """最小 StepContextAdapter 替身，只覆盖 SpecResolver 实际用到的 API。"""

    def __init__(self, channels: _StubChannels) -> None:
        self._ctx = type("_Ctx", (), {"parent": type(
            "_Parent", (), {"channels": channels}
        )()})()


class _StubConfig:
    services = None
    users = None


def _resolver() -> SpecResolver:
    return SpecResolver(view=_StubView(_StubChannels()), config=_StubConfig())


class TestListBodyTemplateResolution(unittest.TestCase):
    """修复后：list body 内的 ${} 模板应被递归替换，list 结构保留。"""

    def test_list_body_recursively_resolves_templates(self) -> None:
        r = _resolver()
        body = [
            {"bl_no": "${bl_no}", "qty": "${qty}"},
            {"foo": "literal"},
        ]
        out = r._resolve_nested(body)
        self.assertIsInstance(out, list)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["bl_no"], "BL1234567890")
        self.assertEqual(out[0]["qty"], 42)
        self.assertEqual(out[1]["foo"], "literal")

    def test_list_body_nested_dict_is_preserved(self) -> None:
        r = _resolver()
        body = [{"a": {"b": "${name}"}}]
        out = r._resolve_nested(body)
        self.assertEqual(out[0]["a"]["b"], "alpha")

    def test_list_body_with_scalar_items(self) -> None:
        """list 里直接放字符串也支持模板替换。"""
        r = _resolver()
        out = r._resolve_nested(["${bl_no}", "literal", "${name}"])
        self.assertEqual(out, ["BL1234567890", "literal", "alpha"])

    def test_resolve_request_keeps_list_type(self) -> None:
        """核心：_resolve_request 走 _resolve_nested 后 body 仍然是 list。"""
        r = _resolver()
        req = Request(body=[{"bl_no": "${bl_no}"}])
        resolved = r._resolve_request(req)
        self.assertIsInstance(resolved.body, list)
        self.assertEqual(resolved.body[0]["bl_no"], "BL1234567890")


class TestDictBodyStillWorks(unittest.TestCase):
    """向后兼容：dict body 行为完全不变。"""

    def test_dict_body_resolution(self) -> None:
        r = _resolver()
        out = r._resolve_nested({"bl_no": "${bl_no}", "qty": "${qty}"})
        self.assertEqual(out, {"bl_no": "BL1234567890", "qty": 42})

    def test_resolve_request_dict_body(self) -> None:
        r = _resolver()
        req = Request(body={"bl_no": "${bl_no}"})
        resolved = r._resolve_request(req)
        self.assertEqual(resolved.body, {"bl_no": "BL1234567890"})


if __name__ == "__main__":
    unittest.main()
