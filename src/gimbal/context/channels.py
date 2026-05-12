from __future__ import annotations
from datetime import datetime
from typing import Any, Callable, Iterable, Optional
from pydantic import BaseModel, ConfigDict, Field

from .base import ContextLayer
from .exceptions import PromotionRejected


class ArtifactRef(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    key: str
    content_type: str
    size_bytes: int
    sha256: str
    created_at: datetime


class Promotion(BaseModel):
    """一次变量提升的不可变审计记录。"""
    model_config = ConfigDict(frozen=True)
    
    key: str
    value: Any
    from_layer: ContextLayer
    to_layer: ContextLayer
    by_step_id: str
    by_scenario_id: Optional[str] = None
    at: datetime
    reason: Optional[str] = None
    overwrote_previous: bool = False     # 是否覆盖了已有值


class ChannelsPolicy(BaseModel):
    """声明本层 channels 接受什么样的提升。
    
    Policy 在 Context 创建时由 ContextManager 注入,运行期间不可变。
    """
    model_config = ConfigDict(frozen=True)
    
    # 接受来自哪些 layer 的提升
    accept_from_layers: frozenset[ContextLayer] = Field(
        default_factory=lambda: frozenset({ContextLayer.STEP})
    )
    
    # 默认所有 key 不可覆盖(只能新增);列在这里的 key 允许覆盖
    overwritable_keys: frozenset[str] = frozenset()
    
    # 显式禁止的 key(如 framework 配置不允许被业务覆盖)
    forbidden_keys: frozenset[str] = frozenset()
    
    # 提升时是否强制要求 reason
    require_reason: bool = False
    
    # 允许的 key 前缀(空集表示不限制)
    allowed_key_prefixes: frozenset[str] = frozenset()


# 几个常用的预设 policy
class Policies:
    @staticmethod
    def scenario_default() -> ChannelsPolicy:
        """Scenario 层:接受 step 提升,大部分 key 可覆盖(支持 token 刷新)。"""
        return ChannelsPolicy(
            accept_from_layers=frozenset({ContextLayer.STEP}),
            overwritable_keys=frozenset(),   # 由 step 在 promote 时显式声明
            require_reason=False,
        )
    
    @staticmethod
    def suite_default() -> ChannelsPolicy:
        """Suite 层:接受 scenario 提升,key 不可覆盖(共享资源一次性产出)。"""
        return ChannelsPolicy(
            accept_from_layers=frozenset({ContextLayer.SCENARIO}),
            overwritable_keys=frozenset(),
            require_reason=True,    # suite 级提升必须说明原因
        )
    
    @staticmethod
    def framework_locked() -> ChannelsPolicy:
        """Framework 层:不接受任何提升。"""
        return ChannelsPolicy(
            accept_from_layers=frozenset(),
            require_reason=True,
        )


PromotionListener = Callable[[Promotion], None]


class Channels:
    """三通道数据载体(variables/metadata/artifacts)。
    
    所有写入必须经过 promote_from()——这是显式建模的"向上提升"操作。
    seal 不影响本类——本类的设计意图就是接受演化。
    
    数据通过私有属性持有,外部只能通过受控接口访问。
    """
    
    def __init__(
        self,
        *,
        owner_layer: ContextLayer,
        policy: ChannelsPolicy,
    ):
        self._owner_layer = owner_layer
        self._policy = policy
        self._variables: dict[str, Any] = {}
        self._metadata: dict[str, Any] = {}
        self._artifacts: dict[str, ArtifactRef] = {}
        self._promotions: list[Promotion] = []
        self._listeners: list[PromotionListener] = []
    
    # ── 监听器:ContextManager 注册,用于把 Promotion 转事件 ──
    def add_listener(self, listener: PromotionListener) -> None:
        self._listeners.append(listener)
    
    # ── 只读访问 ─────────────────────────────────────────
    def get_variable(self, key: str, default: Any = None) -> Any:
        return self._variables.get(key, default)
    
    def has_variable(self, key: str) -> bool:
        return key in self._variables
    
    def variables_snapshot(self) -> dict[str, Any]:
        """返回防御性拷贝。外部修改不会影响内部状态。"""
        return dict(self._variables)
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        return self._metadata.get(key, default)
    
    def metadata_snapshot(self) -> dict[str, Any]:
        return dict(self._metadata)
    
    def get_artifact(self, name: str) -> Optional[ArtifactRef]:
        return self._artifacts.get(name)
    
    def artifacts_snapshot(self) -> dict[str, ArtifactRef]:
        return dict(self._artifacts)
    
    @property
    def promotions(self) -> tuple[Promotion, ...]:
        """提升的完整历史,只读。"""
        return tuple(self._promotions)
    
    @property
    def owner_layer(self) -> ContextLayer:
        return self._owner_layer
    
    @property
    def policy(self) -> ChannelsPolicy:
        return self._policy
    
    # ── 写入:promote_from 是唯一入口 ─────────────────────
    def promote_from(
        self,
        *,
        key: str,
        value: Any,
        from_layer: ContextLayer,
        by_step_id: str,
        by_scenario_id: Optional[str] = None,
        reason: Optional[str] = None,
        allow_overwrite: bool = False,
    ) -> Promotion:
        """接受下层向本层提升一个变量。
        
        allow_overwrite: 调用方显式声明"我知道这会覆盖"。
          policy 中也必须把这个 key 列入 overwritable_keys 才会真正放行。
        """
        self._check_policy(
            key=key,
            from_layer=from_layer,
            reason=reason,
            allow_overwrite=allow_overwrite,
        )
        
        overwrote = key in self._variables
        record = Promotion(
            key=key,
            value=value,
            from_layer=from_layer,
            to_layer=self._owner_layer,
            by_step_id=by_step_id,
            by_scenario_id=by_scenario_id,
            at=datetime.utcnow(),
            reason=reason,
            overwrote_previous=overwrote,
        )
        self._variables[key] = value
        self._promotions.append(record)
        self._notify(record)
        return record
    
    def attach_artifact_from(
        self,
        *,
        name: str,
        ref: ArtifactRef,
        from_layer: ContextLayer,
        by_step_id: str,
    ) -> None:
        """大对象引用的附加(走同样的 policy 检查思路,这里简化)。"""
        if from_layer not in self._policy.accept_from_layers:
            raise PromotionRejected(
                f"{from_layer.value} cannot attach artifact to "
                f"{self._owner_layer.value}"
            )
        self._artifacts[name] = ref
    
    def write_metadata_from(
        self,
        *,
        key: str,
        value: Any,
        from_layer: ContextLayer,
        by_step_id: str,
    ) -> None:
        """metadata 用于框架层数据(retry 次数、耗时等),policy 相对宽松。
        但同样必须经过受控接口,不直接暴露字典。"""
        self._metadata[key] = value
    
    # ── 内部:策略检查 ────────────────────────────────────
    def _check_policy(
        self,
        *,
        key: str,
        from_layer: ContextLayer,
        reason: Optional[str],
        allow_overwrite: bool,
    ) -> None:
        p = self._policy
        
        if from_layer not in p.accept_from_layers:
            raise PromotionRejected(
                f"Layer {from_layer.value} cannot promote to "
                f"{self._owner_layer.value} (policy: accept_from="
                f"{[l.value for l in p.accept_from_layers]})"
            )
        
        if key in p.forbidden_keys:
            raise PromotionRejected(
                f"Key '{key}' is forbidden by policy on "
                f"{self._owner_layer.value} channels"
            )
        
        if p.allowed_key_prefixes and not any(
            key.startswith(prefix) for prefix in p.allowed_key_prefixes
        ):
            raise PromotionRejected(
                f"Key '{key}' does not match allowed prefixes "
                f"{list(p.allowed_key_prefixes)}"
            )
        
        if key in self._variables:
            # 已存在:必须调用方声明 allow_overwrite,且 policy 允许
            if not allow_overwrite:
                raise PromotionRejected(
                    f"Key '{key}' already exists; caller must set "
                    f"allow_overwrite=True to overwrite"
                )
            if key not in p.overwritable_keys:
                raise PromotionRejected(
                    f"Key '{key}' is not in overwritable_keys "
                    f"on {self._owner_layer.value} channels"
                )
        
        if p.require_reason and not reason:
            raise PromotionRejected(
                f"Promotion to {self._owner_layer.value} requires a reason"
            )
    
    def _notify(self, record: Promotion) -> None:
        for listener in self._listeners:
            try:
                listener(record)
            except Exception:
                # 监听器异常不应影响主流程,这里可接日志
                pass