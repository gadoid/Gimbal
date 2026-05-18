from typing import Any, Optional, Protocol, runtime_checkable
from .base import ContextLayer
from .channels import ArtifactRef
from .exceptions import LayerResolutionError
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
    
    def read_http_exchange(self) -> Optional[HttpExchange]:
        return self._ctx.http_exchange

    def write_http_exchange(self, exchange: HttpExchange) -> None:  
        # seal 之前可以直接赋值
        object.__setattr__(self._ctx, "http_exchange", exchange)    