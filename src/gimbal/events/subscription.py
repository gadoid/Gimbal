"""events/subscription.py
订阅记录 + 事件过滤器。
"""
from __future__ import annotations
import re
from enum import Enum
from typing import Any, Callable, Optional
from pydantic import BaseModel, ConfigDict, Field


class SubscriptionMode(str, Enum):
    SYNC = "sync"           # 同步阻塞
    ASYNC = "async"         # 异步 fire-and-forget
    BATCH = "batch"         # 攒批


EventHandler = Callable[[Any], None]


class EventFilter(BaseModel):
    """事件过滤规则（所有条件 AND，任一字段 None 表示不参与）。"""
    model_config = ConfigDict(extra="forbid")

    event_type: Optional[str] = None
    event_type_pattern: Optional[str] = None    # 正则
    run_id: Optional[str] = None
    step_id: Optional[str] = None
    scenario_id: Optional[str] = None
    custom: dict[str, Any] = Field(default_factory=dict)

    def matches(self, event: Any) -> bool:
        """判断 event 是否通过当前过滤规则：依次匹配 event_type、event_type_pattern（re.fullmatch）、run_id、step_id、scenario_id 以及 custom 字典中的键值对，全部通过（或对应字段为 None）返回 True，否则返回 False。参数 event 为带 event_type/run_id/step_id/scenario_id 等属性的事件对象；返回布尔值。"""
        et = getattr(event, "event_type", None)
        if self.event_type and et != self.event_type:
            return False
        if self.event_type_pattern and et is not None:
            # 用 fullmatch 而非 match：避免 "step.*" 误匹配 "stepper.*"
            if not re.fullmatch(self.event_type_pattern, et):
                return False
        if self.run_id and getattr(event, "run_id", None) != self.run_id:
            return False
        if self.step_id and getattr(event, "step_id", None) != self.step_id:
            return False
        if self.scenario_id and getattr(event, "scenario_id", None) != self.scenario_id:
            return False
        for k, v in self.custom.items():
            if getattr(event, k, None) != v:
                return False
        return True


class Subscription(BaseModel):
    """一个事件订阅的不可变记录。"""
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    subscription_id: str
    event_filter: EventFilter
    handler: EventHandler
    mode: SubscriptionMode = SubscriptionMode.SYNC
    plugin_name: Optional[str] = None
    priority: int = 100
