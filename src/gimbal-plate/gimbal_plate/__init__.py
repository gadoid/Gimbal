"""gimbal_plate —— 被测系统结构知识库。

本期公共 API(C1 + C2):
    结构定义:
        EndpointSpec, ApiSpec, RequestSpec, ResponseSpec,
        IOFieldBinding, EndpointMetadata, ServiceDefinition
    能力提供:
        EndpointCase, EndpointCaseDataset, EndpointCaseExporter
    注册表:
        PlateRegistry, registry
"""

# 结构定义层
from gimbal_plate.schema.endpoint import (
    ApiSpec,
    EndpointMetadata,
    EndpointSpec,
    IOFieldBinding,
    RequestSpec,
    ResponseSpec,
)

# 服务定义层
from gimbal_plate.service import ServiceDefinition

# C2 用例导出
from gimbal_plate.case import (
    EndpointCase,
    EndpointCaseDataset,
    EndpointCaseExporter,
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
    "IOFieldBinding",
    "EndpointMetadata",
    "ServiceDefinition",
    # C2 用例导出
    "EndpointCase",
    "EndpointCaseDataset",
    "EndpointCaseExporter",
    # Registry
    "PlateRegistry",
    "registry",
]
