"""context/resolver.py

运行期模板解析器。

职责：
    在 Step 执行前，把 schema 中所有 ${} 引用替换为实际值。
    返回新的 Step 对象，不修改原始 schema。

数据源（按优先级）：
    auth.*      → BootstrapConfig.users   AuthSession 对象及其 @property
    service.*   → BootstrapConfig.services
    *           → Scenario.channels（Extract 提升的动态值）

解析方式：
    统一 JSONPath 导航，依赖 utils/jsonpath.py 的 get() 函数。
    jsonpath.py 需要支持 getattr 导航（Pydantic 模型 + @property）。

不处理的内容：
    表达式计算、字符串格式化、用例展开 —— 这些属于编译期职责。
    运行期只做"读取动态值"这一件事。
"""
from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from gimbal.config.models import BootstrapConfig
    from gimbal.context.views import StepContextAdapter
    from gimbal.schema.step import Step
    from gimbal.schema.api import Api, ApiUnion
    from gimbal.schema.request import Request, RequestUnion
    from gimbal.schema.strategy import StrategyUnion

from gimbal.log import get_logger
logger = get_logger(__name__)

# ${} 内部默认 JSONPath，$ 可省略
# 保留前缀，用于路由到不同数据源
_RESERVED_NAMESPACES = {"auth", "service"}


class SpecResolver:
    """运行期模板解析器。

    用法::

        resolver = SpecResolver(view, config)
        resolved_step = resolver.resolve(step_schema)
        # resolved_step 里所有 ${} 已替换为实际值
    """

    def __init__(
        self,
        view: "StepContextAdapter",
        config: "BootstrapConfig",
    ) -> None:
        self._view = view
        self._config = config
        # 构建根上下文，所有数据源合并到一个 dict
        self._root = self._build_root()
        logger.debug("[SpecResolver] 根上下文构建完成，channels keys={}",
                     list(self._root.get("_channels", {}).keys()))

    # ── 公开接口 ──────────────────────────────────────────────────────────────

    def resolve(self, step: "Step") -> "Step":
        """解析整个 Step，返回新对象，原始 schema 不变。"""
        from gimbal.schema.step import Step

        resolved = Step(
            kind=step.kind,
            description=step.description,
            api=self._resolve_api(step.api),
            request=self._resolve_request(step.request),
            strategy=[self._resolve_strategy(s) for s in step.strategy],
        )
        logger.debug("[SpecResolver] Step 解析完成")
        return resolved

    # ── 各字段解析 ────────────────────────────────────────────────────────────

    def _resolve_api(self, api: "ApiUnion") -> "ApiUnion":
        from gimbal.schema.api import Api, ApiRef

        if isinstance(api, ApiRef):
            return api  # Ref 未展开，跳过

        # 解析 headers，过滤 None 值（解析失败时）
        resolved_headers = {
            k: self._resolve_value(v)
            for k, v in (api.headers or {}).items()
        }
        # 移除解析失败的 None 值
        resolved_headers = {k: v for k, v in resolved_headers.items() if v is not None}

        return Api(
            kind=api.kind,
            service=api.service,
            method=api.method,
            path=self._resolve_value(api.path),
            headers=resolved_headers,
            timeout=api.timeout,
        )

    def _resolve_request(self, request: "RequestUnion") -> "RequestUnion":
        from gimbal.schema.request import Request, RequestRef

        if isinstance(request, RequestRef):
            return request

        # body 类型从 Dict[str, Any] 扩展为 Union[Dict[str, Any], List[Any]]
        # 走 _resolve_nested 才能递归到 list 元素里的 ${} 模板；用 _resolve_dict
        # 在 list body 上只会整体返回 list，内部 ${var.x} 不会被替换。
        return Request(
            kind=request.kind,
            body=self._resolve_nested(request.body or {}),
        )

    def _resolve_strategy(self, strategy: "StrategyUnion") -> "StrategyUnion":
        from gimbal.schema.strategy import (
            Extract, Assign, Assertion, StrategyRef
        )

        if isinstance(strategy, StrategyRef):
            return strategy

        if isinstance(strategy, Extract):
            return Extract(
                **self._base_fields(strategy),
                expression=self._resolve_value(strategy.expression),
                target=strategy.target,        # target 是写入 key，不做解析
                scope=strategy.scope,
                default=self._resolve_value(strategy.default),
                required=strategy.required,
            )

        if isinstance(strategy, Assign):
            return Assign(
                **self._base_fields(strategy),
                source=self._resolve_value(strategy.source),
                target=strategy.target,        # target 是写入 key，不做解析
                scope=strategy.scope,
                default=self._resolve_value(strategy.default),
                required=strategy.required,
            )

        if isinstance(strategy, Assertion):
            return Assertion(
                **self._base_fields(strategy),
                target=self._resolve_value(strategy.target),
                operator=strategy.operator,
                expected=self._resolve_value(strategy.expected),
                message=strategy.message,
                soft=strategy.soft,
            )

        # 未知策略类型，原样返回
        return strategy

    # ── 核心解析逻辑 ──────────────────────────────────────────────────────────

    def _resolve_value(self, value: Any) -> Any:
        """解析单个值。

        三种情况：
            1. 非字符串         → 原样返回
            2. 不含 ${}        → 原样返回
            3. 含 ${}          → 模板替换
                a. 整体是单个 ${} → 保留原始类型（int/dict/...）
                b. 嵌入式 ${}    → 字符串拼接
        """
        if not isinstance(value, str):
            return value

        from gimbal.utils.jsonpath import is_template, resolve_template

        if not is_template(value):
            return value

        resolved = resolve_template(value, self._root)

        if resolved is None:
            logger.warning("[SpecResolver] 变量未找到: {}", value)

        logger.debug("[SpecResolver] 解析: {!r} → {!r}", value, resolved)
        return resolved

    def _resolve_dict(self, data: dict) -> dict:
        """递归解析 dict 的所有值。"""
        return {k: self._resolve_nested(v) for k, v in data.items()}

    def _resolve_nested(self, value: Any) -> Any:
        """递归解析嵌套结构。"""
        if isinstance(value, dict):
            return self._resolve_dict(value)
        if isinstance(value, list):
            return [self._resolve_nested(item) for item in value]
        return self._resolve_value(value)

    # ── 根上下文构建 ──────────────────────────────────────────────────────────

    def _build_root(self) -> dict:
        """构建统一的根上下文 dict。

        结构：
            {
                "auth":    users dict（值为 AuthSession 对象）,
                "service": services dict,
                # channels 里的变量直接展平到根
                "token":   "eyJxx...",
                "user_id": 42,
                ...
            }

        优先级：channels 变量 < service < auth
        （高优先级后写，覆盖低优先级同名 key）
        """
        root: dict = {}

        # 1. Scenario.channels（优先级最低，先写）
        channels_vars = self._view._ctx.parent.channels.variables_snapshot()
        root.update(channels_vars)
        logger.debug("[SpecResolver] channels 变量: {}", list(channels_vars.keys()))

        # 2. services
        if self._config.services:
            root["service"] = self._config.services

        # 3. users（优先级最高，后写）
        if self._config.users:
            root["auth"] = self._config.users

        return root

    # ── 辅助 ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _base_fields(strategy: Any) -> dict:
        """提取 StrategyBase 的公共字段。"""
        return {
            "kind":      strategy.kind,
            "name":      strategy.name,
            "phase":     strategy.phase,
            "order":     strategy.order,
            "enabled":   strategy.enabled,
            "onFailure": strategy.onFailure,
            "timeout":   strategy.timeout,
            "tags":      strategy.tags,
        }