"""gimbal run launch —— 直接解析传入的路径文本信息，发送请求"""
from __future__ import annotations

import sys
from typing import Annotated
from pathlib import Path
from pprint import pprint

import typer
import yaml
import json

from gimbal.core.runner import Engine
from gimbal.core.bootstrap import bootstrap, shutdown
from gimbal.cli.common import (
    DryRunOpt, EnvOpt, LogLevel, LogLevelOpt, InputFormat, FormatOpt, ModeOpt,
    OutputFormat, OutputOpt, PluginsOpt, RegistryOpt, ReportDirOpt, ReporterOpt,
    _build_default_asset_store, _print_run_report, _publish_run_meta,
)
from gimbal.cli.context import CLIContext
from gimbal.log import get_logger
from gimbal.schema.scenario import Scenario

logger = get_logger(__name__)


class InputError(typer.BadParameter):
    """输入参数错误。"""


def _read_source(source: str | None, inline: str | None) -> tuple[str, str | None]:
    """解析 source/inline 的互斥关系，读取原始文本并返回 (raw, 路径扩展名 hint)；非法组合抛 InputError。

    Returns:
        (raw_content, source_hint)
        source_hint 用于 auto 模式下的格式推断，文件路径返回扩展名，
        stdin / inline 返回 None。
    """
    # 互斥校验
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
    """当 fmt 为 auto 时按扩展名或首字符嗅探出真实 InputFormat；显式 fmt 直接透传。"""
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
    """解析 raw 为 JSON 字典；JSON 失败时回退到 YAML 解析；顶层不是 dict 时抛 InputError。"""
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
    """解析 raw 为 YAML 映射；解析失败/为空/顶层非 dict 时抛 InputError。"""
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
    """text 格式占位实现：原样把 raw 包装为带 __raw_text__/__pending_parse__ 标记的 dict，等待后续解析器接入。"""
    # TODO: 接入文本检查/解析方法，例如 text_parser.parse(raw) -> dict
    return {"__raw_text__": raw, "__pending_parse__": True}


