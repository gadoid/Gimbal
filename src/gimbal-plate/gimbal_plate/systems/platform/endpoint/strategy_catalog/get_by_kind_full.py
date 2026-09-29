"""platform.strategy_catalog.get_by_kind_full —— Get Strategy Kind Full

`GET /api/strategy-catalog/{kind}/full`

Proxy ``GET {plate}/api/strategy/{kind}/full`` and unwrap ``data.item``.

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

STRATEGY_CATALOG_GET_BY_KIND_FULL: Final[EndpointSpec] = EndpointSpec(
    id="platform.strategy_catalog.get_by_kind_full",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Get Strategy Kind Full",
    description="Proxy ``GET {plate}/api/strategy/{kind}/full`` and unwrap ``data.item``.",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/strategy-catalog/{kind}/full",
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
            declarations=[]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="strategy-catalog",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
