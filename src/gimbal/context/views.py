from typing import Any, Optional, Protocol, runtime_checkable
from .base import ContextLayer
from .channels import ArtifactRef
from .exceptions import LayerResolutionError, ContextError
from .step import StepContext, AssertionResult
from gimbal.context.step import HttpExchange

@runtime_checkable
class StrategyContextView(Protocol):
    @property
    def step_id(self) -> str: ...
    @property
    def scenario_id(self) -> str: ...
    @property
    def strategy_spec(self) -> dict: ...
    @property
    def resolved_vars(self) -> dict[str, Any]: ...
    
    def read_variable(
        self, key: str, *,
        from_layer: ContextLayer = ContextLayer.SCENARIO,
        default: Any = None,
    ) -> Any: ...

    def resolve(
        self, key: str, default: Any = None,
    ) -> Any: ...

    def promote_variable(
        self, key: str, value: Any, *,
        to: ContextLayer = ContextLayer.SCENARIO,
        reason: Optional[str] = None,
        allow_overwrite: bool = False,
    ) -> None: ...
    
    def record_assertion(self, result: AssertionResult) -> None: ...
    
    def attach_artifact(
        self, name: str, ref: ArtifactRef,
        *, to: ContextLayer = ContextLayer.SCENARIO,
    ) -> None: ...


class StepContextAdapter:
    """把 StepContext 适配成 StrategyContextView。
    Strategy 拿到的是 view,不是 ctx 本身——避免越权访问。"""
    
    def __init__(self, ctx: StepContext):
        self._ctx = ctx
        self.content = ctx
    @property
    def step_id(self) -> str:
        return self._ctx.step_id
    
    @property
    def scenario_id(self) -> str:
        return self._ctx.scenario_id
    
    @property
    def strategy_spec(self) -> dict:
        return self._ctx.inputs.strategy_spec
    
    @property
    def resolved_vars(self) -> dict[str, Any]:
        return self._ctx.inputs.resolved_vars
    
    # ── 读 ───────────────────────────────────────────
    def read_variable(
        self, key: str, *,
        from_layer: ContextLayer = ContextLayer.SCENARIO,
        default: Any = None,
    ) -> Any:
        target = self._resolve_layer(from_layer)
        return target.channels.get_variable(key, default)

    def resolve(self, key: str, default: Any = None) -> Any:
        """统一查询：先 resolved_vars，再 channels，最后 config。"""
        # 1. Step 自身预解析的变量
        if key in self._ctx.inputs.resolved_vars:
            return self._ctx.inputs.resolved_vars[key]

        # 2. 默认从 SCENARIO 层的 channels 查
        target = self._ctx.parent  # scenario
        if target.channels.has_variable(key):
            return target.channels.get_variable(key)

        # 3. 查 config（直接用 model_dump 转 dict 查询）
        cfg = target.config.model_dump()
        if key in cfg:
            return cfg[key]

        return default

    # ── 写(向上提升) ─────────────────────────────────
    def promote_variable(
        self, key: str, value: Any, *,
        to: ContextLayer = ContextLayer.SCENARIO,
        reason: Optional[str] = None,
        allow_overwrite: bool = False,
    ) -> None:
        target = self._resolve_layer(to)
        target.channels.promote_from(
            key=key,
            value=value,
            from_layer=ContextLayer.STEP,
            by_step_id=self._ctx.step_id,
            by_scenario_id=self._ctx.scenario_id,
            reason=reason,
            allow_overwrite=allow_overwrite,
        )
        # 同时记录到本 step 的产物中,便于回放和归档
        self._ctx.outcome.promotions_made.append(f"{to.value}:{key}")
        self._ctx.outcome.extracted[key] = value
    
    def record_assertion(self, result: AssertionResult) -> None:
        self._ctx.outcome.assertions.append(result)
    
    def attach_artifact(
        self, name: str, ref: ArtifactRef,
        *, to: ContextLayer = ContextLayer.SCENARIO,
    ) -> None:
        target = self._resolve_layer(to)
        target.channels.attach_artifact_from(
            name=name, ref=ref,
            from_layer=ContextLayer.STEP,
            by_step_id=self._ctx.step_id,
        )
    
    # ── 内部 ─────────────────────────────────────────
    def _resolve_layer(self, layer: ContextLayer):
        if layer == ContextLayer.STEP:
            raise LayerResolutionError(
                "Cannot target STEP layer from a step view (no self-promotion)"
            )
        ctx = self._ctx.parent          # scenario
        if layer == ContextLayer.SCENARIO:
            return ctx
        ctx = ctx.parent                # suite
        if layer == ContextLayer.SUITE:
            return ctx
        ctx = ctx.parent                # framework
        if layer == ContextLayer.FRAMEWORK:
            return ctx
        raise LayerResolutionError(f"Unknown layer: {layer}")
    
    def read_http_exchange(self, *keys: str) -> dict[str, Any]:
        """读取 http_exchange 中指定字段，不传 keys 则返回全部。"""
        exchange = self._ctx.http_exchange
        if exchange is None:
            return {}
        
        if not keys:
            return {
                "request_method":   exchange.request_method,
                "request_url":      exchange.request_url,
                "request_headers":  exchange.request_headers,
                "request_body":     exchange.request_body,
                "response_status":  exchange.response_status,
                "response_headers": exchange.response_headers,
                "response_body":    exchange.response_body,
                "duration_ms":      exchange.duration_ms,
            }
        
        return {k: getattr(exchange, k, None) for k in keys}

    def write_http_exchange(self, **kwargs) -> None:
        if self._ctx.http_exchange is None:
            raise ContextError("http_exchange not initialized; reset_http_exchange() must be called before CALLING phase")
        self._ctx.http_exchange.update(**kwargs)

    def reset_http_exchange(self) -> None:
        """重置 http_exchange 为新实例，允许在 retry 时重新初始化。"""
        object.__setattr__(self._ctx, "http_exchange", HttpExchange())

    def seal_http_exchange(self) -> None:
        """封印 http_exchange，封印后不可再写入。幂等操作。"""
        if self._ctx.http_exchange is not None:
            self._ctx.http_exchange.seal()