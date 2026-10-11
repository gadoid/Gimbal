"""M2 订阅规则（M2 方案 v2.4 §2 B 类；步骤 1 定义形态）。

与执行器 ``gimbal/schema/subscribe.py`` 同构（本就 forbid）；
``normalize_subscribe_spec`` 等运行时函数留在执行器，M2 只收定义。
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

# where 键的合法事件字段（除执行上下文标签外）——与执行器同源
EVENT_WHERE_FIELDS: tuple[str, ...] = (
    "event_type", "status", "scenario_id", "step_id", "suite_id",
    "plugin_name", "level",
)


class LogSelector(BaseModel):
    """日志选择器：按最低级别与 category 过滤。"""

    model_config = ConfigDict(extra="forbid")

    level: Optional[str] = Field(
        default=None, description="最低日志级别（大小写不敏感）")
    category: Optional[str] = Field(
        default=None, description="日志分类或通配（* / ?）")


class SubscribeRule(BaseModel):
    """单条订阅规则：选择（events/logs）× 过滤（where）× 输出（sink）。"""

    model_config = ConfigDict(extra="forbid")

    events: Optional[list[str]] = Field(
        default=None, description="事件类型或模式（fnmatch 通配）；None=不订阅事件")
    logs: Optional[LogSelector] = Field(
        default=None, description="日志选择器；None=不订阅日志")
    where: dict[str, str] = Field(
        default_factory=dict, description="标签或事件字段 → 精确值或通配")
    sink: str = Field(..., description="输出通道：stdout | stderr | file:<path>")
