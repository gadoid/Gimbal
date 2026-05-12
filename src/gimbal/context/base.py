from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, PrivateAttr

from .exceptions import SealedContextError


class ContextLayer(str, Enum):
    FRAMEWORK = "framework"
    SUITE = "suite"
    SCENARIO = "scenario"
    STEP = "step"
    
    def is_above(self, other: "ContextLayer") -> bool:
        """判断当前 layer 是否在 other 之上(更靠近 root)。"""
        order = [
            ContextLayer.STEP,
            ContextLayer.SCENARIO,
            ContextLayer.SUITE,
            ContextLayer.FRAMEWORK,
        ]
        return order.index(self) > order.index(other)


class SealedBaseModel(BaseModel):
    """所有 Context 的基类。
    
    seal 后:
    - 模型字段不可重新赋值(身份/状态字段冻结)
    - 但 Channels 这种"通道型"字段内部走 promote_from,不经过 __setattr__,
      因此 seal 不影响合法的变量提升。这是有意设计。
    """
    model_config = ConfigDict(
        validate_assignment=True,
        arbitrary_types_allowed=True,
        extra="forbid",
    )
    
    _sealed: bool = PrivateAttr(default=False)
    _sealed_at: Optional[datetime] = PrivateAttr(default=None)
    
    @property
    def layer(self) -> ContextLayer:
        """子类实现:声明自己所属的层级。"""
        raise NotImplementedError
    
    def seal(self) -> None:
        if not self._sealed:
            self._sealed = True
            self._sealed_at = datetime.utcnow()
    
    @property
    def is_sealed(self) -> bool:
        return self._sealed
    
    @property
    def sealed_at(self) -> Optional[datetime]:
        return self._sealed_at
    
    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            super().__setattr__(name, value)
            return
        if getattr(self, "_sealed", False):
            raise SealedContextError(
                f"{type(self).__name__} sealed at {self._sealed_at}; "
                f"cannot reassign field '{name}'. "
                f"If you need to add variables, use Channels.promote_from()."
            )
        super().__setattr__(name, value)