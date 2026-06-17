"""reporter/builtin/__init__.py - 内置 Reporter 工厂自注册。

这些 import 触发各模块的 factory 定义，import 本身不做注册；
注册由用户首次调用 ``register_builtin_reporters(registry)`` 完成，
或由 ReporterRuntime 的 lazy import 完成。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from gimbal.reporter.base import ReportArtifact, ReporterBase
from gimbal.reporter.protocol import ReportContext, Reporter

if TYPE_CHECKING:
    from gimbal.reporter.registry import ReporterRegistry


__all__ = [
    "ReportArtifact",
    "ReporterBase",
    "Reporter",
    "ReportContext",
    "register_builtin_reporters",
    "builtin_reporter_names",
]


BUILTIN_NAMES = (
    "console",
    "json",
    "junit",
    "allure",
    "html",
    "im_notifier",
    "platform_uploader",
)


def register_builtin_reporters(registry: "ReporterRegistry") -> None:
    """把所有内置 reporter 注册到 registry。"""
    from gimbal.reporter.builtin.console import factory as _console
    from gimbal.reporter.builtin.json_reporter import factory as _json
    from gimbal.reporter.builtin.junit import factory as _junit
    from gimbal.reporter.builtin.allure_reporter import factory as _allure
    from gimbal.reporter.builtin.html_reporter import factory as _html
    from gimbal.reporter.builtin.im_notifier import factory as _im
    from gimbal.reporter.builtin.platform_uploader import factory as _pu

    for name, factory in (
        ("console", _console),
        ("json", _json),
        ("junit", _junit),
        ("allure", _allure),
        ("html", _html),
        ("im_notifier", _im),
        ("platform_uploader", _pu),
    ):
        registry.register(name, factory, replace=True)


def builtin_reporter_names() -> tuple[str, ...]:
    """返回所有内置 reporter 注册名的元组，便于 CLI 校验和文档展示。"""
    return BUILTIN_NAMES
