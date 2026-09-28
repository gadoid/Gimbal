"""schema/subscribe.py — 声明式订阅规格（P1-04）。

同一种写法（JSON 列表）在 CLI ``--subscribe <file>``、suite 配置
（``graph.subscribe``）、server 请求（``RunsRequest.subscribe``）三处生效，
编译为总线过滤 + 输出通道（events/subscribe.py）。

规格格式::

    [
      {
        "events": ["step.*", "run.finished"],   # 事件类型/模式；缺省=不订阅事件
        "logs":   {"level": "WARNING", "category": "call"},  # 缺省=不订阅日志
        "where":  {"module": "fin", "status": "failed"},     # 标签/事件字段 → 值或通配
        "sink":   "stdout" | "stderr" | "file:<path>"
      }
    ]

校验（编译期，错误码 SUBSCRIBE_INVALID，见 compiler/errors.py）：
未知 sink、未知事件类型（字面量不含通配符且不在事件表）、未知 where 键
（既不是执行上下文标签也不是事件字段）都报错。
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

# where 键的合法事件字段（除九个执行上下文标签外）
EVENT_WHERE_FIELDS: tuple[str, ...] = (
    "event_type", "status", "scenario_id", "step_id", "suite_id",
    "plugin_name", "level",
)


class LogSelector(BaseModel):
    """日志选择器：按最低级别与 category 过滤。"""
    model_config = ConfigDict(extra="forbid")

    level: Optional[str] = Field(
        default=None,
        description="最低日志级别（DEBUG/INFO/WARNING/ERROR/CRITICAL，大小写不敏感）",
    )
    category: Optional[str] = Field(
        default=None,
        description="日志分类（log/category.py 词表）或通配（* / ?）",
    )


class SubscribeRule(BaseModel):
    """单条订阅规则：选择（events/logs）× 过滤（where）× 输出（sink）。"""
    model_config = ConfigDict(extra="forbid")

    events: Optional[list[str]] = Field(
        default=None,
        description="事件类型或模式列表（fnmatch 通配）；None=本规则不订阅事件",
    )
    logs: Optional[LogSelector] = Field(
        default=None,
        description="日志选择器；None=本规则不订阅日志",
    )
    where: dict[str, str] = Field(
        default_factory=dict,
        description="标签或事件字段 → 精确值或通配（fnmatch：* ? [seq]）",
    )
    sink: str = Field(
        ...,
        description="输出通道：stdout | stderr | file:<path>",
    )


SubscribeSpec = list[SubscribeRule]


def normalize_subscribe_spec(raw: Any) -> SubscribeSpec:
    """裸数据（dict 列表 / None）→ SubscribeRule 列表（pydantic 校验）。"""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("subscribe 规格必须是规则列表（JSON array）")
    return [SubscribeRule.model_validate(item) for item in raw]
