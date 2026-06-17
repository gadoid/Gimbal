from __future__ import annotations
from datetime import datetime, timezone
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
        """将当前 context 标记为已封存(sealed),冻结所有字段赋值;仅在未封存时生效,并记录封存时间。"""
        if not self._sealed:
            self._sealed = True
            # 修复 #3：使用 timezone-aware datetime
            self._sealed_at = datetime.now(timezone.utc)

    @property
    def is_sealed(self) -> bool:
        """返回 context 是否已被封存;True 表示字段不能再重新赋值。"""
        return self._sealed

    @property
    def sealed_at(self) -> Optional[datetime]:
        """返回封存时的时间戳(timezone-aware);未封存则返回 None。"""
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