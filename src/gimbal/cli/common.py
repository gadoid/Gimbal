"""共享参数定义。

Typer 推荐用 `Annotated[T, typer.Option(...)]` 定义参数。
把高频参数提取成类型别名，子命令函数签名里直接复用，类型注解即文档。

对比 Click 装饰器叠加方式：
  - Click: @click.option 装饰器一层层叠
  - Typer: 函数签名 + Annotated 类型别名，IDE 类型推导友好

约定：
  - *Opt 后缀表示 typer.Option 定义的参数
  - *Arg 后缀表示 typer.Argument 定义的位置参数
"""
from __future__ import annotations

from enum import Enum
from typing import Annotated

import typer


# ============================================================
# 枚举类型 —— Typer 会自动从 Enum 生成 --help 中的选项列表
# ============================================================

class SourceStrategy(str, Enum):
    """资产来源策略。"""
    auto = "auto"
    local = "local"
    remote = "remote"


class OrderStrategy(str, Enum):
    """多目标执行顺序。"""
    sequential = "sequential"
    parallel = "parallel"
    as_given = "as-given"

class InputFormat(str, Enum) :
    auto = "auto"
    json = "json"
    yaml = "yaml"

class LogLevel(str, Enum):
    debug = "debug"
    info = "info"
    warning = "warning"
    error = "error"


class OutputFormat(str, Enum):
    console = "console"
    json = "json"
    junit = "junit"


class ServerMode(str, Enum):
    http = "http"
    grpc = "grpc"
    websocket = "websocket"


class AuthMode(str, Enum):
    none = "none"
    token = "token"
    mtls = "mtls"


# ============================================================
# 通用 run 参数类型别名 —— 所有 run 子命令都用
# ============================================================

EnvOpt = Annotated[
    str,
    typer.Option("--env", help="目标环境。", rich_help_panel="环境与日志"),
]

FormatOpt = Annotated[
    InputFormat,
    typer.Option(
        "-f", "--format", 
        help="输入格式。auto 时按扩展名/内容推断;stdin 和 --inline 必须显式指定。",
        rich_help_panel = "输入控制"
    ),
]


ProfileOpt = Annotated[
    str,
    typer.Option("--profile", help="使用的配置 profile。", rich_help_panel="环境与日志"),
]

LogLevelOpt = Annotated[
    LogLevel,
    typer.Option("--log-level", help="日志级别。", rich_help_panel="环境与日志"),
]

TagOpt = Annotated[
    list[str] | None,
    typer.Option(
        "--tag", "-t",
        help='标签过滤，可重复。例如 -t smoke -t "not slow"。',
        rich_help_panel="过滤与变量",
    ),
]

VarOpt = Annotated[
    list[str] | None,
    typer.Option(
        "--var",
        help="注入变量，KV 形式。例如 --var user=admin。",
        rich_help_panel="过滤与变量",
    ),
]

VarFileOpt = Annotated[
    list[str] | None,
    typer.Option(
        "--var-file",
        help="变量文件，可重复。",
        rich_help_panel="过滤与变量",
        exists=True, dir_okay=False,
    ),
]

ParallelOpt = Annotated[
    str,
    typer.Option(
        "--parallel", "-p",
        help="并发数，整数或 'auto'(按 CPU 核数)。",
        rich_help_panel="执行控制",
    ),
]

TimeoutOpt = Annotated[
    int,
    typer.Option(
        "--timeout",
        min=1, max=86400,
        help="单用例超时（秒）。",
        rich_help_panel="执行控制",
    ),
]

RetryOpt = Annotated[
    int,
    typer.Option(
        "--retry",
        min=0, max=10,
        help="失败重试次数。",
        rich_help_panel="执行控制",
    ),
]

DryRunOpt = Annotated[
    bool,
    typer.Option(
        "--dry-run",
        help="只装配不真正执行。",
        rich_help_panel="执行控制",
    ),
]

FailFastOpt = Annotated[
    bool,
    typer.Option(
        "--fail-fast",
        help="首个失败即停止。",
        rich_help_panel="执行控制",
    ),
]

