"""gimbal run show —— 只读解析本地 Scenario 文件，输出步骤索引 → 描述的映射。

不执行、不 bootstrap 框架；只做"读 + 展示"，方便：
  - 人快速了解 scenario 内容
  - CLI 操作：决定 `--step-to=<idx>` 该设到几
  - AI 操作：把 step_map 当结构化上下文喂给 LLM

输入只有一种来源：--from-path 本地 JSON/YAML 文件。
（历史上有过"从资产仓库按 ID 拉取"的模式，随引用机制一并移除。）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, Literal

import typer

from gimbal.cli.context import CLIContext
from gimbal.log import get_logger
from gimbal.schema.scenario import Scenario
from gimbal.schema.step import Step

logger = get_logger(__name__)


# ── 步骤元数据抽取 ────────────────────────────────────────────────────────────────

def _step_kind(step: object) -> str:
    """返回 step 的类型标签：'step' / 'unknown'。"""
    kind = getattr(step, "kind", None)
    if isinstance(step, Step):
        return "step"
    return str(kind) if kind else "unknown"


def _step_summary(step: object) -> dict:
    """抽取 step 的轻量元数据（不动 HTTP、不跑策略）。"""
    out: dict = {
        "kind": _step_kind(step),
        "description": getattr(step, "description", None) or "",
    }
    # Api 描述（method + path + service）
    api = getattr(step, "api", None)
    if api is not None and not isinstance(api, type(None)):
        method = getattr(api, "method", None) or ""
        path = getattr(api, "path", None) or ""
        service = getattr(api, "service", None) or ""
        if method or path or service:
            out["api"] = {
                "service": service,
                "method":  method,
                "path":    path,
            }
    # Strategy summary（仅 kinds，不打印完整表达式）
    strategies = getattr(step, "strategy", None)
    if strategies:
        kinds = []
        for s in strategies:
            k = getattr(s, "kind", None) or type(s).__name__.lower()
            kinds.append(k)
        out["strategy_kinds"] = kinds
        out["strategy_count"] = len(kinds)
    return out


def _scenario_to_step_map(scenario_id: str, scenario: Scenario) -> dict:
    """把整个 Scenario 转为只读的结构化映射（含 meta、tag、step 索引表）。"""
    meta = getattr(scenario, "meta", None)
    steps = list(getattr(scenario, "steps", []) or [])

    step_rows = []
    for idx, step in enumerate(steps):
        row = {"index": idx, **_step_summary(step)}
        step_rows.append(row)

    return {
        "scenario_id":   scenario_id,
        "name":          getattr(meta, "name", None) if meta else None,
        "description":   getattr(meta, "description", None) if meta else None,
        "tags":          list(getattr(meta, "tags", []) or []) if meta else [],
        "module":        getattr(meta, "module", None) if meta else None,
        "priority":      getattr(meta, "priority", None) if meta else None,
        "author":        getattr(meta, "author", None) if meta else None,
        "step_count":    len(step_rows),
        "steps":         step_rows,
        "usage_hint": {
            "stop_at_step":      "gimbal run launch <file> --step-to=<index>",
            "stop_at_multiple":  "gimbal run launch <file> --breakpoint=<index>",
        },
    }


# ── 渲染器 ───────────────────────────────────────────────────────────────────────

def _render_table(payload: dict, no_color: bool = False) -> None:
    """人类可读的彩色表格（rich）；no_color 为 True 时降级为纯文本。"""
    meta = payload
    head = f"Scenario:  {meta['scenario_id']}\n"
    head += f"Name:      {meta.get('name') or '?'}\n"
    head += f"Module:    {meta.get('module') or '-'}\n"
    head += f"Priority:  {meta.get('priority')}\n"
    head += f"Author:    {meta.get('author') or '-'}\n"
    head += f"Tags:      [{', '.join(meta.get('tags') or []) or '-'}]\n"
    head += f"Steps:     {meta['step_count']}\n"
    head += (
        f"Desc:      {meta.get('description') or '-'}\n"
    )
    typer.echo(head)

    if not meta["steps"]:
        typer.echo("(no steps)")
        return

    # 计算列宽：index / kind / description
    rows = []
    for s in meta["steps"]:
        kind = s["kind"]
        desc = s["description"] or "(no description)"
        api = s.get("api") or {}
        api_str = ""
        if api:
            method = api.get("method") or "*"
            path = api.get("path") or "*"
            api_str = f"  [{method} {path}]"
        rows.append((str(s["index"]), kind, desc + api_str))

    idx_w = max(len("idx"), max(len(r[0]) for r in rows))
    kind_w = max(len("kind"), max(len(r[1]) for r in rows))

    sep = f"┌─{'─' * idx_w}─┬─{'─' * kind_w}─┬────────────────────────────────────────────────────┐"
    mid = f"├─{'─' * idx_w}─┼─{'─' * kind_w}─┼────────────────────────────────────────────────────┤"
    header = f"│ {'idx'.ljust(idx_w)} │ {'kind'.ljust(kind_w)} │ description                                        │"
    bottom = f"└─{'─' * idx_w}─┴─{'─' * kind_w}─┴────────────────────────────────────────────────────┘"
    line_fmt = f"│ {{}} │ {{}} │ {{}} │"

    typer.echo(sep)
    typer.echo(header)
    typer.echo(mid)
    desc_w = 52
    for idx_s, kind_s, desc_s in rows:
        d = (desc_s[:desc_w - 3] + "...") if len(desc_s) > desc_w else desc_s
        typer.echo(line_fmt.format(idx_s.ljust(idx_w), kind_s.ljust(kind_w), d.ljust(desc_w)))
    typer.echo(bottom)


def _render_text(payload: dict) -> None:
    """纯文本（无 unicode box-drawing），CI 友好。"""
    print(f"Scenario: {payload['scenario_id']}")
    print(f"  name:        {payload.get('name') or '?'}")
    print(f"  module:      {payload.get('module') or '-'}")
    print(f"  priority:    {payload.get('priority')}")
    print(f"  author:      {payload.get('author') or '-'}")
    print(f"  tags:        [{', '.join(payload.get('tags') or []) or '-'}]")
    print(f"  description: {payload.get('description') or '-'}")
    print(f"  step_count:  {payload['step_count']}")
    print()
    print(f"  {'idx':>4}  {'kind':<10}  {'description':<60}")
    print(f"  {'-'*4}  {'-'*10}  {'-'*60}")
    for s in payload["steps"]:
        kind = s["kind"]
        desc = (s["description"] or "(no description)")[:60]
        print(f"  {s['index']:>4}  {kind:<10}  {desc:<60}")


def _render_markdown(payload: dict) -> None:
    """Markdown 表格，方便贴工单 / PR。"""
    print(f"## Scenario: `{payload['scenario_id']}`")
    print()
    print(f"- **Name**: {payload.get('name') or '?'}")
    print(f"- **Module**: {payload.get('module') or '-'}")
    print(f"- **Priority**: {payload.get('priority')}")
    print(f"- **Author**: {payload.get('author') or '-'}")
    print(f"- **Tags**: {', '.join(payload.get('tags') or []) or '-'}")
    print(f"- **Steps**: {payload['step_count']}")
    print()
    print(f"> {payload.get('description') or '(no description)'}")
    print()
    print("| idx | kind | description |")
    print("| --- | ---- | ----------- |")
    for s in payload["steps"]:
        kind = s["kind"]
        desc = (s["description"] or "(no description)").replace("|", "\\|")
        print(f"| {s['index']} | {kind} | {desc} |")
    print()
    print("**Usage**:")
    print(f"- 跑到 N 步后停止：`gimbal run launch <file> --step-to=<idx>`")
    print(f"- 在 idx 处暂停：`gimbal run launch <file> --breakpoint=<idx>`")


# ── 主入口 ───────────────────────────────────────────────────────────────────────

def show(
    ctx: typer.Context,
    from_path: Annotated[
        Path,
        typer.Option(
            "--from-path",
            help="从本地 JSON/YAML 文件读取 scenario。",
            exists=True, file_okay=True, dir_okay=False,
        ),
    ],
    # ========== 输出 ==========
    format: Annotated[
        Literal["table", "text", "json", "md"],
        typer.Option("--format", "-f", help="输出格式：table（默认，带表格）、text（纯文本）、json（结构化）、md（Markdown）。"),
    ] = "table",
    with_usage_hint: Annotated[
        bool,
        typer.Option("--no-usage-hint", help="json 输出时不附加 usage_hint 字段。"),
    ] = True,
    # ========== 通用 ==========
    no_color: Annotated[
        bool,
        typer.Option("--no-color", help="关闭 ANSI 颜色（CI 友好；自动检测非 TTY）。"),
    ] = False,
) -> None:
    """Typer 命令：只读展示 Scenario 的 step 索引表（不执行）。

    [bold]示例：[/bold]

      gimbal run show --from-path ./debug-case.yaml
      gimbal run show --from-path ./debug-case.yaml --format=json
    """
    cli_ctx: CLIContext = ctx.obj  # noqa: F841  (保持与其余子命令一致的引用风格)

    # 0. 自动检测非 TTY 时强制关闭颜色（除非显式传 --no-color=False）
    if not sys.stdout.isatty() and not no_color:
        no_color = True

    payloads = _load_from_path(from_path, with_usage_hint and format == "json")

    # 渲染
    if format == "json":
        typer.echo(json.dumps(payloads, ensure_ascii=False, indent=2))
    elif format == "md":
        for p in payloads:
            _render_markdown(p)
            if p is not payloads[-1]:
                typer.echo("\n---\n")
    elif format == "text":
        for p in payloads:
            _render_text(p)
            if p is not payloads[-1]:
                typer.echo()
    else:  # table
        for p in payloads:
            _render_table(p, no_color=no_color)
            if p is not payloads[-1]:
                typer.echo()
    raise typer.Exit(code=0)


def _load_from_path(path: Path, keep_usage_hint: bool) -> list[dict]:
    """从本地 JSON/YAML 读取单个 scenario，返回 step map 列表（通常 1 个）。"""
    from gimbal.cli.commands.run_launch import (
        _read_source, _detect_format, _parse_json, _parse_yaml, InputFormat,
    )
    raw, hint = _read_source(str(path), None)
    fmt = _detect_format(InputFormat.auto, raw, hint)
    if fmt == InputFormat.json:
        data = _parse_json(raw)
    elif fmt == InputFormat.yaml:
        data = _parse_yaml(raw)
    else:
        # text 模式：占位，未走 schema 解析
        typer.secho(
            f"Error: 暂不支持 text 格式的 scenario 文件解析: {path}",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(code=2)
    try:
        sc = Scenario.model_validate(data)
    except Exception as exc:
        typer.secho(
            f"Scenario validation failed for {path}: {exc}",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(code=2)

    payload = _scenario_to_step_map(sc.scenarioId or path.stem, sc)
    if not keep_usage_hint:
        payload.pop("usage_hint", None)
    return [payload]
