"""platform.auth.get_me —— Me

`GET /api/auth/me`

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

AUTH_GET_ME: Final[EndpointSpec] = EndpointSpec(
    id="platform.auth.get_me",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Me",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/auth/me",
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
                DeclarationEntry(name="user", path="$.user", type="object", ui_kind="json",
                                  required=True,
                                  description="Public-facing user view. ``created_at`` is serialized to ISO 8601 string.",
                                  assertable=True, children=[
                                     DeclarationEntry(name="created_at",
                                                       path="$.user.created_at",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="display_name",
                                                       path="$.user.display_name",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="id", path="$.user.id",
                                                       type="integer", ui_kind="number",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="is_active",
                                                       path="$.user.is_active",
                                                       type="boolean", ui_kind="boolean",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="is_admin",
                                                       path="$.user.is_admin",
                                                       type="boolean", ui_kind="boolean",
                                                       assertable=True),
                                     DeclarationEntry(name="role", path="$.user.role",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="updated_at",
                                                       path="$.user.updated_at",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="username",
                                                       path="$.user.username",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                 ]
                ),
            ]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="auth",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
