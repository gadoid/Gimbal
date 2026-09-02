"""gimbal_plate.schema.endpoint —— 被测接口契约的 V1 形态。"""
from gimbal_plate.schema.endpoint.api_spec import ApiSpec
from gimbal_plate.schema.endpoint.endpoint import EndpointSpec
from gimbal_plate.schema.endpoint.io_spec import (
    DeclarationEntry,
    RequestSpec,
    ResponseSpec,
)
from gimbal_plate.schema.endpoint.metadata import EndpointMetadata

__all__ = [
    "ApiSpec",
    "DeclarationEntry",
    "EndpointSpec",
    "RequestSpec",
    "ResponseSpec",
    "EndpointMetadata",
]
