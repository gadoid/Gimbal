"""reporter/__init__.py - Reporter 模块公共 API。

典型用法:

    from gimbal.reporter import ReporterRegistry, ReporterRuntime, ReportArtifact
    from gimbal.reporter.builtin import register_builtin_reporters

    registry = ReporterRegistry()
    register_builtin_reporters(registry)
    runtime = ReporterRuntime(registry)
    runtime.setup(bus, config)
    runtime.begin_all(framework_ctx, ["console", "junit"], report_dir, plugin_configs)
    # ... 跑测试 ...
    artifacts = runtime.finalize_all(run_result)
    runtime.shutdown()
"""
from __future__ import annotations

from gimbal.reporter.base import ReportArtifact, ReporterBase
from gimbal.reporter.protocol import ReportContext, Reporter
from gimbal.reporter.registry import (
    ReporterAlreadyRegistered,
    ReporterNotFound,
    ReporterRegistry,
)
from gimbal.reporter.runtime import ReportErrorLog, ReporterRuntime


__all__ = [
    # 协议 / 数据
    "Reporter",
    "ReportContext",
    "ReportArtifact",
    # 基类
    "ReporterBase",
    # 注册 / 调度
    "ReporterRegistry",
    "ReporterRuntime",
    "ReportErrorLog",
    "ReporterAlreadyRegistered",
    "ReporterNotFound",
]
