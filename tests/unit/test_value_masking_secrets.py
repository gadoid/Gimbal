"""r5 4.3 按值掩码(2026-11-10):登记点 + 证据出口。

评审五轮 4.3 裁定:项目凭证对成员的边界从「键名脱敏」升级为「按值
掩码」—— 成员把 ``${auth.<槽>.<字段>}`` 的解析值放进键名普通的字段 /
提取变量时,events / rows / details 也只见 ``***redacted***``。

* 登记点 = ``AuthRegistry.set``(users 定义输入)+ ``apply_token``
  (运行期访问令牌);
* 出口 = ``CallResult.to_evidence``(事件/归档/报告统一证据面)/
  StepEndEvent 投影(extracts / assertions / error_brief)/ details 行
  (run.finished 随终线发平台);
* **原值面不受影响**:scratch / 断言 / 提取仍拿真值求值(掩码只在
  证据出口,见 ``CallResult.to_scratch`` 契约)。
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

import pytest

from gimbal.auth.registry import AuthRegistry
from gimbal.auth.session import AuthSession
from gimbal.context.projections import project_step_completed
from gimbal.core.runner import Engine
from gimbal.protocols import secrets
from gimbal.protocols.result import CallResult

SECRET = "proj-pw-9876543210"
TOKEN = "jwt-abcdef1234567890"


@pytest.fixture(autouse=True)
def _clean_registry():
    secrets.reset_for_tests()
    yield
    secrets.reset_for_tests()


# ── 登记册 ──────────────────────────────────────────────────────

def test_register_threshold_and_scrub_shapes():
    # 非字符串 / 空串 / 过短 / 掩码占位自身 一律不登记
    secrets.register_secret(None, 42, "", "short", "***redacted***", SECRET)
    assert secrets.registered_values() == (SECRET,)
    # 子串嵌在大串里也掩;dict 的值与键、list 逐项;返回新结构不改入参
    src = {"note": f"login {SECRET} ok", SECRET: "x",
           "items": [f"Bearer {SECRET}"], "n": 3}
    out = secrets.scrub(src)
    assert out == {"note": f"login {secrets.REDACTED} ok",
                   secrets.REDACTED: "x",
                   "items": [f"Bearer {secrets.REDACTED}"], "n": 3}
    assert src["note"] == f"login {SECRET} ok"
    # 空册零开销路径:原对象直通(证据热路径无登记值时不产生拷贝)
    secrets.reset_for_tests()
    same = {"k": "v"}
    assert secrets.scrub(same) is same


def test_registry_set_registers_secrets_not_username():
    reg = AuthRegistry()
    s = AuthSession(url="http://a", username="proj-u", password=SECRET)
    reg.set("qa1", s)
    assert secrets.registered_values() == (SECRET,)      # username/url 不入册
    s.apply_token(TOKEN, 7200)
    assert set(secrets.registered_values()) == {SECRET, TOKEN}


# ── 出口①:to_evidence(事件/归档/报告统一证据面)────────────────

def test_to_evidence_masks_plain_keyed_secret():
    secrets.register_secret(SECRET)
    cr = CallResult(
        protocol="http",
        request={"note": SECRET, "password": SECRET},   # 普通键名 + 敏感键名
        response={"status": 200, "meta": {"x-trace": f"tok={SECRET}"},
                  "body": {"data": [SECRET, "keep"]}},
    )
    ev = cr.to_evidence()
    assert ev["request"]["note"] == secrets.REDACTED
    assert ev["request"]["password"] == secrets.REDACTED   # 键名口径照旧
    assert ev["response"]["meta"]["x-trace"] == f"tok={secrets.REDACTED}"
    assert ev["response"]["body"]["data"] == [secrets.REDACTED, "keep"]
    # 原值面(scratch)不受影响:断言/提取仍拿真值
    assert cr.to_scratch()["request"]["note"] == SECRET


# ── 出口②:StepEndEvent 投影(extracts / assertions / error_brief)──

def _ctx(**over) -> SimpleNamespace:
    assertion = SimpleNamespace(
        name="eq", target="$.x", operator="eq",
        expected="ok", actual=f"got {SECRET}", passed=False,
        message=f"expected ok got {SECRET}")
    base = dict(
        scenario_id="sc-1", step_id="s1", ended_at=None,
        inputs=SimpleNamespace(step_name="查单", description=""),
        outcome=SimpleNamespace(
            status=SimpleNamespace(value="passed"), duration_ms=1.0,
            promotions_made=[], retry_count=0, error_info=None,
            assertions=[assertion],
            extracted={"login_hint": TOKEN, "batch_no": "keep-me-plain"}),
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_step_end_projection_masks_extracts_and_assertions():
    secrets.register_secret(TOKEN, SECRET)
    ev = project_step_completed(_ctx(), "run-1")
    # 提取值:普通键名(login_hint)也掩 —— 键名脱敏逃不掉的路径
    assert ev.extracts[0]["value"] == secrets.REDACTED
    # 断言 actual / message 带值 → 掩;无关值照旧
    assert ev.assertions[0]["actual"] == f"got {secrets.REDACTED}"
    assert ev.assertions[0]["message"] == f"expected ok got {secrets.REDACTED}"
    assert ev.assertions[0]["expected"] == "ok"
    assert ev.extracts[1]["value"] == "keep-me-plain"


def test_step_end_projection_error_brief_masked():
    secrets.register_secret(SECRET)
    ctx = _ctx(outcome=SimpleNamespace(
        status=SimpleNamespace(value="error"), duration_ms=1.0,
        promotions_made=[], retry_count=0,
        error_info=SimpleNamespace(message=f"call failed: {SECRET}"),
        assertions=[], extracted={}))
    ev = project_step_completed(ctx, "run-1")
    assert ev.error_brief == f"call failed: {secrets.REDACTED}"


# ── 出口③:details 行(run.finished 随终线发平台)────────────────

def _detail_result(**over) -> SimpleNamespace:
    base = dict(
        scenario_id="sc-1", status="failed", duration_ms=1.0,
        halted=False, halt_reason=f"call failed: {SECRET}",
        outputs={"cursor": SECRET},
        step_results=[SimpleNamespace(
            step_id="s1", status="failed", duration_ms=1.0,
            error=f"login {SECRET} rejected", error_phase="calling",
            error_kind="auth", repaired=False)],
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_detail_row_masks_error_strings_and_outputs():
    secrets.register_secret(SECRET)
    row = Engine._detail_row(_detail_result())
    assert secrets.REDACTED in row["halt_reason"]
    # cursor 键在键名脱敏的游标豁免表里,但值掩照掩(D3 豁免的是键名口径)
    assert row["outputs"]["cursor"] == secrets.REDACTED
    assert secrets.REDACTED in row["steps"][0]["error"]
    assert SECRET not in repr(row)


def test_detail_row_no_registry_passthrough():
    # 空册时行为与旧完全一致(未登记 = 不掩,不引入新脱敏噪声)
    row = Engine._detail_row(_detail_result())
    assert row["outputs"]["cursor"] == SECRET
