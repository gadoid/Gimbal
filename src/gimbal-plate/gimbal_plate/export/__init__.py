"""gimbal_plate.export —— 面向不同消费者的导出模块。

按 V3 PLATE_V3_DESIGN.md §4:每个消费者一个独立模块,输入统一是 EndpointSpec
(以及 systems/ 下的默认模板),不影响 schema/ 与 systems/。

V3.1.1 抽象化:本包提供三种入口,调用方按场景任选其一:

    1. **声明式 dispatch** —— 调试 / UI 配置 / 动态 consumer 名
       ``from gimbal_plate.export import dispatch``
       ``dispatch("platform", scenario=sc, endpoints=ALL_ENDPOINTS)``

    2. **静态契约** —— 编译时类型检查 / IDE 自动补全
       ``from gimbal_plate.export import PlatformConsumerRequest``
       ``from gimbal_plate.export.platform import PlatformScenarioExporter``

    3. **直接调用 exporter** —— 已有调用方代码直接继承自 Step 1
       ``from gimbal_plate.export.platform import PlatformScenarioExporter``
       ``PlatformScenarioExporter(sc, endpoints=...).to_dict()``

两条新路径(1 和 2)共享同一份 ``ConsumerRequest`` 定义 + 同一份 exporter
实现。改任一处,两条路径都生效。

消费者列表(V3.1.1 实装):
    - gimbal:   翻译为 gimbal 引擎可执行 dict
    - platform: 翻译为 platform 后端渲染视图 dict(支持 sections 切片)

公开 API
--------
    声明式入口:
        dispatch(consumer, scenario, **kwargs) -> dict
        available_consumers() -> list[str]

    静态契约:
        GimbalConsumerRequest
        PlatformConsumerRequest
        PlatformSection

    ABC + 具体实现:
        ScenarioExporter(ABC)
        ExporterCapabilities
        GimbalScenarioExporter
        PlatformScenarioExporter
        PlatformScenarioView / PlatformEndpointView / PlatformStepView

    旧版数据模型(继续导出,向后兼容):
        EndpointCase / EndpointCaseDataset / EndpointCaseExporter
"""
from gimbal_plate.export._protocol import (
    ExporterCapabilities,
    ScenarioExporter,
)
from gimbal_plate.export._registry import available_consumers, dispatch
from gimbal_plate.export._requests import (
    GimbalConsumerRequest,
    PlatformConsumerRequest,
    PlatformSection,
)
from gimbal_plate.export.gimbal import (
    EndpointCase,
    EndpointCaseDataset,
    EndpointCaseExporter,
    GimbalScenarioExporter,
)
from gimbal_plate.export.platform import (
    PlatformEndpointView,
    PlatformScenarioExporter,
    PlatformScenarioView,
    PlatformStepView,
)

__all__ = [
    # 声明式入口
    "dispatch",
    "available_consumers",
    # 静态契约(请求模型)
    "GimbalConsumerRequest",
    "PlatformConsumerRequest",
    "PlatformSection",
    # ABC
    "ScenarioExporter",
    "ExporterCapabilities",
    # 现有 exporter
    "GimbalScenarioExporter",
    "PlatformScenarioExporter",
    "PlatformScenarioView",
    "PlatformEndpointView",
    "PlatformStepView",
    # 旧版(向后兼容)
    "EndpointCase",
    "EndpointCaseDataset",
    "EndpointCaseExporter",
]