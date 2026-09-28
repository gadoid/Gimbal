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
    OutputFormat, OutputOpt, PluginsOpt, ReportDirOpt, ReporterOpt,
    _print_run_report, _publish_run_meta,
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
    # ========== 步骤级控制（阶段 1 最小子集）==========
    step_from: Annotated[
        int | None,
        typer.Option("--step-from", help="从指定 step 开始执行（0-based，区间外跳过；v2.1 批次 E 生效）。", rich_help_panel="步骤控制"),
    ] = None,
    step_to: Annotated[
        int | None,
        typer.Option("--step-to", help="执行到指定 step 停止（0-based）。", rich_help_panel="步骤控制"),
    ] = None,
    halt_at: Annotated[
        int | None,
        typer.Option("--halt-at", help="执行到指定 step 停止（0-based；残留 #3：承接旧 --breakpoint 数字语义）。", rich_help_panel="步骤控制"),
    ] = None,
    breakpoint_at: Annotated[
        list[str] | None,
        typer.Option("--breakpoint", help="debugger 断点地址 'step-001:call_before'（只收地址；数字停点用 --halt-at，残留 #3 拆分）。", rich_help_panel="步骤控制"),
    ] = None,
    debug: Annotated[
        bool,
        typer.Option("--debug", help="装载 debugger（仅单单元且 n_runs=1；批次 E）", rich_help_panel="调试"),
    ] = False,
    pause: Annotated[
        str,
        typer.Option("--pause", help="暂停策略: none | on_failure | every_step", rich_help_panel="调试"),
    ] = "on_failure",
    dry_run: DryRunOpt = False,
    plugins : PluginsOpt = [],
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
        gimbal run launch ./debug.yaml --halt-at=5
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
    cli_ctx.extras["fail_fast"] = fail_fast   # v2.1 批次 F：接线（loader bool_fields 已支持）
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
    #    按 kind 分派：suite 走 Engine._run_suite（支持 execution.parallel 并行分派），
    #    scenario 走单场景路径；runtime_control 仅对 scenario 有意义。
    from pydantic import TypeAdapter
    from gimbal.schema.scenario import RunUnion
    try:
        target = TypeAdapter(RunUnion).validate_python(payload)
    except Exception as exc:
        typer.secho(f"用例格式校验失败: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    scenario = target

    # 7.4 断点入参分流（残留 #3）：--breakpoint 只收地址；数字停点必须用 --halt-at
    debug_breakpoints: list[str] = []
    for bp in (breakpoint_at or []):
        as_str = str(bp)
        if ":" not in as_str:
            typer.secho(
                f"--breakpoint 只接受地址形式（如 step-000:call_before）；"
                f"数字停点请用 --halt-at（得到 {bp!r}）",
                fg=typer.colors.RED, err=True,
            )
            raise typer.Exit(code=2)
        debug_breakpoints.append(as_str)
    breakpoint_at = None

    # 7.5 构造 RuntimeControl（与 run_scenario 同一套优先级）
    from gimbal.core.scenario_runner import RuntimeControl

    runtime_control: RuntimeControl | None = None
    if step_to is not None or step_from is not None or halt_at is not None:
        runtime_control = RuntimeControl(
            halt_at=step_to if step_to is not None else halt_at,
            halt_reason=(
                f"cli --step-to={step_to}" if step_to is not None
                else (f"cli --halt-at={halt_at}" if halt_at is not None else "user-requested")
            ),
            step_from=step_from,
        )
    # v2.1 批次 E：step_from 生效（区间外 step 跳过，所需输入由 vars/inputs 提供）

    # 7.6 debugger 装载（v2.1 批次 E）：仅单单元且 n_runs=1；调试挂起不计超时
    debugger = None
    if debug:
        from gimbal.core.debugger import debug_unit_count
        if output == OutputFormat.jsonl:
            typer.secho(
                "--debug 与 -o jsonl 同用:调试提示走 stderr,stdout 保持纯事件流",
                fg=typer.colors.YELLOW, err=True,
            )
        unit_count = debug_unit_count(scenario)
        if unit_count != 1:
            typer.secho(
                f"--debug 仅支持单单元目标（当前 {unit_count} 个）；suite 级调试明确不做",
                fg=typer.colors.RED, err=True,
            )
            shutdown(configuration)
            raise typer.Exit(code=2)
        from gimbal.core.debugger import DebuggerPlugin
        debugger = DebuggerPlugin(
            pause=pause,
            breakpoints=debug_breakpoints,
            event_bus=configuration.event_bus,
        )
        debugger.activate(configuration.hook_registry)
        # 引擎让步：调试档位下挂起不计超时（并入 runtime_control）
        from gimbal.core.scenario_runner import RuntimeControl as _RC
        if runtime_control is None:
            runtime_control = _RC(debug_mode=True)
        else:
            runtime_control.debug_mode = True

    # 7.7 jsonl 事件流（v2.1 批次 F-2c + S-5）：订阅全部事件逐行打 stdout，
    #     终线 run.finished 由 runner 发布（RunFinishedEvent）、sink 打印
    jsonl_sub = None
    if output == OutputFormat.jsonl:
        from gimbal.cli.common import attach_jsonl_sink
        jsonl_sub = attach_jsonl_sink(configuration.event_bus)

    #8. 数据类有效，执行器启动
    engine = Engine(configuration)
    try:
        result = engine.run(scenario, runtime_control=runtime_control)
    finally:
        if debugger is not None:
            debugger.deactivate(configuration.hook_registry)
        if jsonl_sub is not None:
            try:
                configuration.event_bus.unsubscribe(jsonl_sub)
            except Exception:  # noqa: BLE001
                pass
        # 必须 shutdown 才会触发 ReporterRuntime.shutdown()、生成 artifacts
        shutdown(configuration)
    _print_run_report(result, output, artifacts=engine.artifacts)
    raise typer.Exit(code=result.exit_code)