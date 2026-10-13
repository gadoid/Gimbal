"""集成 P2/Y2:G7 error_kind 分类 + G2 outputs 脱敏(明细行暴露)。

- auth 只认结构化来源(B-2,2026-10-13 收紧):响应状态断言失败且实际
  401/403 时断言执行器追加的 "[auth_status:NNN]" 标记,与 calling 阶段
  的登录失败词表/亲历 40x(凭证失效信号,平台侧据此暂停集成实例);
  业务值恰好 401 的普通断言/提取失败不再误判;
- calling 阶段按超时/传输;其余(断言/提取失败)→ logic;通过 → none;
- _detail_row:每步 error_kind;顶层 outputs 过脱敏键表(与
  CallResult.to_evidence 同键表口径),深拷贝不就地改。
"""
from __future__ import annotations

from types import SimpleNamespace

from gimbal.core.runner import Engine


def _step(error=None, phase=None, status=None) -> SimpleNamespace:
    return SimpleNamespace(step_id="s1", error=error, error_phase=phase,
                           status=status or ("passed" if error is None
                                             else "failed"),
                           duration_ms=1.0, repaired=False)


# ── _error_kind_of ───────────────────────────────────────────────

def test_auth_by_structured_marker_and_calling_status():
    # ① 断言执行器产出的结构化标记(唯一 verifying 面 auth 来源)
    assert Engine._error_kind_of(
        _step(error="FAIL: expected 200 eq 401 [auth_status:401]",
              phase="verifying")) == "auth"
    # ② calling 阶段亲历的 40x(登录器/传输层)
    assert Engine._error_kind_of(
        _step(error="[calling] 403 Forbidden", phase="calling")) == "auth"


def test_business_401_no_longer_misclassified():
    """B-2 回归(2026-10-13 检查文档 B-2 实测反例):业务值恰好含
    401/403 的错误文本不得判 auth —— 误判会把正常集成实例暂停,
    且要人工复活。"""
    assert Engine._error_kind_of(
        _step(error="FAIL: expected 42 eq 401",
              phase="verifying")) == "logic"
    assert Engine._error_kind_of(
        _step(error="订单号 401-2026 提取失败",
              phase="after_request")) == "logic"
    # 无标记的裸状态断言失败同样不算(标记只能由断言执行器产出)
    assert Engine._error_kind_of(
        _step(error="期望 status 200,实际 401",
              phase="verifying")) == "logic"


def test_auth_by_login_failure_in_calling():
    assert Engine._error_kind_of(
        _step(error="[calling] 登录失败: 密码错误", phase="calling")) == "auth"
    assert Engine._error_kind_of(
        _step(error="[calling] unauthorized", phase="calling")) == "auth"
    # verifying 阶段的普通"auth"字样不算(断言文本常见词,防误判)
    assert Engine._error_kind_of(
        _step(error="字段 authorization_id 不匹配", phase="verifying")) != "auth"


def test_timeout_transport_logic_none():
    assert Engine._error_kind_of(
        _step(error="[calling] request timed out after 30s",
              phase="calling")) == "timeout"
    assert Engine._error_kind_of(
        _step(error="[calling] connect error", phase="calling")) == "transport"
    assert Engine._error_kind_of(
        _step(error="$.data.amount 期望 1 实际 2",
              phase="verifying")) == "logic"
    assert Engine._error_kind_of(_step()) == "none"
    assert Engine._error_kind_of(
        _step(error="", phase=None, status="passed")) == "none"


# ── _detail_row:outputs 脱敏 + error_kind 落行 ──────────────────

def _result(outputs=None, steps=()) -> SimpleNamespace:
    return SimpleNamespace(
        scenario_id="sc-t", status="failed", duration_ms=1.0,
        halted=False, halt_reason=None, outputs=outputs or {},
        step_results=list(steps))


def test_detail_row_outputs_redacted_and_isolated():
    outputs = {"order_id": "O1", "access_token": "s3cret",
               "nested": {"password": "p", "ok": 1}}
    row = Engine._detail_row(_result(outputs=outputs))
    out = row["outputs"]
    assert out["order_id"] == "O1"
    assert out["access_token"] == "***redacted***"
    assert out["nested"]["password"] == "***redacted***"
    assert out["nested"]["ok"] == 1
    # 深拷贝隔离:改行输出不动原对象
    out["order_id"] = "MUT"
    assert outputs["order_id"] == "O1"


def test_detail_row_steps_carry_error_kind():
    row = Engine._detail_row(_result(steps=[
        _step(error="期望 200 实际 401 [auth_status:401]", phase="verifying"),
        _step(),
    ]))
    assert row["steps"][0]["error_kind"] == "auth"
    assert row["steps"][1]["error_kind"] == "none"
    # 历史字段原样(error/error_phase/duration_ms)
    assert row["steps"][0]["error_phase"] == "verifying"
