"""protocols/registry.py — 协议执行器注册表。

职责：
  - protocol 名 → ProtocolExecutor 实例的分派（状态机 _do_call 的第一段）；
  - 与 StrategyDispatcher 联动：注册协议时同步在 dispatcher 登记其 kind，
    卸载时同步移除 —— 两张表永不失同步；
  - 按插件名批量注销（插件热卸载路径，与 event/hook 的清理纪律一致）；
  - 线程安全（RLock）：注册集中在 bootstrap 期，运行期只读，
    加锁是为并行 suite 场景下的注册/查询互斥兜底。

内置协议：http（protocols/builtin/http.py，注册表第一员）。
扩展方式：插件在 on_activate 里 ctx.register_protocol(MyProtocolExecutor())
（core/plugin.py），或测试/嵌入场景直接 registry.register(...)。
"""
from __future__ import annotations

import threading
from typing import Any, Optional

from gimbal.log import get_logger
from gimbal.protocols.base import ProtocolExecutor

logger = get_logger(__name__)


class ProtocolRegistry:
    """协议执行器注册表（protocol → executor，附带 dispatcher 联动）。"""

    def __init__(self, dispatcher: Any = None) -> None:
        """dispatcher 可选：给了则注册/注销时同步维护 dispatcher 的 kind 表。"""
        self._executors: dict[str, ProtocolExecutor] = {}
        self._params: dict[str, "type | None"] = {}  # protocol → call 字段模型（S-1）
        self._by_plugin: dict[str, list[str]] = {}   # plugin_name → [protocol, ...]
        self._dispatcher = dispatcher
        self._lock = threading.RLock()

    # ── 注册/注销 ─────────────────────────────────────────────

    def register(
        self,
        executor: ProtocolExecutor,
        *,
        plugin_name: Optional[str] = None,
        params: Optional["type"] = None,
    ) -> None:
        """注册协议执行器；同名协议后者覆盖前者（升级语义），并同步 dispatcher。

        params 为该协议 call 字段模型（编译期校验 / ext 导出）；缺省回退读
        executor.params_model 类属性。
        """
        if not isinstance(executor, ProtocolExecutor):
            raise TypeError(
                f"协议执行器必须继承 ProtocolExecutor，得到 {type(executor).__name__}"
            )
        resolved = params or getattr(executor, "params_model", None)
        with self._lock:
            self._executors[executor.protocol] = executor
            self._params[executor.protocol] = resolved
            if plugin_name:
                protos = self._by_plugin.setdefault(plugin_name, [])
                if executor.protocol not in protos:
                    protos.append(executor.protocol)
            if self._dispatcher is not None:
                self._dispatcher.register(executor, params=resolved)
        logger.debug(
            "[ProtocolRegistry] 协议注册: protocol={} executor={} plugin={}",
            executor.protocol, type(executor).__name__, plugin_name,
        )

    def unregister(self, protocol: str) -> bool:
        """按协议名注销；同步移除 dispatcher 的 kind 表。返回是否原本存在。"""
        with self._lock:
            executor = self._executors.pop(protocol, None)
            self._params.pop(protocol, None)
            if executor is None:
                return False
            for protos in self._by_plugin.values():
                if protocol in protos:
                    protos.remove(protocol)
            if self._dispatcher is not None:
                self._dispatcher.unregister(executor.kind)
        return True

    def unregister_plugin(self, plugin_name: str) -> int:
        """按插件名注销其注册的全部协议（含 dispatcher 联动）。返回移除数量。"""
        with self._lock:
            protos = self._by_plugin.pop(plugin_name, [])
            for proto in protos:
                self.unregister(proto)
        if protos:
            logger.info(
                "[ProtocolRegistry] 插件协议注销: plugin={} removed={}", plugin_name, protos,
            )
        return len(protos)

    # ── 查询 ─────────────────────────────────────────────────

    def resolve(self, protocol: str) -> Optional[ProtocolExecutor]:
        """按协议名取执行器；未注册返回 None（调用方负责报错）。"""
        with self._lock:
            return self._executors.get(protocol)

    def params_of(self, protocol: str) -> Optional["type"]:
        """按协议名取 call 字段模型；未注册或无模型返回 None（编译期校验 / ext 用）。"""
        with self._lock:
            return self._params.get(protocol)

    def protocols(self) -> list[str]:
        """已注册协议名列表（快照）。"""
        with self._lock:
            return sorted(self._executors.keys())

    def __contains__(self, protocol: str) -> bool:
        with self._lock:
            return protocol in self._executors


def build_default_protocol_registry(dispatcher: Any = None) -> ProtocolRegistry:
    """构造默认注册表：内置 http 协议（HttpProtocolExecutor，第一员）。"""
    from gimbal.protocols.builtin.http import HttpCallParams, HttpProtocolExecutor

    registry = ProtocolRegistry(dispatcher=dispatcher)
    registry.register(HttpProtocolExecutor(), params=HttpCallParams)
    return registry
