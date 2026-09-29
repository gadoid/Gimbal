"""platform.catalog.get_services —— Get Catalog Services

`GET /api/catalog/services`

服务目录聚合(30s TTL 缓存)。

字段面由 gimbal-bootstrap 的 contract_gen 从平台 OpenAPI 生成。这个文件
**可以手改** —— 实测核订的语义（description / ui_kind / required）写在
这里，重新生成默认不覆盖；要覆盖用 --force。
"""

from typing import Final

from gimbal_plate.schema.endpoint import (
    ApiSpec,
    DeclarationEntry,
    EndpointMetadata,
    EndpointSpec,
    RequestSpec,
    ResponseSpec,
)
from gimbal_plate.systems.platform.system_info import (
    PLATFORM_DEFAULT_OWNER,
    PLATFORM_DEFAULT_TAGS,
    PLATFORM_DEFAULT_VERSION,
    PLATFORM_SERVICE,
    PLATFORM_SYSTEM,
)

CATALOG_GET_SERVICES: Final[EndpointSpec] = EndpointSpec(
    id="platform.catalog.get_services",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Get Catalog Services",
    description="服务目录聚合(30s TTL 缓存)。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/catalog/services",
        auth="bearer",
        timeout_seconds=30.0,
    ),
    request=RequestSpec(
        body_type="none",
        declarations=[]
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="Successful Response",
            declarations=[
                DeclarationEntry(name="endpoints", path="$.endpoints", type="array",
                                  ui_kind="json", required=True, assertable=True, children=[
                                     DeclarationEntry(name="id", path="$.endpoints.id",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="service",
                                                       path="$.endpoints.service",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                 ]
                ),
                DeclarationEntry(name="plateReachable", path="$.plateReachable",
                                  type="boolean", ui_kind="boolean", assertable=True),
                DeclarationEntry(name="services", path="$.services", type="array",
                                  ui_kind="json", required=True, assertable=True, children=[
                                     DeclarationEntry(name="endpointCount",
                                                       path="$.services.endpointCount",
                                                       type="integer", ui_kind="number",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="name", path="$.services.name",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="system",
                                                       path="$.services.system",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                 ]
                ),
            ]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="catalog",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
