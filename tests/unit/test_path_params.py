"""RS2 / R5b：http path 占位符代入（Release v4.4 §4.6）。

模板归 binding（plate 投影，`{name}`），值归场景（`call.path_params`）；
代入在执行器 build_spec 一处完成（平台模式与 CLI 模式共用），缺键报
``PATH_PARAM_MISSING``。`path_params` 是 http 协议参数（C 类），不改 M2
结构——`HttpCallParams` 声明字段、执行器代入。
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from gimbal.protocols.base import ProtocolCallContext   # noqa: E402
from gimbal.protocols.builtin.http import HttpCallParams  # noqa: E402
from gimbal.schema import Call                           # noqa: E402
from gimbal.strategy.builtin.call import CallExecutor    # noqa: E402


def _pctx(call: Call) -> ProtocolCallContext:
    return ProtocolCallContext(
        call=call, step_id="step-000",
        services={"fin-service": "https://fin.example.com"},
    )


def _call(**extra) -> Call:
    return Call.model_validate({
        "protocol": "http", "service": "fin-service",
        "method": "GET", **extra,
    })


class TestPathParams:
    def test_params_model_accepts_path_params(self) -> None:
        p = HttpCallParams.model_validate(
            {"path": "/a/{uid}", "path_params": {"uid": "u1"}})
        assert p.path_params == {"uid": "u1"}

    def test_substitution_in_url(self) -> None:
        ex = CallExecutor()
        call = _call(path="/users/{uid}/orders/{oid}",
                     path_params={"uid": "u1", "oid": "o9"})
        spec = ex.build_spec(call, _pctx(call))
        assert spec.url == "https://fin.example.com/users/u1/orders/o9"

    def test_variable_template_value_passthrough(self) -> None:
        """值可以是 ${var} 变量模板——原样代入,随变量机制展开。"""
        ex = CallExecutor()
        call = _call(path="/users/{uid}",
                     path_params={"uid": "${user.id}"})
        spec = ex.build_spec(call, _pctx(call))
        assert spec.url == "https://fin.example.com/users/${user.id}"

    def test_missing_key_reports_path_param_missing(self) -> None:
        from gimbal.strategy.executor_base import StrategyStatus

        ex = CallExecutor()
        call = _call(path="/users/{uid}/{oid}",
                     path_params={"uid": "u1"})           # 缺 oid
        result = ex.build_spec(call, _pctx(call))
        assert result.status == StrategyStatus.ERROR
        assert "PATH_PARAM_MISSING" in result.message
        assert "{oid}" in result.message

    def test_no_params_leaves_path_untouched(self) -> None:
        """无 path_params 时 path 原样使用(存量路径无双花括号语义)。"""
        ex = CallExecutor()
        call = _call(path="/plain")
        spec = ex.build_spec(call, _pctx(call))
        assert spec.url.endswith("/plain")
