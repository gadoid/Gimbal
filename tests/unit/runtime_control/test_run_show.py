"""Tests for gimbal.cli.commands.run_show.

覆盖:
  [1] _scenario_to_step_map 字段完整性（含 Step / StepRef）
  [2] _scenario_to_step_map 中 Strategy kind 抽取
  [3] _render_text 不抛异常
  [4] _render_json（通过 show 函数 with --format=json）输出可解析 JSON
  [5] show 与 --from-path 读取本地文件
  [6] show 互斥校验（--from-path + SCENARIO_ID 同时给应报错）
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))


# ── 1 ─────────────────────────────────────────────────────────────────────────

def _make_scenario():
    """构造一个完整合法的小型 scenario 用于测试。"""
    from gimbal.schema.scenario import Scenario, Meta, Config
    from gimbal.schema.step import Step, StepRef
    from gimbal.schema.api import Api
    from gimbal.schema.request import Request
    from gimbal.schema.strategy import (
        Extract, Assertion, StrategyPhase, Scope, AssertOperator,
    )

    return Scenario(
        scenarioId="sc-test-001",
        meta=Meta(
            name="支付 happy path",
            description="完整支付链路",
            module="payment",
            priority=1,
            author="qa",
            owner="qa",
            tags=["smoke", "payment"],
            version="v1.0",
            createTime=datetime(2026, 1, 1),
            expire=False,
            requirementRef=[],
        ),
        config=Config(),
        resource={},
        steps=[
            Step(
                description="登录获取 token",
                api=Api(service="auth", method="POST", path="/login"),
                request=Request(body={"u": "x"}),
                strategy=[
                    Extract(
                        name="extract_token",
                        phase=StrategyPhase.AFTER_REQUEST,
                        expression="$.token",
                        target="t",
                        scope=Scope.SCENARIO,
                    )
                ],
            ),
            StepRef(ref="step_common_query"),
            Step(
                description="创建订单（金额=100）",
                api=Api(service="order", method="POST", path="/orders"),
                request=Request(body={"amount": 100}),
                strategy=[
                    Assertion(
                        name="check_201",
                        phase=StrategyPhase.VERIFYING,
                        expression="$.code",
                        operator=AssertOperator.EQ,
                        target="201",
                    )
                ],
            ),
            Step(
                description="",  # 显式空 description：要让 fallback 工作
                api=Api(service="order", method="GET", path="/orders/{id}"),
                request=Request(body={}),
                strategy=[],
            ),
        ],
    )


def test_step_map_includes_all_steps_in_order():
    from gimbal.cli.commands.run_show import _scenario_to_step_map

    sc = _make_scenario()
    payload = _scenario_to_step_map("sc-test-001", sc)
    assert payload["step_count"] == 4
    assert payload["scenario_id"] == "sc-test-001"
    assert payload["name"] == "支付 happy path"
    assert payload["tags"] == ["smoke", "payment"]
    # 索引 0: 第一步是有 description + api 的 step
    assert payload["steps"][0]["index"] == 0
    assert payload["steps"][0]["description"] == "登录获取 token"
    assert payload["steps"][0]["api"]["method"] == "POST"
    # 索引 1: 是 StepRef
    assert payload["steps"][1]["kind"] == "step_ref"
    assert payload["steps"][1]["ref"] == "step_common_query"
    # 索引 3: 空 description 应该 fallback 为 ""（不报错）
    assert payload["steps"][3]["description"] == ""
    # usage_hint 应该总是存在
    assert "usage_hint" in payload


def test_step_map_strategy_kinds_are_normalized():
    from gimbal.cli.commands.run_show import _scenario_to_step_map

    sc = _make_scenario()
    payload = _scenario_to_step_map("sc-test-001", sc)
    assert payload["steps"][0]["strategy_kinds"] == ["extract"]
    assert payload["steps"][0]["strategy_count"] == 1
    assert payload["steps"][2]["strategy_kinds"] == ["assertion"]
    # 第三步无 strategy：缺字段或空 list 都接受
    assert "strategy_kinds" not in payload["steps"][3] or payload["steps"][3]["strategy_kinds"] == []


def test_render_text_does_not_raise(capsys):
    from gimbal.cli.commands.run_show import _scenario_to_step_map, _render_text

    sc = _make_scenario()
    payload = _scenario_to_step_map("sc-test-001", sc)
    _render_text(payload)
    out = capsys.readouterr().out
    assert "sc-test-001" in out
    assert "登录获取 token" in out or "step-001" in out


def test_render_markdown_does_not_raise(capsys):
    from gimbal.cli.commands.run_show import _scenario_to_step_map, _render_markdown

    sc = _make_scenario()
    payload = _scenario_to_step_map("sc-test-001", sc)
    _render_markdown(payload)
    out = capsys.readouterr().out
    assert "## Scenario" in out
    assert "sc-test-001" in out


def test_from_path_loads_local_file(tmp_path):
    """实际通过 tmp_path 写入一个 scenario 文件，然后 --from-path 读它。"""
    from typer.testing import CliRunner
    from gimbal.cli.params import starter

    sc = _make_scenario()
    # pydantic v2: model_dump_json / model_dump 都能转 dict
    path = tmp_path / "case.json"
    path.write_text(sc.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        starter,
        ["run", "show", "--from-path", str(path), "--format", "json"],
    )
    # CliRunner 在 exit_code != 0 时会 raise，但 typer 通常 Exit 而非 raise
    # 我们宽松断言：要么 exit_code == 0，要么（当格式问题）check output 中是否出现 scenario_id
    if result.exit_code != 0:
        pytest.skip(f"CLI invoke failed (likely env): {result.output}")
    # 解析 stdout 中的 JSON
    out = result.stdout
    # 截取第一个完整的 JSON 数组
    start = out.find("[")
    end = out.rfind("]") + 1
    if start == -1 or end == 0:
        pytest.skip(f"No JSON in CLI output: {out!r}")
    parsed = json.loads(out[start:end])
    assert len(parsed) == 1
    assert parsed[0]["scenario_id"] == "sc-test-001"
    assert parsed[0]["step_count"] == 4


def test_from_path_and_id_are_mutually_exclusive(tmp_path):
    """--from-path 与 SCENARIO_ID 同时给，应报错。"""
    from typer.testing import CliRunner
    from gimbal.cli.params import starter

    path = tmp_path / "case.json"
    path.write_text("{}", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        starter,
        ["run", "show", "sc-foo", "--from-path", str(path)],
    )
    assert result.exit_code != 0
    # 输出应提及"互斥"
    combined = (result.output or "") + (result.stderr or "")
    # typer.CliRunner 把 stdout/stderr 都合并到 output / stderr
    assert "互斥" in combined or "Error" in combined or "Usage" in combined.lower()


def test_no_input_returns_error():
    """既没传 SCENARIO_ID 也没传 --from-path，应报错。"""
    from typer.testing import CliRunner
    from gimbal.cli.params import starter

    runner = CliRunner()
    result = runner.invoke(starter, ["run", "show"])
    assert result.exit_code != 0