ReporterOpt = Annotated[
    list[str] | None,
    typer.Option(
        "--reporter",
        help="报告插件，可重复。",
        rich_help_panel="报告与输出",
    ),
]

ReportDirOpt = Annotated[
    str,
    typer.Option(
        "--report-dir",
        help="报告输出目录。",
        rich_help_panel="报告与输出",
        file_okay=False,
    ),
]

OutputOpt = Annotated[
    OutputFormat,
    typer.Option(
        "--output", "-o",
        help="结果输出格式。",
        rich_help_panel="报告与输出",
    ),
]


# ============================================================
# 资产来源参数 —— 仅 suite/scenario 使用
# ============================================================

SourceOpt = Annotated[
    SourceStrategy,
    typer.Option(
        "--source",
        help="资产来源策略：auto=本地优先 / local=仅本地 / remote=强制远端。",
        rich_help_panel="资产来源",
    ),
]

RegistryOpt = Annotated[
    str | None,
    typer.Option(
        "--registry",
        help="远端资产库地址，覆盖默认配置。",
        rich_help_panel="资产来源",
    ),
]

VersionOpt = Annotated[
    str | None,
    typer.Option(
        "--version",
        help="指定资产版本，不指定则用 latest 或 pinned。",
        rich_help_panel="资产来源",
    ),
]

NoCacheOpt = Annotated[
    bool,
    typer.Option(
        "--no-cache",
        help="强制重新拉取。等价于 --source=remote。",
        rich_help_panel="资产来源",
    ),
]

CacheOnlyOpt = Annotated[
    bool,
    typer.Option(
        "--cache-only",
        help="仅本地缓存。等价于 --source=local。",
        rich_help_panel="资产来源",
    ),
]


# ============================================================
# 多目标执行参数 —— suite/scenario 用
# ============================================================

OrderOpt = Annotated[
    OrderStrategy,
    typer.Option(
        "--order",
        help="多个目标的执行顺序。",
        rich_help_panel="多目标控制",
    ),
]

ContinueOnErrorOpt = Annotated[
    bool,
    typer.Option(
        "--continue-on-error",
        help="某目标失败后继续执行后续目标。",
        rich_help_panel="多目标控制",
    ),
]


# ============================================================
# 通配匹配确认参数 —— 涉及通配/批量的子命令用
# ============================================================

YesOpt = Annotated[
    bool,
    typer.Option(
        "--yes", "-y",
        help="跳过通配匹配多个时的确认提示。",
        rich_help_panel="确认行为",
    ),
]

AllowEmptyOpt = Annotated[
    bool,
    typer.Option(
        "--allow-empty",
        help="允许零匹配，不报错退出。",
        rich_help_panel="确认行为",
    ),
]


# ============================================================
# 辅助函数
# ============================================================

def resolve_source(
    source: SourceStrategy,
    no_cache: bool,
    cache_only: bool,
) -> SourceStrategy:
    """协调 --source / --no-cache / --cache-only。"""
    if no_cache and cache_only:
        raise typer.BadParameter("--no-cache 和 --cache-only 互斥。")
    if no_cache:
        return SourceStrategy.remote
    if cache_only:
        return SourceStrategy.local
    return source


def parse_vars(var_list: list[str] | None) -> dict[str, str]:
    """解析 --var key=value 列表。"""
    if not var_list:
        return {}
    out: dict[str, str] = {}
    for item in var_list:
        if "=" not in item:
            raise typer.BadParameter(f"Invalid --var format: {item!r}, expected KEY=VALUE.")
        k, v = item.split("=", 1)
        out[k.strip()] = v
    return out


def parse_parallel(value: str) -> int:
    """解析 --parallel，支持 'auto'。"""
    if value.lower() == "auto":
        import os
        return os.cpu_count() or 1
    try:
        n = int(value)
        if n < 1:
            raise ValueError
        return n
    except ValueError:
        raise typer.BadParameter(f"Invalid --parallel: {value!r}, expected integer or 'auto'.")