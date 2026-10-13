"""B-2(2026-10-13)另一半:断言执行器产出 auth 结构化标记。

响应状态断言($.call.response.status / legacy $.response_status)失败
且实际值 401/403 → 消息尾附 ``[auth_status:NNN]``;其他目标/其他值/
通过断言一律不加。标记是引擎 ``_error_kind_of`` auth 分类的唯一
verifying 面来源 —— 没有它,业务值 401 的误判回归就拦不住。
"""
from __future__ import annotations

from typing import Any

from gimbal.schema import Assertion
from gimbal.strategy.builtin.assertion import AssertionExecutor


class _ScratchView:
    """AssertionExecutor 消费面最小替身:scratch jget + 记录no-op。"""

    def __init__(self, scratch: dict) -> None:
        self._scratch = scratch

    # executor 只用 record_assertion / scratch jget / read_variable 兜底
    def record_assertion(self, result: Any) -> None:  # noqa: ANN401
        pass

    def read_variable(self, key: str, **_: Any) -> None:
        return None

    def get_scratch_dict(self) -> dict:
        return self._scratch


def _run(target: str, actual: Any, expected: Any = "200") -> str:
    view = _ScratchView({"call": {"response": {"status": actual}}})
    spec = Assertion(target=target, operator="eq", expected=expected)
    result = AssertionExecutor().execute(spec, view)
    return str(result.message)


def test_status_target_401_403_get_marker():
    assert _run("$.call.response.status", "401").endswith("[auth_status:401]")
    assert _run("$.call.response.status", "403").endswith("[auth_status:403]")
    # 自定义 message 同样带标记(标记在 message 之后追加)
    view = _ScratchView({"call": {"response": {"status": 401}}})
    spec = Assertion(target="$.call.response.status", operator="eq",
                     expected="200", message="登录态校验")
    msg = str(AssertionExecutor().execute(spec, view).message)
    assert msg.endswith("[auth_status:401]")
    assert msg.startswith("登录态校验")


def test_other_targets_and_values_no_marker():
    # 业务值恰好 401,但目标不是响应状态 → 不加(引擎侧即 logic)
    assert "[auth_status" not in _run("$.data.code", "401")
    # 状态目标但值非 401/403(如 500/200) → 不加
    assert "[auth_status" not in _run("$.call.response.status", "500")
    # legacy 目标同样覆盖
    view = _ScratchView({"response_status": "401"})
    spec = Assertion(target="$.response_status", operator="eq",
                     expected="200")
    msg = str(AssertionExecutor().execute(spec, view).message)
    assert msg.endswith("[auth_status:401]")
