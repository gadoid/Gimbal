"""阶段 1：call.py str body 分支的单元测试。

覆盖范围：
  - str body + POST 走 content= 通道（bytes 形式）
  - str body 缺 Content-Type 时输出 warning（不阻断）
  - str body + Content-Type 显式声明时不打 warning
  - dict body 走 json= 通道（向后兼容）
  - GET + str body 走 params= 通道（向后兼容）
  - 空字符串 str body 不被 falsy 吞掉

策略：mock httpx.Client.request，验证传参形态；不发起真实网络请求。
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import unittest
from unittest.mock import patch, MagicMock

from gimbal.strategy.builtin.call import CallExecutor


class _StubView:
    """最小 view 替身：覆盖 CallExecutor 实际用到的 scratch 读写。"""

    def __init__(self) -> None:
        self._scratch: dict = {}

    def read_scratch(self, key: str, default=None):
        return self._scratch.get(key, default)

    def write_scratch(self, key: str, value) -> None:
        self._scratch[key] = value


def _make_spec(method="POST", url="http://svc/api", headers=None, body=None,
               timeout=30.0):
    """构造一个 _CallSpec 替身（dataclass-like）。"""
    from gimbal.statemachine.engine import _CallSpec
    return _CallSpec(
        method=method,
        url=url,
        headers=headers or {},
        body=body if body is not None else {},
        timeout=timeout,
    )


class TestCallExecutorStrBody(unittest.TestCase):
    """call.py 新增 str body 分支的回归测试。"""

    def _patch_httpx(self, response_status=200, response_body=None,
                     response_text=""):
        """返回一个 patch 上下文，替换 httpx.Client 内的 request。"""
        mock_response = MagicMock()
        mock_response.status_code = response_status
        if response_body is not None:
            mock_response.json.return_value = response_body
        else:
            mock_response.json.side_effect = Exception("not json")
            mock_response.text = response_text
        mock_response.headers = {"Content-Type": "application/json"}

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request = MagicMock(return_value=mock_response)
        return patch("httpx.Client", return_value=mock_client), mock_client

    def test_str_body_uses_content_channel(self) -> None:
        """str body + POST 走 content= 通道（httpx 的 content 参数接收 bytes）。"""
        ctx, mock_client = self._patch_httpx(
            response_body={"ok": True}
        )
        spec = _make_spec(
            method="POST",
            headers={"Content-Type": "application/xml"},
            body="<order><id>1</id></order>",
        )
        view = _StubView()
        executor = CallExecutor()

        with ctx:
            result = executor.execute(spec, view)

        # 验证调用参数
        call_kwargs = mock_client.request.call_args.kwargs
        self.assertEqual(call_kwargs["method"], "POST")
        self.assertEqual(call_kwargs["content"], b"<order><id>1</id></order>")
        # 不应传 json=
        self.assertNotIn("json", call_kwargs)
        # 不应传 params=
        self.assertNotIn("params", call_kwargs)
        # result 应该 PASSED
        self.assertEqual(result.status.value, "passed")

    def test_str_body_without_content_type_logs_warning(self) -> None:
        """str body 缺 Content-Type 时应 logger.warning，不阻断。"""
        from gimbal.strategy.builtin import call as call_module
        ctx, mock_client = self._patch_httpx(response_body={"ok": True})
        spec = _make_spec(
            method="POST",
            headers={},
            body="plain text",
        )
        view = _StubView()
        executor = CallExecutor()

        # loguru 没有 stdlib logging.Handler 钩子，直接 patch 模块级 logger.warning
        with patch.object(call_module.logger, "warning") as mock_warn:
            with ctx:
                result = executor.execute(spec, view)

        mock_warn.assert_called_once()
        warn_msg = mock_warn.call_args.args[0]
        self.assertIn("缺少 Content-Type", warn_msg)
        # result 仍然 PASSED（不阻断）
        self.assertEqual(result.status.value, "passed")

    def test_str_body_with_content_type_no_warning(self) -> None:
        """str body + 显式 Content-Type 时不打 warning。"""
        from gimbal.strategy.builtin import call as call_module
        ctx, mock_client = self._patch_httpx(response_body={"ok": True})
        spec = _make_spec(
            method="POST",
            headers={"Content-Type": "text/xml"},
            body="<xml/>",
        )
        view = _StubView()
        executor = CallExecutor()

        # 验证不调用 warning
        with patch.object(call_module.logger, "warning") as mock_warn:
            with ctx:
                result = executor.execute(spec, view)

        mock_warn.assert_not_called()
        self.assertEqual(result.status.value, "passed")

    def test_dict_body_still_uses_json(self) -> None:
        """向后兼容：dict body 仍走 json= 通道。"""
        ctx, mock_client = self._patch_httpx(response_body={"ok": True})
        spec = _make_spec(
            method="POST",
            body={"orderId": 123, "name": "x"},
        )
        view = _StubView()
        executor = CallExecutor()

        with ctx:
            result = executor.execute(spec, view)

        call_kwargs = mock_client.request.call_args.kwargs
        self.assertEqual(call_kwargs["json"], {"orderId": 123, "name": "x"})
        self.assertNotIn("content", call_kwargs)
        self.assertEqual(result.status.value, "passed")

    def test_list_body_still_uses_json(self) -> None:
        """向后兼容：list body 仍走 json= 通道。"""
        ctx, mock_client = self._patch_httpx(response_body={"ok": True})
        spec = _make_spec(method="POST", body=[{"id": 1}, {"id": 2}])
        view = _StubView()
        executor = CallExecutor()

        with ctx:
            result = executor.execute(spec, view)

        call_kwargs = mock_client.request.call_args.kwargs
        self.assertEqual(call_kwargs["json"], [{"id": 1}, {"id": 2}])
        self.assertNotIn("content", call_kwargs)

    def test_get_with_str_body_uses_params(self) -> None:
        """GET + str body 走 params= 通道（向后兼容）。"""
        ctx, mock_client = self._patch_httpx(response_body={"ok": True})
        spec = _make_spec(method="GET", body="a=1&b=2")
        view = _StubView()
        executor = CallExecutor()

        with ctx:
            result = executor.execute(spec, view)

        call_kwargs = mock_client.request.call_args.kwargs
        self.assertEqual(call_kwargs["params"], "a=1&b=2")
        self.assertEqual(result.status.value, "passed")

    def test_empty_str_body_preserved(self) -> None:
        """空字符串 str body 不被当作 None 处理。"""
        ctx, mock_client = self._patch_httpx(response_body={"ok": True})
        spec = _make_spec(
            method="POST",
            headers={"Content-Type": "text/plain"},
            body="",
        )
        view = _StubView()
        executor = CallExecutor()

        with ctx:
            result = executor.execute(spec, view)

        call_kwargs = mock_client.request.call_args.kwargs
        self.assertEqual(call_kwargs["content"], b"")
        self.assertEqual(result.status.value, "passed")


if __name__ == "__main__":
    unittest.main()
