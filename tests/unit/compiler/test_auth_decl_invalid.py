"""C-3(2026-10-13):call.auth 声明自洽的编译期防线。

两个此前静默的缺陷形态:
* 声明 ``call.auth``(bearer/basic/custom)但无 ``call.user`` → 运行期
  ``login("")`` 恒空,**静默发出无认证请求**;
* ``auth=custom`` 签名器名拼错 → 静默回落 md5 签名。

p_validate 规则 7(AUTH_DECL_INVALID)在编译期拦截;合法声明不受影响。
"""
from __future__ import annotations

import pytest

from gimbal.compiler.errors import CompileError
from gimbal.compiler.pipeline import compile_plan
from gimbal.schema import Scenario


def _scenario(steps: list[dict]) -> Scenario:
    return Scenario.model_validate({
        "kind": "scenario", "scenarioId": "sc-c3",
        "meta": {"name": "c3"},
        "config": {"users": {"u1": {"username": "a", "password": "b"}}},
        "resource": {},
        "steps": steps,
    })


def _step(auth: str | None = None, user: str | None = None,
          signer: str | None = None) -> dict:
    call: dict = {"protocol": "http", "method": "GET", "path": "/a",
                  "service": "s", "headers": {}}
    if auth:
        call["auth"] = auth
    if user:
        call["user"] = user
    if signer:
        call["auth_signer"] = signer
    return {"kind": "step", "call": call,
            "request": {"kind": "request", "body": {}}, "strategy": []}


def test_auth_without_user_rejected():
    with pytest.raises(CompileError) as ei:
        compile_plan(_scenario([_step(auth="bearer")]))
    assert "AUTH_DECL_INVALID" in str(ei.value)
    assert "缺 call.user" in str(ei.value)


def test_custom_unknown_signer_rejected():
    with pytest.raises(CompileError) as ei:
        compile_plan(_scenario([
            _step(auth="custom", user="u1", signer="md6sign")]))
    assert "AUTH_DECL_INVALID" in str(ei.value)
    assert "md6sign" in str(ei.value)


def test_valid_declarations_pass():
    # 合法声明组合全部编译通过(compile_plan 内部即跑 p_validate,错误
    # 会以 CompileError 抛出 —— 不抛即过)
    compile_plan(_scenario([
        _step(auth="bearer", user="u1"),
        _step(auth="basic", user="u1"),
        _step(auth="custom", user="u1"),               # 缺省 md5sign
        _step(auth="custom", user="u1", signer="standard.bearer"),
        _step(auth="none"),
        _step(user="u1"),                              # 遗留 md5(无声明)
        _step(),                                       # 裸调用
    ]))
