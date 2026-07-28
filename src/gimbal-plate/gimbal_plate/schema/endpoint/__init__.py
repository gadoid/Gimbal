"""gimbal_plate.endpoint —— 被测接口的全量描述。

核心类型:
    - ``ApiSpec``       接口坐标(service / method / path / headers / timeout)
    - ``EndpointInfo``  业务自然语言信息(不进产物)
    - ``EndpointSpec``  一个接口的全量描述:坐标 + 请求/响应体形状 + 业务信息
"""
from gimbal_plate.schema.endpoint.endpoint import (
    ApiSpec,
    EndpointInfo,
    EndpointSpec,
)

__all__ = [
    "ApiSpec",
    "EndpointInfo",
    "EndpointSpec",
]