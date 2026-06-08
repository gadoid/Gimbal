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
from pathlib import Path
from typing import Annotated, TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from gimbal.repository import AssetStore


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
    info = "info"
    warning = "warning"
    debug = "debug"
    error = "error"


class OutputFormat(str, Enum):
    console = "console"
    json = "json"


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


ModeOpt = Annotated[
    str,
    typer.Option("--mode", help="使用的启动模式(mode)。", rich_help_panel="环境与日志"),
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
PluginsOpt = Annotated[
    list[str],
    typer.Option(
       "-P","--plugins",
       help="加载插件",
       rich_help_panel="插件执行"
    )
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


def _build_default_asset_store(registry: Path | None = None) -> "AssetStore":
    """构造默认的本地 AssetStore（registry 路径由 --registry 覆盖）。

    供 suite / scenario CLI 子命令共用，避免在两处重复构造。
    """
    from gimbal.repository import AssetStore, LocalFsContentStore

    root = (registry or Path("~/.gimbal/registry")).expanduser()
    return AssetStore(backend=LocalFsContentStore(root=root))


def _collect_run_meta() -> dict[str, Any]:
    """收集本次运行的元数据（CI/CD 上下文 / git 信息 / 触发人 / 业务扩展）。

    数据来源：
      - 环境变量：CI 平台约定的标准变量（GitHub Actions / GitLab CI / Jenkins / 通用）
      - 用户可在 ~/.gimbal/env 或 gimbal.toml 的 [run_meta] 段补充自定义键值

    兼容设计：
      - 所有字段都有 default；任何环境变量缺失都不会抛错
      - 字段名为人类可读，与 HTML 报告头部 pill 一一对应
    """
    import os

    return {
        # CI/CD 上下文
        "ci":              bool(os.environ.get("CI")),
        "ci_provider":     os.environ.get("CI_PROVIDER", ""),     # 手动指定
        "build_url":       os.environ.get("BUILD_URL", "") or os.environ.get("CI_BUILD_URL", "") or os.environ.get("GITHUB_SERVER_URL", ""),
        "build_number":    os.environ.get("BUILD_NUMBER", "") or os.environ.get("GITHUB_RUN_NUMBER", "") or os.environ.get("CI_PIPELINE_ID", ""),
        "build_id":        os.environ.get("BUILD_ID", "") or os.environ.get("GITHUB_RUN_ID", ""),
        # Git 上下文（短名：与 HTML 报告头部 pill / JsonReporter dump 对齐）
        "branch":          os.environ.get("GIT_BRANCH", "") or os.environ.get("GITHUB_REF_NAME", "") or os.environ.get("CI_COMMIT_REF_NAME", ""),
        "commit":          (os.environ.get("GIT_COMMIT", "") or os.environ.get("GITHUB_SHA", "") or os.environ.get("CI_COMMIT_SHA", ""))[:12],
        "commit_msg":      (os.environ.get("GIT_COMMIT_MESSAGE", "") or os.environ.get("CI_COMMIT_MESSAGE", ""))[:120],
        # 触发人
        "triggered_by":    os.environ.get("GIT_AUTHOR", "") or os.environ.get("GITHUB_ACTOR", "") or os.environ.get("CI_COMMIT_AUTHOR", "") or os.environ.get("USER", "") or os.environ.get("USERNAME", ""),
    }


def _publish_run_meta(configuration: Any) -> None:
    """收集并发布 RunMetaEvent 到 EventBus。

    时机：bootstrap() 之后、Engine.run() 之前。
    此时 bus 已经初始化，reporter 也已订阅过 interested_events。

    容错：bus 不存在或 publish 失败时静默跳过（reporter 拿不到 meta 时
    应能优雅地降级到空 meta，而不是让 CLI 崩溃）。
    """
    import os  # 显式 import，便于工具识别

    bus = getattr(configuration, "event_bus", None)
    if bus is None:
        return
    try:
        from gimbal.events.types import RunMetaEvent
        meta = _collect_run_meta()
        bus.publish(RunMetaEvent(meta=meta))
    except Exception:  # noqa: BLE001
        # 元数据发布失败不影响主流程
        pass


def _print_run_report(result: Any, fmt: "OutputFormat", artifacts: list | None = None) -> None:
    """统一格式化输出 RunResult。

    console —— 给人看的高亮摘要
    json    —— 机器读的 JSON dump
    """
    import json as _json
    import typer as _typer

    payload = {
        "exit_code": result.exit_code,
        "total":     result.total,
        "passed":    result.passed,
        "failed":    result.failed,
        "skipped":   result.skipped,
        "error":     result.error,
        "details":   result.details,
    }

    if fmt == OutputFormat.json:
        _typer.echo(_json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return

    # console：分组显示通过/失败/错误
    if result.passed == result.total and result.total > 0:
        _typer.secho(
            f"PASS  total={result.total} passed={result.passed} duration={_total_duration_ms(result):.1f}ms",
            fg=_typer.colors.GREEN, bold=True,
        )
    elif result.total == 0:
        _typer.secho("WARN  no targets executed", fg=_typer.colors.YELLOW, bold=True)
    else:
        _typer.secho(
            f"FAIL  total={result.total} passed={result.passed} "
            f"failed={result.failed} error={result.error} "
            f"duration={_total_duration_ms(result):.1f}ms",
            fg=_typer.colors.RED, bold=True,
        )
    for d in result.details:
        status = d.get("status", "?")
        color = {
            "passed": _typer.colors.GREEN,
            "failed": _typer.colors.RED,
            "error":  _typer.colors.RED,
            "skipped": _typer.colors.YELLOW,
        }.get(status, _typer.colors.WHITE)
        _typer.secho(
            f"  - {d.get('scenario_id', '?')}: {status} ({d.get('duration_ms', 0):.1f}ms)",
            fg=color,
        )


    # ── artifacts section ────────────────────────────────────────────────────
    if artifacts:
        _typer.secho(
            f"  Reports ({len(artifacts)}):",
            fg=_typer.colors.CYAN, bold=True,
            )
        for art in artifacts:
            name = getattr(art, "name", "?")
            path = getattr(art, "path", None)
            media = getattr(art, "media_type", None)
            loc = str(path) if path is not None else "<inline>"
            meta = ""
            md = getattr(art, "metadata", None)
            if isinstance(md, dict) and md:
                meta = " " + ", ".join(f"{k}={v}" for k, v in md.items())
            media_tag = f" [{media}]" if media else ""
            _typer.echo(f"   - {name}{media_tag}: {loc}{meta}")


def _total_duration_ms(result: Any) -> float:

    return sum(float(d.get("duration_ms", 0)) for d in result.details)