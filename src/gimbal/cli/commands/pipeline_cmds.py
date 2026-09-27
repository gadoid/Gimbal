"""gimbal compile / validate —— 编译管线的截断输出（v2.1 批次 B）。

compile：加载 → schema 校验 → compile_target（Plan）→ validate_plan →
打印 Plan JSON（含单元清单与策略）；错误 exit 2。
validate：同一管线但不产出 Plan 明细，只报告校验结论；错误 exit 2。
"""
from __future__ import annotations

import json
from typing import Annotated

import typer
from pydantic import TypeAdapter

from gimbal.cli.commands.run_launch import normalize_input
from gimbal.cli.common import InputFormat, FormatOpt
from gimbal.compiler.pipeline import CompileError, compile_target, validate_plan
from gimbal.log import get_logger
from gimbal.schema.plan import Plan
from gimbal.schema.scenario import RunUnion

logger = get_logger(__name__)


def _load_target(source: str, fmt):
    payload = normalize_input(source, None, fmt)
    return TypeAdapter(RunUnion).validate_python(payload)


def _plan_summary(plan: Plan) -> dict:
    """Plan 的可读摘要（compile 打印用；完整 scenario 副本不在摘要里）。"""
    return {
        "mode": plan.mode,
        "implicit": plan.implicit,
        "suite_id": plan.suite_id,
        "policy": plan.policy.model_dump(),
        "before": [u.id for u in plan.before],
        "units": [
            {
                "id": u.id,
                "inputs": u.inputs,
                "needs": u.needs,
                "shared_key": u.shared_key,
                "policy": u.policy.model_dump(),
                "scenario_id": u.scenario.scenarioId,
                "steps": len(u.scenario.steps),
            }
            for u in plan.units
        ],
        "after": [u.id for u in plan.after],
    }


def compile_cmd(
    source: Annotated[str, typer.Argument(help="Scenario/Graph 文件路径", metavar="SOURCE")],
    fmt: FormatOpt = InputFormat.auto,
    full: Annotated[bool, typer.Option("--full", help="输出完整 Plan（含生效副本）而非摘要")] = False,
) -> None:
    """编译为 Plan 并打印（不执行）。"""
    try:
        target = _load_target(source, fmt)
        plan = compile_target(target)
    except Exception as exc:  # noqa: BLE001
        typer.secho(f"编译失败: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    errors = validate_plan(plan)
    out = plan.model_dump(mode="json") if full else _plan_summary(plan)
    typer.echo(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    if errors:
        typer.secho("校验问题:", fg=typer.colors.YELLOW, err=True)
        for e in errors:
            typer.secho(f"  - {e}", fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(code=2)


def validate_cmd(
    source: Annotated[str, typer.Argument(help="Scenario/Graph 文件路径", metavar="SOURCE")],
    fmt: FormatOpt = InputFormat.auto,
) -> None:
    """校验：schema + 编译管线 + Plan 校验（不执行）。"""
    try:
        target = _load_target(source, fmt)
    except Exception as exc:  # noqa: BLE001
        typer.secho(f"schema 校验失败: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    try:
        plan = compile_target(target)
    except CompileError as exc:
        typer.secho(f"编译失败: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    errors = validate_plan(plan)
    if errors:
        typer.secho("校验失败:", fg=typer.colors.RED, err=True)
        for e in errors:
            typer.secho(f"  - {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    typer.secho(
        f"OK: kind={target.kind} mode={plan.mode} units={len(plan.units)} "
        f"parallel={plan.policy.parallel}",
        fg=typer.colors.GREEN,
    )


def resolve_cmd(
    source: Annotated[str, typer.Argument(help="Scenario/Graph 文件路径", metavar="SOURCE")],
    fmt: FormatOpt = InputFormat.auto,
    unit: Annotated[str | None, typer.Option("--unit", help="导出指定单元为独立可调 scenario（inputs 注入 config.vars）")] = None,
) -> None:
    """展示编译视图：单元清单 + 静态分析输入/输出面 + 连线；--unit 导出单元。"""
    import json as _json
    from gimbal.compiler.analysis import analyze_scenario

    try:
        target = _load_target(source, fmt)
        plan = compile_target(target)
    except Exception as exc:  # noqa: BLE001
        typer.secho(f"解析失败: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    if unit is not None:
        match = next((u for u in plan.all_units_in_order if u.id == unit), None)
        if match is None:
            typer.secho(
                f"单元 {unit!r} 不存在；可用: {[u.id for u in plan.all_units_in_order]}",
                fg=typer.colors.RED, err=True,
            )
            raise typer.Exit(code=2)
        # 统一注入原语第三用：--unit 导出 = inputs 注入为 scenario vars 的独立副本
        scenario = match.scenario
        if match.inputs:
            merged = {**(scenario.config.vars or {}), **match.inputs}
            scenario = scenario.model_copy(update={
                "config": scenario.config.model_copy(update={"vars": merged}),
            })
        typer.echo(_json.dumps(scenario.model_dump(mode="json"), ensure_ascii=False,
                              indent=2, default=str))
        return

    decl_map = {u.id: u for u in plan.all_units_in_order}
    view = {
        "mode": plan.mode,
        "policy": plan.policy.model_dump(),
        "units": [],
    }
    for u in plan.all_units_in_order:
        analysis = analyze_scenario(u.scenario)
        view["units"].append({
            "id": u.id,
            "needs": u.needs,
            "inputs_literal": u.inputs,
            "inputs_required": sorted(analysis.inputs),
            "inputs_optional": sorted(analysis.optional_inputs),
            "outputs": sorted(analysis.outputs) or None,
            "wiring": plan.wiring.get(u.id, {}),
        })
    typer.echo(_json.dumps(view, ensure_ascii=False, indent=2, default=str))
