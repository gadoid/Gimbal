"""gimbal_plate.export._requests —— 各 consumer 的请求模型(V3.1.1)。

设计背景
--------
plate 对外暴露的服务是**无状态**的:

    - 状态的变更(``ServiceDefinition`` / ``EndpointSpec`` / ``Scenario``
      等数据类对象的版本变更)由 plate 内部管理
    - 对外的请求被**统一过**:无论调用方是 gimbal 引擎、platform 后端,
      还是未来的 apidoc / mock / mcp 消费者,都看到同一份 ``dispatch()``
      入口形态,plate 负责路由与校验

这个设计的两个落地形态:

    1. **声明式入口** ``dispatch(consumer, ...)`` —— 用于调试、UI 配置、
       动态 consumer 名场景
    2. **静态契约** ``GimbalConsumerRequest(...)`` / ``PlatformConsumerRequest(...)``
       —— 用于固定契约、编译时类型检查、IDE 自动补全

两条路径共享同一份字段定义。改 request model,两条路径都生效。

设计原则
--------
    - 每个 consumer 一个独立的 ``BaseModel`` 子类,声明它接受的入参
    - 字段类型 / 可选值 / 默认值 全部集中在请求模型里
    - ``dispatch()`` 入口用对应请求模型做校验,错误信息来自 Pydantic
    - 调用方可直接 import 请求模型(静态契约),也可走 ``dispatch()``
      (动态入口)——两条路径共享同一份字段定义

为何用 Pydantic BaseModel 而不是 dataclass:
    - ``sections`` 字段用 ``Literal[...]`` 校验非允许值
    - ``scenario`` / ``endpoints`` 自动校验类型
    - 与 ``gimbal_plate.schema.*`` 风格一致

消费者列表(V3.1.1 实装):
    - "gimbal"   → ``GimbalConsumerRequest``
    - "platform" → ``PlatformConsumerRequest``
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from gimbal_plate.schema.endpoint import EndpointSpec
from gimbal_plate.schema.scenario import Scenario as ScenarioModel


# ── gimbal ────────────────────────────────────────────────────────────

class GimbalConsumerRequest(BaseModel):
    """gimbal consumer 的请求模型。

    用途:把 ``Scenario`` 翻译为 gimbal 引擎可执行 dict,丢弃平台视图扩展字段。

    字段:
        consumer: 固定为 "gimbal",用作 dispatch 路由键。
        scenario: 要翻译的 Scenario 数据类。
    """

    model_config = ConfigDict(extra="forbid")

    consumer: Literal["gimbal"] = "gimbal"
    scenario: ScenarioModel


# ── platform ──────────────────────────────────────────────────────────

# platform 视图允许的 sections(显式枚举,便于 IDE 提示与 dispatch 校验)
PlatformSection = Literal["endpoints", "navigation", "config_summary"]


class PlatformConsumerRequest(BaseModel):
    """platform consumer 的请求模型。

    用途:把 ``Scenario`` 翻译为 platform 后端消费的渲染视图 dict。
    V3.1.1 引入 ``sections`` 字段以支持声明式切片:调用方可只选
    ``("endpoints", "navigation")`` 而非整视图。

    字段:
        consumer: 固定为 "platform"。
        scenario: 要翻译的 Scenario 数据类。
        endpoints: 可选;``ALL_ENDPOINTS`` 列表;不提供时 endpoints /
            navigation / config_summary 都是空集。
        sections: 要包含的视图切片;默认全选。
    """

    model_config = ConfigDict(extra="forbid")

    consumer: Literal["platform"] = "platform"
    scenario: ScenarioModel
    endpoints: list[EndpointSpec] | None = None
    sections: tuple[PlatformSection, ...] = (
        "endpoints",
        "navigation",
        "config_summary",
    )


__all__ = [
    "GimbalConsumerRequest",
    "PlatformConsumerRequest",
    "PlatformSection",
]