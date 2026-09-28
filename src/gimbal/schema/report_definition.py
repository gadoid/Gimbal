"""schema/report_definition.py — 报告定义(B5/P3-06,定稿 D9)。

报告 = 选择(订阅规格) + 投影(JSONPath 字段清单) + 呈现(html/markdown/
table)。报告定义是**声明性**的 —— 不写代码即可定制「看什么、怎么呈现」;
``reporter/definition_reporter.py`` 消费此模型产出报告工件。

与 P1-04 订阅的关系:选择的 ``events``/``where`` 语法与订阅规格同源
(同一套编译器/匹配器),报告只是多一层投影与呈现。
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ReportSelection(BaseModel):
    """选择面:哪些事件/日志进报告(与 P1-04 订阅规格同源)。"""
    model_config = ConfigDict(extra="forbid")

    events: list[str] = Field(
        default_factory=lambda: ["*"],
        description="事件类型/模式(fnmatch;['*'] = 全部)")
    where: dict[str, str] = Field(
        default_factory=dict,
        description="标签/字段过滤(P1-04 同款 where 语法)")


class ReportProjection(BaseModel):
    """投影面:从事件 payload 提取哪些字段(JSONPath)。"""
    model_config = ConfigDict(extra="forbid")

    source: str = Field(
        default="payload",
        description="取值根:payload(事件 dump)| event(事件对象属性)")
    fields: list[str] = Field(
        default_factory=lambda: ["seq", "event_type", "message"],
        description="JSONPath 字段清单(按序渲染为报告列/键)")


class ReportPresentation(BaseModel):
    """呈现面:格式与模板。"""
    model_config = ConfigDict(extra="forbid")

    format: Literal["html", "markdown", "table"] = Field(
        default="html",
        description="呈现格式")
    title: str = Field(default="执行报告", description="报告标题")
    # 可选自定义模板(html/markdown 的 Jinja2 模板串;缺省用内置模板)
    template: Optional[str] = Field(
        default=None,
        description="自定义模板(Jinja2;缺省用内置)")


class ReportDefinition(BaseModel):
    """报告定义(B5):选择 + 投影 + 呈现,声明性可存储复用。"""
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=128,
                      description="定义名(唯一)")
    description: str = Field(default="", description="说明")
    selection: ReportSelection = Field(default_factory=ReportSelection)
    projection: ReportProjection = Field(default_factory=ReportProjection)
    presentation: ReportPresentation = Field(default_factory=ReportPresentation)
