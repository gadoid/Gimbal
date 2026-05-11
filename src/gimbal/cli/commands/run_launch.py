"""gimbal run launch —— 直接解析传入的路径文本信息，发送请求"""
from __future__ import annotations

import sys
from typing import Annotated
from pathlib import Path

import typer
import yaml
import json


from gimbal.cli.common import (
    AllowEmptyOpt, DryRunOpt, EnvOpt, LogLevel, LogLevelOpt,
    InputFormat, FormatOpt, TagOpt, TimeoutOpt, VarFileOpt, VarOpt, YesOpt,
    parse_parallel, parse_vars,
)
from gimbal.cli.context import CLIContext
from gimbal.core.asset_resolver import AssetKind
from gimbal.core.runner import LocalMatcher, Runner, RunRequest

class InputError(typer.BadParameter):
    """输入参数错误。"""


def _read_source(source: str | None, inline: str | None) -> tuple[str, str | None]:
    """读取原始输入内容。

    Returns:
        (raw_content, source_hint)
        source_hint 用于 auto 模式下的格式推断，文件路径返回扩展名，
        stdin / inline 返回 None。
    """
    # 互斥校验
    provided = [x for x in (source, inline) if x is not None]
    if len(provided) == 0:
        raise InputError("必须提供 SOURCE (文件路径或 '-') 或 --inline 之一")
    if source is not None and inline is not None:
        raise InputError("SOURCE 和 --inline 不能同时提供")

    # inline 字符串
    if inline is not None:
        return inline, None

    # stdin
    if source == "-":
        if sys.stdin.isatty():
            raise InputError("指定了 '-' 但 stdin 是终端，没有可读取的内容")
        return sys.stdin.read(), None

    # 文件路径
    path = Path(source)
    if not path.exists():
        raise InputError(f"文件不存在: {source}")
    if not path.is_file():
        raise InputError(f"不是有效文件: {source}")
    return path.read_text(encoding="utf-8"), path.suffix.lower()


def _detect_format(
    fmt: InputFormat,
    raw: str,
    source_hint: str | None,
) -> InputFormat:
    """auto 模式下推断真实格式。"""
    if fmt != InputFormat.auto:
        return fmt

    # 文件路径：按扩展名
    if source_hint:
        if source_hint in (".yaml", ".yml"):
            return InputFormat.yaml
        if source_hint == ".json":
            return InputFormat.json
        if source_hint in (".txt", ".text"):
            return InputFormat.auto
        # 其他扩展名走内容嗅探

    # stdin / inline / 未知扩展名：内容嗅探
    stripped = raw.lstrip()
    if not stripped:
        raise InputError("输入内容为空")

    # JSON 通常以 { 或 [ 开头
    if stripped[0] in "{[":
        return InputFormat.json
    # 否则当作 yaml 处理 (yaml 是 json 超集，纯字典/列表也能解析)
    return InputFormat.yaml


def _parse_json(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        try :
            print(f"JSON 解析失败, 尝试使用YAML解析") 
            data = _parse_yaml(raw)
        except Exception as e :
            raise InputError(f"JSON/YAML解析均失败，请检查文本格式\nError : {e}") 
    if not isinstance(data, dict):
        raise InputError(f"JSON 顶层必须是对象 (dict)，实际是 {type(data).__name__}")
    return data


def _parse_yaml(raw: str) -> dict:
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        raise InputError(f"YAML 解析失败: {e}") from e
    if data is None:
        raise InputError("YAML 内容为空")
    if not isinstance(data, dict):
        raise InputError(f"YAML 顶层必须是映射 (dict)，实际是 {type(data).__name__}")
    return data


def _parse_text(raw: str) -> dict:
    """text 格式预留：不做任何转换，交给后续专门方法处理。

    当前留空：仅原样包装，后续接入文本检查/解析方法时在此处替换。
    """
    # TODO: 接入文本检查/解析方法，例如 text_parser.parse(raw) -> dict
    return {"__raw_text__": raw, "__pending_parse__": True}


def normalize_input(
    source: str | None,
    inline: str | None,
    fmt: InputFormat,
) -> dict:
    """把多种输入源归一化为 dict。"""
    raw, hint = _read_source(source, inline)
    real_fmt = _detect_format(fmt, raw, hint)
    if real_fmt == InputFormat.json:
        return _parse_json(raw)
    if real_fmt == InputFormat.yaml:
        return _parse_yaml(raw)
    if real_fmt == InputFormat.auto:
        return _parse_text(raw)

    raise InputError(f"未知输入格式: {real_fmt}")


# ============ launch 主入口 ============

def launch(
    ctx: typer.Context,
    # ========== 输入控制 ==========
    source: Annotated[
        str | None,
        typer.Argument(help="文件路径或 '-' 表示 stdin", metavar="SOURCE"),
    ] = None,
    inline: Annotated[
        str | None,
        typer.Option("--inline", help="直接传内容", rich_help_panel="输入控制"),
    ] = None,
    fmt: FormatOpt = InputFormat.auto,
    # ========== 通用 ==========
    env: EnvOpt = "dev",
    log_level: LogLevelOpt = LogLevel.info,
    tag: TagOpt = None,
    dry_run: DryRunOpt = False,
) -> None:
    """指定标准输入，用例文件或 inline 内容交给框架直接执行。

    [bold]示例：[/bold]
        文件路径:
        gimbal run launch ./debug.yaml

        内联字符串:
        gimbal run launch --inline '{"name":"x"}' -f json

        标准输入(stdin):
        cat case.yaml | gimbal run launch - -f yaml
    """
    clictx: CLIContext = ctx.obj
    clictx.action_path = "run.launch"
    # 1. 归一化输入 → dict
    payload: dict = normalize_input(source, inline, fmt)

    # 2. dry-run 仅打印解析结果，不真正执行
    if dry_run:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        raise typer.Exit(code=0)

    # 3. 交给 Runner 执行 (这里按你现有 Runner 接口填实参)
    request = RunRequest(
        kind="scenario",
        targets=["hello"],
        env=env,
        tags=tag or [],
        log_level=log_level,
    )

    request = RunRequest(
        kind=AssetKind.SCENARIO,
        targets=matched,
        env=env,
        profile=profile,
        log_level=log_level.value,
        tags=tag or [],
        variables=parse_vars(var),
        var_files=var_file or [],
        parallel=parse_parallel(parallel),
        timeout=timeout,
        retry=retry,
        dry_run=dry_run,
        fail_fast=fail_fast,
        reporters=reporter or ["console"],
        report_dir=report_dir,
        output=output.value,
        order=order.value,
        continue_on_error=continue_on_error,
        step_from=step_from,
        step_to=step_to,
        breakpoints=breakpoint_at or [],
    )
    # runner = Runner(matcher=LocalMatcher(), context=clictx)
    # runner.run(request)

