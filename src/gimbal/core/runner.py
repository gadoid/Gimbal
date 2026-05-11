"""执行器与本地匹配器。

CLI 层只负责构造 RunRequest，具体执行委托给 Runner。
Runner 内部对接你的 Scenario/Strategy/状态机执行引擎。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import typer

from gimbal.cli.context import CLIContext
from gimbal.core.asset_resolver import AssetKind, ResolvedAsset


@dataclass
class RunRequest:
    """一次执行请求，CLI 层构造，执行层消费。

    这是 CLI 和核心引擎之间的契约。后续即使把入口换成
    HTTP API / gRPC，只要能拼出 RunRequest，引擎层无需改动。
    """
    kind: AssetKind
    targets: list[ResolvedAsset]

    # 环境与配置
    env: str = "dev"
    profile: str = "default"
    log_level: str = "info"

    # 过滤与变量
    tags: list[str] = field(default_factory=list)
    variables: dict[str, str] = field(default_factory=dict)
    var_files: list[str] = field(default_factory=list)

    # 执行控制
    parallel: int = 1
    timeout: int = 300
    retry: int = 0
    dry_run: bool = False
    fail_fast: bool = False

    # 报告
    reporters: list[str] = field(default_factory=list)
    report_dir: str = "./reports"
    output: str = "console"

    # 多目标控制
    order: str = "as-given"
    continue_on_error: bool = False

    # suite-specific
    include_scenarios: list[str] = field(default_factory=list)
    exclude_scenarios: list[str] = field(default_factory=list)

    # scenario-specific
    step_from: int | None = None
    step_to: int | None = None
    breakpoints: list[int] = field(default_factory=list)

    # match-specific
    shuffle: bool = False
    seed: int | None = None


@dataclass
class RunResult:
    """执行结果。"""
    exit_code: int = 0
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0


class Runner:
    """执行器入口。占位实现，演示接口。"""

    def __init__(self, ctx: CLIContext) -> None:
        self.ctx = ctx

    def run(self, request: RunRequest) -> RunResult:
        typer.echo(f"[Runner] kind={request.kind.value}, targets={len(request.targets)}")
        typer.echo(f"[Runner] env={request.env}, profile={request.profile}")
        typer.echo(f"[Runner] parallel={request.parallel}, timeout={request.timeout}s")
        if request.dry_run:
            typer.echo(typer.style("[Runner] DRY-RUN mode, no actual execution.", fg=typer.colors.YELLOW))
        for t in request.targets:
            typer.echo(f"  → {t.id} ({t.source_path})")
        # TODO: 接入你的 Scenario/Strategy 执行引擎
        return RunResult(exit_code=0, total=len(request.targets), passed=len(request.targets))


class LocalMatcher:
    """本地文件匹配器。占位实现。"""

    def __init__(
        self,
        patterns: list[str],
        search_paths: list[str] | None = None,
        recursive: bool = True,
        include: list[str] | None = None,
        exclude: list[str] | None = None,
        changed_only: bool = False,
        changed_since: str = "HEAD~1",
        last_failed: bool = False,
        last_failed_first: bool = False,
        tags: list[str] | None = None,
    ) -> None:
        self.patterns = patterns
        self.search_paths = search_paths or ["."]
        self.recursive = recursive
        self.include = include or []
        self.exclude = exclude or []
        self.changed_only = changed_only
        self.changed_since = changed_since
        self.last_failed = last_failed
        self.last_failed_first = last_failed_first
        self.tags = tags or []

    def collect(self) -> list[ResolvedAsset]:
        """按 pattern 收集本地用例文件。占位实现。"""
        # TODO: 实际实现
        #   - 解析 pattern 前缀（id:/name:/tag: vs 路径 glob）
        #   - 用 pathlib.Path.glob 扫描
        #   - --changed-only 调 git diff
        #   - --last-failed 读取上次失败记录
        results: list[ResolvedAsset] = []
        for pat in self.patterns:
            if pat.startswith("id:") or pat.startswith("name:") or pat.startswith("tag:"):
                # 表达式形式：交给查询器
                results.append(ResolvedAsset(
                    id=pat,
                    kind=AssetKind.LOCAL,
                    source_path=f"<expr>{pat}",
                ))
            else:
                # 路径 glob
                results.append(ResolvedAsset(
                    id=Path(pat).stem or pat,
                    kind=AssetKind.LOCAL,
                    source_path=pat,
                ))
        return results