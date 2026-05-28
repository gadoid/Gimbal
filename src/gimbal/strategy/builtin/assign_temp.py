from __future__ import annotations

import logging
import traceback
from typing import Any, TYPE_CHECKING

from gimbal.strategy.executor_base import StrategyExecutor, StrategyResult, StrategyStatus
from .utils import _scope_to_layer
from gimbal.log import get_logger
from gimbal.utils.jsonpath import get as jsonpath_get, set_value as jsonpath_set

logger = get_logger(__name__)


def _normalize_path(path: str) -> str:
    """规范化 jsonpath：没有 $ 前缀的自动加上。"""
    path = path.strip()
    if not path.startswith("$"):
        path = "$." + path
    return path


def _jsonpath_to_key(path: str) -> str:
    """从 jsonpath 中提取最顶层的 key 名称。
    如 "$.order_no" -> "order_no", "$.data.items[0].name" -> "data"
    """
    path = path.strip()
    if path.startswith("$."):
        path = path[2:]
    import re
    m = re.match(r'^([^.[]+)', path)
    if m:
        return m.group(1)
    return path


class AssignTempExecutor(StrategyExecutor):
    """从上下文读取值并写入到 scenario context 的指定路径。

    1. 从指定层级的上下文用 jsonpath 解析 source 获取值
    2. 将值写入 scenario context 的 target 路径（使用 jsonpath set 语法）
    3. 后续步骤的模板解析会使用更新后的 context 值

    示例：
      source: "$.order_no" (从上下文读取 order_no 的值)
      target: "$.order_sn" (写入 scenario context order_sn)
      scope: SCENARIO
    """

    kind = "assign_temp"

    def execute(self, spec: "StrategyBase", view: "StrategyContextView") -> StrategyResult:
        from gimbal.schema.strategy import AssignTemp
        from gimbal.context.base import ContextLayer

        assert isinstance(spec, AssignTemp)

        try:
            # 1. 规范化路径
            source_path = _normalize_path(spec.source)
            target_path = _normalize_path(spec.target)

            # 2. 从指定层级的上下文读取值
            layer = _scope_to_layer(spec.scope)
            ctx_data = self._get_layer_context_data(view, layer)
            value = jsonpath_get(ctx_data, source_path)

            logger.debug("[AssignTempExecutor] 从上下文读取: source={} layer={} value={}",
                        source_path, layer.value, value)

            if value is None:
                logger.warning("[AssignTempExecutor] 上下文变量未找到: source={} layer={}",
                             source_path, layer.value)
                return StrategyResult(
                    status=StrategyStatus.FAILED,
                    message=f"AssignTemp: source {source_path!r} resolved to None in layer {layer.value}",
                )

            # 3. 提取 target 的顶层 key
            target_key = _jsonpath_to_key(target_path)

            # 4. 获取 scenario context 的当前数据
            scenario_layer = ContextLayer.SCENARIO
            scenario_data = self._get_layer_context_data(view, scenario_layer)

            # 5. 将值写入 target 路径
            updated_data = jsonpath_set(scenario_data, target_path, value)

            # 6. 通过 promote_variable 写入 scenario context
            view.promote_variable(target_key, updated_data, to=scenario_layer, allow_overwrite=True)

            logger.info("[AssignTempExecutor] 更新 context 成功: target={} value={} layer={}",
                       target_path, value, scenario_layer.value)

            return StrategyResult(
                status=StrategyStatus.PASSED,
                message=f"AssignTemp: set {target_path}={value!r}",
                extracted={spec.target: value},
            )
        except Exception as exc:
            logger.exception("[AssignTempExecutor] 更新异常: source={} target={}",
                           spec.source, spec.target)
            return StrategyResult(
                status=StrategyStatus.ERROR,
                message=str(exc),
                error=traceback.format_exc(),
            )

    def _get_layer_context_data(self, view, layer) -> dict:
        """获取指定层级的上下文数据字典。"""
        if not hasattr(view, "_ctx"):
            return {}
        target = view._resolve_layer(layer)
        if hasattr(target, "channels"):
            return target.channels.variables_snapshot()
        return {}
