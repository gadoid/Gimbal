"""M2 报告定义（M2 方案 v2.4 §2 B 类；步骤 1 定义形态）。

与执行器 ``gimbal/schema/report_definition.py`` 同构（本就 forbid）。
取代执行能力梳理 E6「投影定义在执行器」的早期口径：**定义归 plate M2，
执行实现在执行器**。平台保存报告定义时按此校验（M2 §6）。
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ReportSelection(BaseModel):
    """选择面：哪些事件/日志进报告。"""

    model_config = ConfigDict(extra="forbid")

    events: list[str] = Field(
        default_factory=lambda: ["*"],
        description="事件类型/模式（fnmatch；['*'] = 全部）")
    where: dict[str, str] = Field(
        default_factory=dict, description="标签/字段过滤")


class ReportProjection(BaseModel):
    """投影面：从事件 payload 提取哪些字段（JSONPath）。"""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(
        default="payload", description="取值根：payload | event")
    fields: list[str] = Field(
        default_factory=lambda: ["seq", "event_type", "message"],
        description="JSONPath 字段清单（按序渲染为报告列/键）")


class ReportPresentation(BaseModel):
    """呈现面：格式与模板。"""

    model_config = ConfigDict(extra="forbid")

    format: Literal["html", "markdown", "table"] = Field(default="html")
    title: str = Field(default="执行报告")
    template: Optional[str] = Field(
        default=None, description="自定义模板（Jinja2；缺省用内置）")


class ReportDefinition(BaseModel):
    """报告定义：选择 + 投影 + 呈现，声明性可存储复用。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=128)
    description: str = ""
    selection: ReportSelection = Field(default_factory=ReportSelection)
    projection: ReportProjection = Field(default_factory=ReportProjection)
    presentation: ReportPresentation = Field(default_factory=ReportPresentation)
