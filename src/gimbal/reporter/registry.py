"""reporter/registry.py — ReporterRegistry 注册表。

镜像 ``StrategyDispatcher`` 的设计：name → factory，支持：
  - 自注册（``builtin/__init__.py`` 启动时调用 ``register``）
  - 第三方插件在 ``on_activate`` 中通过 ``ctx.plugin_registry.register_reporter`` 注册
  - entry_point 组 ``gimbal.reporters`` 自动发现（bootstrap 阶段）

factory 形式：``Callable[[dict[str, Any]], Reporter]``，参数是 user_config 子字典。
这样可以延迟实例化（每次 run 创建新实例），避免 reporter 内部状态污染。
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from gimbal.exceptions import GimbalError
from gimbal.log import get_logger

logger = get_logger(__name__)


ReporterFactory = Callable[[dict[str, Any]], "Reporter"]  # noqa: F821
# Avoid forward reference issues at import time:
# "Reporter" is defined in protocol.py; we keep string annotation to skip import.


class ReporterAlreadyRegistered(GimbalError):
    """重复注册同名 Reporter。"""
    code = "REPORTER_ALREADY_REGISTERED"


class ReporterNotFound(GimbalError):
    """未注册的 Reporter 名。"""
    code = "REPORTER_NOT_FOUND"


class ReporterRegistry:
    """Reporter 注册表。"""

    def __init__(self) -> None:
        self._factories: dict[str, ReporterFactory] = {}

    # ── 注册 ────────────────────────────────────────────────────────────

    def register(
        self,
        name: str,
        factory: ReporterFactory,
        *,
        replace: bool = False,
    ) -> None:
        """注册一个 Reporter 工厂。

        Args:
            name:    注册名，例如 "console" / "junit" / "allure"
            factory: ``factory(user_config: dict) -> Reporter`` 形式
            replace: 已存在时是否允许覆盖（默认 False 抛 ReporterAlreadyRegistered）
        """
        if not name:
            raise ValueError("ReporterRegistry.register: name 不能为空")
        if not callable(factory):
            raise TypeError(
                f"ReporterRegistry.register: factory 必须是 callable，"
                f"实际类型 {type(factory).__name__}"
            )
        if name in self._factories and not replace:
            raise ReporterAlreadyRegistered(
                f"Reporter {name!r} 已经注册；如需覆盖请传 replace=True"
            )
        self._factories[name] = factory
        logger.debug(
            "[ReporterRegistry] registered: name={} factory={}",
            name, getattr(factory, "__name__", repr(factory)),
        )

    def unregister(self, name: str) -> bool:
        """注销一个 Reporter。返回是否真的存在并被删除。"""
        return self._factories.pop(name, None) is not None

    # ── 查询 ────────────────────────────────────────────────────────────

    def available(self) -> list[str]:
        """已注册的 reporter 名称列表（按注册顺序）。"""
        return list(self._factories.keys())

    def has(self, name: str) -> bool:
        return name in self._factories

    def get_factory(self, name: str) -> ReporterFactory:
        if name not in self._factories:
            raise ReporterNotFound(
                f"Reporter {name!r} 未注册；已注册的: {self.available()}"
            )
        return self._factories[name]

    # ── 实例化 ──────────────────────────────────────────────────────────

    def create(
        self,
        names: list[str],
        user_configs: Optional[dict[str, dict[str, Any]]] = None,
    ) -> list["Reporter"]:  # noqa: F821
        """按 names 顺序实例化 reporter。

        Args:
            names:       启用的 reporter 名列表
            user_configs: 按 reporter 名的 user_config 子字典；缺 key 时传空 dict

        Returns:
            与 names 等长的 reporter 实例列表

        Raises:
            ReporterNotFound: 任一 name 未注册
        """
        cfgs = user_configs or {}
        result = []
        for n in names:
            factory = self.get_factory(n)
            user_cfg = cfgs.get(n) or {}
            try:
                reporter = factory(user_cfg)
            except Exception as exc:  # noqa: BLE001
                raise GimbalError(
                    f"Reporter {n!r} factory 调用失败: {exc}",
                    reporter_name=n,
                ) from exc
            result.append(reporter)
        return result

    # ── 调试 ────────────────────────────────────────────────────────────

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ReporterRegistry names={self.available()}>"
