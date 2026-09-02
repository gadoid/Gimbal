"""gimbal_plate —— 被测系统结构知识库。

本期公共 API(C1 + C2):
    结构定义:
        EndpointSpec, ApiSpec, RequestSpec, ResponseSpec,
        DeclarationEntry, EndpointMetadata, ServiceDefinition
    能力提供:
        EndpointCase, EndpointCaseDataset, EndpointCaseExporter,
        GimbalScenarioExporter
    注册表:
        PlateRegistry, registry
"""

# 结构定义层
from gimbal_plate.schema.endpoint import (
    ApiSpec,
    DeclarationEntry,
    EndpointMetadata,
    EndpointSpec,
    RequestSpec,
    ResponseSpec,
)
from gimbal_plate.schema.service_definition import ServiceDefinition

# C2 用例导出(从 export.gimbal 提供,case/ 旧模块已删除)
from gimbal_plate.export.gimbal import (
    EndpointCase,
    EndpointCaseDataset,
    EndpointCaseExporter,
    GimbalScenarioExporter,
)

# Registry facade
from gimbal_plate.registry import (
    PlateRegistry,
    registry,
)

__all__ = [
    # 结构定义
    "EndpointSpec",
    "ApiSpec",
    "RequestSpec",
    "ResponseSpec",
    "DeclarationEntry",
    "EndpointMetadata",
    "ServiceDefinition",
    # C2 用例导出
    "EndpointCase",
    "EndpointCaseDataset",
    "EndpointCaseExporter",
    "GimbalScenarioExporter",
    # Registry
    "PlateRegistry",
    "registry",
]
