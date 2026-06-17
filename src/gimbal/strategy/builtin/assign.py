from __future__ import annotations

import logging
import traceback
from typing import Any, TYPE_CHECKING

from gimbal.strategy.executor_base import StrategyExecutor, StrategyResult, StrategyStatus
from .utils import _resolve_source_value
from gimbal.log import get_logger
logger = get_logger(__name__)

class AssignExecutor(StrategyExecutor):
    """将字面量或 context 变量赋值到指定路径。

    source 可以是：
      - 字面量（str/int/bool/dict）
      - 模板字符串 "${varname}" -> 从 context 中读取
    """

    kind = "assign"

    def execute(self, spec: "StrategyBase", view: "StrategyContextView") -> StrategyResult:
        """执行赋值策略：解析 spec.source 后的值写入 view.scratch 的 spec.target 路径，required 但解析为 None 时返回 FAILED。"""
        from gimbal.schema.strategy import Assign

        assert isinstance(spec, Assign)

        try:
            logger.debug("[AssignExecutor] 执行赋值: target={} source={} scope={}",
                        spec.target, spec.source, spec.scope)

            # 解析 source：是模板还是字面量
            value = _resolve_source_value(spec.source, view, spec.scope)

            if value is None:
                if spec.default is not None:
                    value = spec.default
                    logger.debug("[AssignExecutor] 使用默认值: target={} default={}", spec.target, value)
                elif spec.required:
                    logger.warning("[AssignExecutor] 赋值失败: target={} source={} is required but resolved to None",
                                  spec.target, spec.source)
                    return StrategyResult(
                        status=StrategyStatus.FAILED,
                        message=f"Assign: source {spec.source!r} resolved to None, field required",
                    )

            # 写入 StepScratch（支持 JSONPath 写入嵌套结构）
            view.write_scratch(spec.target, value)

            logger.info("[AssignExecutor] 赋值成功: target={} value={}", spec.target, value)

            return StrategyResult(
                status=StrategyStatus.PASSED,
                message=f"Assigned {spec.target}={value!r}",
                extracted={spec.target: value},
            )
        except Exception as exc:
            logger.exception("[AssignExecutor] 赋值异常: target={}", spec.target)
            return StrategyResult(
                status=StrategyStatus.ERROR,
                message=str(exc),
                error=traceback.format_exc(),
            )