def normalize_input(
    source: str | None,
    inline: str | None,
    fmt: InputFormat,
) -> dict:
    """把多种输入源（文件路径/'-'/--inline × json/yaml/auto）归一化为单层 dict。"""
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
    mode: ModeOpt = "local",
    log_level: LogLevelOpt = LogLevel.info,

    fail_fast: Annotated[
        bool,
        typer.Option("--fail-fast", help="首个失败即停止", rich_help_panel="执行控制"),
    ] = False,
    # ========== 步骤级控制（与 gimbal run scenario 对齐；阶段 1 最小子集）==========
    step_from: Annotated[
        int | None,
        typer.Option("--step-from", help="从指定 step 开始执行（阶段 2 引入 StepResolver 后生效；当前仅提示警告）。", rich_help_panel="步骤控制"),
    ] = None,
    step_to: Annotated[
        int | None,
        typer.Option("--step-to", help="执行到指定 step 停止（0-based）。", rich_help_panel="步骤控制"),
    ] = None,
    breakpoint_at: Annotated[
        list[int] | None,
        typer.Option("--breakpoint", help="在指定 step 暂停（暂以首个为准；交互模式在阶段 2 完整支持）。", rich_help_panel="步骤控制"),
    ] = None,
    dry_run: DryRunOpt = False,
    plugins : PluginsOpt = [],
    registry: RegistryOpt = None,
    # ========== 报告与输出 ==========
    reporter: ReporterOpt = None,
    report_dir: ReportDirOpt = "./reports",
    output: OutputOpt = OutputFormat.console,
) -> None:
    """Typer 命令：bootstrap 框架 → 归一化输入为 dict → 校验为 Scenario → Engine.run 执行并打印报告。"""
    """指定标准输入，用例文件或 inline 内容交给框架直接执行。

    [bold]示例：[/bold]
        文件路径:
        gimbal run launch ./debug.yaml

        内联字符串:
        gimbal run launch --inline '{"name":"x"}' -f json

        标准输入(stdin):
        cat case.yaml | gimbal run launch - -f yaml

        阶段控制（最小子集）：
        cat case.yaml | gimbal run launch - --step-to=3
        gimbal run launch ./debug.yaml --breakpoint=5
    """
    # 0. 步骤级控制参数互斥校验（与 run_scenario 对齐）
    if step_from is not None and step_to is not None and step_from > step_to:
        raise InputError("--step-from 不能大于 --step-to。")
    if breakpoint_at is not None and step_to is not None:
        logger.warning(
            "[CLI] --step-to={} 与 --breakpoint={} 同时设置；优先使用 --step-to",
            step_to, breakpoint_at,
        )

    # 1. 将传入参数 注入到 ctx上下文中
    cli_ctx : CLIContext = ctx.obj
    # cli_ctx.extras["fail_fast"] = fail_fast
    # cli_ctx.extras["report_dir"] = report_dir
    # cli_ctx.extras["env"] = env
    # cli_ctx.extras["mode"] = mode
    # cli_ctx.extras["log_level"] = log_level
    cli_ctx.env = env
    cli_ctx.mode = mode
    cli_ctx.log_level = log_level.value  # LogLevel is a str enum, use .value to get the actual string
    # 把 report_dir注入 extras，由 ConfigLoader._from_cli()提取为 BootstrapConfig.report_dir
    if report_dir:
        cli_ctx.extras["report_dir"] = report_dir
    # 把 reporter 选项注入 extras，由 ConfigLoader._from_cli()提取为 BootstrapConfig.reporters
    if reporter:
        cli_ctx.extras["reporters"] = list(reporter)


    # 2. 传入ctx, 进行配置信息加载，返回所有信息合并后的上下文信息
    configuration  = bootstrap(cli_ctx)
    # 2.5 发布 RunMetaEvent（CI/CD / git / 触发人等上下文）
    _publish_run_meta(configuration)
    # 3. 持有信息后，进行内存总线初始化，插件初始化，资产仓库初始化，

    # 4. 归一化输入 → dict
    payload: dict = normalize_input(source, inline, fmt)

    # 5. suite/scenario 从资产仓库查询对应的suite和scenario信息,进行实例化
    # 6. dry-run 打印解析结果
    if dry_run:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        raise typer.Exit(code=0)

    #7. schema + 资产有效性检查，对数据类进行格式检查，对资产进行有效性检查
    try:
        scenario = Scenario.model_validate(payload)
    except Exception as exc:
        typer.secho(f"用例格式校验失败: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    # 7.5 构造 RuntimeControl（与 run_scenario 同一套优先级）
    from gimbal.core.scenario_runner import RuntimeControl

    runtime_control: RuntimeControl | None = None
    if step_to is not None:
        runtime_control = RuntimeControl(
            halt_at=step_to,
            halt_reason=f"cli --step-to={step_to}",
        )
    elif breakpoint_at is not None and breakpoint_at:
        runtime_control = RuntimeControl(
            halt_at=breakpoint_at[0],
            halt_reason=f"cli --breakpoint={breakpoint_at[0]}",
        )
    if step_from is not None:
        # 当前 ScenarioRunner 未实现 step_from；显示警告，不静默吞掉
        typer.secho(
            f"[warn] --step-from={step_from} 当前版本暂未生效（将在阶段 2 引入 StepResolver 后支持）。\n"
            f"       当前阶段 1 仅支持 --step-to 与 --breakpoint。",
            fg=typer.colors.YELLOW, err=True,
        )

    #8. 数据类有效，引用链接有效，执行器启动
    #    注入资产仓库，让 ScenarioPreprocessor Phase 0 启用对 RefBase 节点的物化
    asset_store = _build_default_asset_store(Path(registry) if registry else None)
    logger.debug("[CLI] asset_store ready: backend={}", asset_store.backend_name)
    engine = Engine(configuration, asset_store=asset_store)
    try:
        result = engine.run(scenario, runtime_control=runtime_control)
    finally:
        # 必须 shutdown 才会触发 ReporterRuntime.shutdown()、生成 artifacts
        shutdown(configuration)
    _print_run_report(result, output, artifacts=engine.artifacts)
    raise typer.Exit(code=result.exit_code)