"""platform.auth.post_register —— Register

`POST /api/auth/register`

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

_RESPONSE_DECLS: Final[list[DeclarationEntry]] = [
    DeclarationEntry(name="access_token", path="$.access_token", type="string",
                      ui_kind="text", required=True, assertable=True),
    DeclarationEntry(name="refresh_token", path="$.refresh_token", type="string",
                      ui_kind="text", required=True, assertable=True),
    DeclarationEntry(name="token_type", path="$.token_type", type="string", ui_kind="text",
                      assertable=True),
    DeclarationEntry(name="user", path="$.user", type="object", ui_kind="json",
                      required=True,
                      description="Public-facing user view. ``created_at`` is serialized to ISO 8601 string.",
                      assertable=True, children=[
                         DeclarationEntry(name="created_at", path="$.user.created_at",
                                           type="string", ui_kind="text", required=True,
                                           assertable=True),
                         DeclarationEntry(name="display_name", path="$.user.display_name",
                                           type="string", ui_kind="text", required=True,
                                           assertable=True),
                         DeclarationEntry(name="id", path="$.user.id", type="integer",
                                           ui_kind="number", required=True, assertable=True),
                         DeclarationEntry(name="is_active", path="$.user.is_active",
                                           type="boolean", ui_kind="boolean", required=True,
                                           assertable=True),
                         DeclarationEntry(name="is_admin", path="$.user.is_admin",
                                           type="boolean", ui_kind="boolean",
                                           assertable=True),
                         DeclarationEntry(name="role", path="$.user.role", type="string",
                                           ui_kind="text", assertable=True),
                         DeclarationEntry(name="updated_at", path="$.user.updated_at",
                                           type="string", ui_kind="text", assertable=True),
                         DeclarationEntry(name="username", path="$.user.username",
                                           type="string", ui_kind="text", required=True,
                                           assertable=True),
                     ]
    ),
]

AUTH_POST_REGISTER: Final[EndpointSpec] = EndpointSpec(
    id="platform.auth.post_register",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Register",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="POST",
        path="/api/auth/register",
        timeout_seconds=30.0,
    ),
    request=RequestSpec(
        body_type="json",
        declarations=[
            DeclarationEntry(name="display_name", path="$.display_name", type="string",
                              ui_kind="text"),
            DeclarationEntry(name="password", path="$.password", type="string",
                              ui_kind="text", required=True),
            DeclarationEntry(name="username", path="$.username", type="string",
                              ui_kind="text", required=True),
        ]
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="成功",
            declarations=_RESPONSE_DECLS,
        ),
        201: ResponseSpec(
            status=201,
            description="Successful Response",
            declarations=_RESPONSE_DECLS,
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="auth",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
        business_notes="responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）",
    ),
)
