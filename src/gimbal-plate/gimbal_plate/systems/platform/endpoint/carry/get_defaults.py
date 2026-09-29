"""platform.carry.get_defaults —— Get Defaults

`GET /api/carry/defaults`

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

CARRY_GET_DEFAULTS: Final[EndpointSpec] = EndpointSpec(
    id="platform.carry.get_defaults",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Get Defaults",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/carry/defaults",
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
                DeclarationEntry(name="defaults", path="$.defaults", type="object",
                                  ui_kind="json", assertable=True),
            ]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="carry",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
