"""platform.auths.get_by_auth_id —— Get Auth

`GET /api/auths/{auth_id}`

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

AUTHS_GET_BY_AUTH_ID: Final[EndpointSpec] = EndpointSpec(
    id="platform.auths.get_by_auth_id",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Get Auth",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/auths/{auth_id}",
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
                DeclarationEntry(name="alias", path="$.alias", type="string",
                                  ui_kind="text", assertable=True),
                DeclarationEntry(name="alias_ref_count", path="$.alias_ref_count",
                                  type="integer", ui_kind="number", assertable=True),
                DeclarationEntry(name="created_at", path="$.created_at", type="string",
                                  ui_kind="text", assertable=True),
                DeclarationEntry(name="expires_in", path="$.expires_in", type="integer",
                                  ui_kind="number", assertable=True),
                DeclarationEntry(name="id", path="$.id", type="integer", ui_kind="number",
                                  assertable=True),
                DeclarationEntry(name="password", path="$.password", type="string",
                                  ui_kind="text", assertable=True),
                DeclarationEntry(name="password_masked", path="$.password_masked",
                                  type="string", ui_kind="text", assertable=True),
                DeclarationEntry(name="scenario_ref_count", path="$.scenario_ref_count",
                                  type="integer", ui_kind="number", assertable=True),
                DeclarationEntry(name="token_type", path="$.token_type", type="string",
                                  ui_kind="text", assertable=True),
                DeclarationEntry(name="updated_at", path="$.updated_at", type="string",
                                  ui_kind="text", assertable=True),
                DeclarationEntry(name="url", path="$.url", type="string", ui_kind="text",
                                  assertable=True),
                DeclarationEntry(name="username", path="$.username", type="string",
                                  ui_kind="text", assertable=True),
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
