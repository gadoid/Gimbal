"""gimbal compile / validate / resolve —— 编译管线的截断输出（v2.1 批次 B）。

compile：加载 → schema 校验 → compile_target（Plan）→ p_validate →
打印 Plan JSON（含单元清单与策略）；错误 exit 2。
validate：同一管线但不产出 Plan 明细，只报告校验结论；错误 exit 2。
resolve：静态分析视图（单元清单 + 输入/输出面 + 连线）；--unit 导出单元。

P0-06（2026-09-28）：三命令支持 ``-o json``。失败输出机器可读结构::

    {"ok": false, "errors": [{"code", "message", "location"}, ...]}

code 取稳定错误码（compiler/errors.ErrCode）；CompileError 携带定位，
p_validate 字符串错误以 ``"CODE: message"`` 前缀解析。退出码仍为 2。
"""
from __future__ import annotations

import json
import re
from typing import Annotated

import typer
from pydantic import TypeAdapter, ValidationError

from gimbal.cli.commands.run_launch import normalize_input
from gimbal.cli.common import InputFormat, FormatOpt
from gimbal.compiler.errors import CompileError, ErrCode
from gimbal.compiler.pipeline import compile_target, p_validate
from gimbal.log import get_logger
from gimbal.schema.plan import Plan
from gimbal.schema.scenario import RunUnion

logger = get_logger(__name__)

JsonOpt = Annotated[
    bool,
    typer.Option("-o", "--output", help="机器可读 JSON 输出（失败时输出结构化错误）"),
]

_CODE_PREFIX_RE = re.compile(r"^([A-Z][A-Z0-9_]*): (.*)$", re.S)


def _err_item(code: str, message: str, location: dict | None = None) -> dict:
    return {"code": code, "message": message, "location": location or {}}


def _string_error_item(e: str) -> dict:
    m = _CODE_PREFIX_RE.match(e)
    if m:
        return _err_item(m.group(1), m.group(2))
    return _err_item(ErrCode.GENERIC, e)


def _emit_json_errors(errors: list) -> None:
    items = [e.to_json() if isinstance(e, CompileError) else _string_error_item(e)
             for e in errors]
    typer.echo(json.dumps({"ok": False, "errors": items}, ensure_ascii=False, indent=2))


def _load_target(source: str, fmt, json_mode: bool = False) -> tuple[bool, object]:
    """加载 + schema 校验；失败时（json_mode 下输出结构）返回 (False, err)。"""
    try:
        payload = normalize_input(source, None, fmt)
        return True, TypeAdapter(RunUnion).validate_python(payload)
    except ValidationError as exc:
        err = _err_item(ErrCode.SCHEMA_INVALID, str(exc))
    except Exception as exc:  # noqa: BLE001
        err = _err_item(ErrCode.GENERIC, str(exc))
    if json_mode:
        _emit_json_errors([CompileError(err["message"], code=err["code"],
                                        location=err["location"])])
    else:
        typer.secho(f"schema 校验失败: {err['message']}", fg=typer.colors.RED, err=True)
    return False, err


def _compile_plan_or_exit(target, json_mode: bool) -> Plan:
    """编译（权威协议/策略表）；失败时按模式输出并 exit 2。"""
    try:
        from gimbal.protocols.registry import build_default_protocol_registry
        from gimbal.strategy.dispatcher import build_default_dispatcher as _bdd
        return compile_target(target, protocols=build_default_protocol_registry(),
                              strategies=_bdd())
    except CompileError as exc:
        if json_mode:
            _emit_json_errors([exc])
        else:
            typer.secho(f"编译失败: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    except Exception as exc:  # noqa: BLE001
        wrapped = CompileError(str(exc), code=ErrCode.GENERIC)
        if json_mode:
            _emit_json_errors([wrapped])
        else:
            typer.secho(f"编译失败: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)


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
    json_mode: JsonOpt = False,
) -> None:
    """编译为 Plan 并打印（不执行）。"""
    ok, target = _load_target(source, fmt, json_mode)
    if not ok:
        raise typer.Exit(code=2)
    plan = _compile_plan_or_exit(target, json_mode)

    errors = p_validate(plan)
    out = plan.model_dump(mode="json") if full else _plan_summary(plan)
    typer.echo(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    if errors:
        if json_mode:
            _emit_json_errors(errors)
        else:
            typer.secho("校验问题:", fg=typer.colors.YELLOW, err=True)
            for e in errors:
                typer.secho(f"  - {e}", fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(code=2)


def validate_cmd(
    source: Annotated[str, typer.Argument(help="Scenario/Graph 文件路径", metavar="SOURCE")],
    fmt: FormatOpt = InputFormat.auto,
    json_mode: JsonOpt = False,
) -> None:
    """校验：schema + 编译管线 + Plan 校验（不执行）。"""
    ok, target = _load_target(source, fmt, json_mode)
    if not ok:
        raise typer.Exit(code=2)
    plan = _compile_plan_or_exit(target, json_mode)

    errors = p_validate(plan)
    if errors:
        if json_mode:
            _emit_json_errors(errors)
        else:
            typer.secho("校验失败:", fg=typer.colors.RED, err=True)
            for e in errors:
                typer.secho(f"  - {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    if json_mode:
        typer.echo(json.dumps({
            "ok": True,
            "kind": target.kind,
            "mode": plan.mode,
            "units": len(plan.units),
            "parallel": plan.policy.parallel,
        }, ensure_ascii=False))
    else:
        typer.secho(
            f"OK: kind={target.kind} mode={plan.mode} units={len(plan.units)} "
            f"parallel={plan.policy.parallel}",
            fg=typer.colors.GREEN,
        )


def resolve_cmd(
    source: Annotated[str, typer.Argument(help="Scenario/Graph 文件路径", metavar="SOURCE")],
    fmt: FormatOpt = InputFormat.auto,
    unit: Annotated[str | None, typer.Option("--unit", help="导出指定单元为独立可调 scenario（inputs 注入 config.vars）")] = None,
    json_mode: JsonOpt = False,
) -> None:
    """展示编译视图：单元清单 + 静态分析输入/输出面 + 连线；--unit 导出单元。"""
    import json as _json
    from gimbal.compiler.analysis import analyze_scenario

    ok, target = _load_target(source, fmt, json_mode)
    if not ok:
        raise typer.Exit(code=2)
    plan = _compile_plan_or_exit(target, json_mode)

    if unit is not None:
        match = next((u for u in plan.all_units_in_order if u.id == unit), None)
        if match is None:
            msg = (f"单元 {unit!r} 不存在；可用: {[u.id for u in plan.all_units_in_order]}")
            if json_mode:
                _emit_json_errors([CompileError(msg, code=ErrCode.GENERIC,
                                                location={"unit": unit})])
            else:
                typer.secho(msg, fg=typer.colors.RED, err=True)
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
