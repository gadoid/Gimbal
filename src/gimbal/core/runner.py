"""执行器与本地匹配器。

CLI 层只负责构造 RunRequest，具体执行委托给 Runner。
Runner 内部对接你的 Scenario/Strategy/状态机执行引擎。
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from pathlib import Path
from typing import Any, Annotated
from schema.scenario import RunUnion
import typer

from gimbal.cli.context import CLIContext
from gimbal.core.asset_resolver import AssetKind, ResolvedAsset

class Reference(BaseModel) :
    refLink : str = "占位"

class RuntimeOptions(BaseModel) :
    env: str = "dev"
    profile : str = "default"
    log_level: str = "info"
    reporters: list[str] = Field(default_factory=list)
    reportDir: str = "./reports"
    output: str = "console" 

class RunRequest(BaseModel):
    """一次执行请求，CLI 层构造，执行层消费。

    这是 CLI 和核心引擎之间的契约。后续即使把入口换成
    HTTP API / gRPC，只要能拼出 RunRequest，引擎层无需改动。
    """
    run: RunUnion = Field(..., description="最终待执行的内容")
    reference: Reference = Field(default_factory=Reference, description="引用的服务地址")
    runtime : RuntimeOptions = Field(default_factory=RuntimeOptions, description="运行时配置")

    # 多目标控制
    # order: str = "as-given"
    # continue_on_error: bool = False

class RunResult(BaseModel):
    """执行结果。"""
    exit_code: int = 0
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0


class Runner:
    """执行器入口。占位实现，演示接口。"""

    def __init__(self,runrequest: RunRequest, ctx: CLIContext) -> None:
        self.runrequest = runrequest
        self.ctx = ctx

    def run(self) -> RunResult:
        typer.echo(f"[Runner] kind={request.kind.value}, targets={len(request.targets)}")
        typer.echo(f"[Runner] env={request.env}, profile={request.profile}")
        typer.echo(f"[Runner] parallel={request.parallel}, timeout={request.timeout}s")
        if request.dry_run:
            typer.echo(typer.style("[Runner] DRY-RUN mode, no actual execution.", fg=typer.colors.YELLOW))
        for t in request.targets:
            typer.echo(f"  → {t.id} ({t.source_path})")
        # TODO: 接入你的 Scenario/Strategy 执行引擎
        return RunResult(exit_code=0, total=len(request.targets), passed=len(request.targets))

