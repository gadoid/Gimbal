"""platform.auths.post_by_auth_id_test —— Test Auth

`POST /api/auths/{auth_id}/test`

Dial the stored credential against ``url`` (probe service).

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

AUTHS_POST_BY_AUTH_ID_TEST: Final[EndpointSpec] = EndpointSpec(
    id="platform.auths.post_by_auth_id_test",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Test Auth",
    description="Dial the stored credential against ``url`` (probe service).",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="POST",
        path="/api/auths/{auth_id}/test",
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
                DeclarationEntry(name="message", path="$.message", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="ok", path="$.ok", type="boolean", ui_kind="boolean",
                                  required=True, assertable=True),
                DeclarationEntry(name="status_code", path="$.status_code", type="integer",
                                  ui_kind="number", assertable=True),
            ]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="auths",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
