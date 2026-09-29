"""platform.users.post_root —— Create User

`POST /api/users`

Create a new user(M2.5 收紧:admin 开号 —— 创建账号是人事权,
spec-1「任何登录用户可开号」的遗留闭合,权限方案 §5.3)。

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
    DeclarationEntry(name="created_at", path="$.created_at", type="string", ui_kind="text",
                      required=True, assertable=True),
    DeclarationEntry(name="display_name", path="$.display_name", type="string",
                      ui_kind="text", required=True, assertable=True),
    DeclarationEntry(name="id", path="$.id", type="integer", ui_kind="number",
                      required=True, assertable=True),
    DeclarationEntry(name="is_active", path="$.is_active", type="boolean",
                      ui_kind="boolean", required=True, assertable=True),
    DeclarationEntry(name="is_admin", path="$.is_admin", type="boolean", ui_kind="boolean",
                      assertable=True),
    DeclarationEntry(name="role", path="$.role", type="string", ui_kind="text",
                      assertable=True),
    DeclarationEntry(name="updated_at", path="$.updated_at", type="string", ui_kind="text",
                      assertable=True),
    DeclarationEntry(name="username", path="$.username", type="string", ui_kind="text",
                      required=True, assertable=True),
]

USERS_POST_ROOT: Final[EndpointSpec] = EndpointSpec(
    id="platform.users.post_root",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Create User",
    description="Create a new user(M2.5 收紧:admin 开号 —— 创建账号是人事权,\nspec-1「任何登录用户可开号」的遗留闭合,权限方案 §5.3)。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="POST",
        path="/api/users",
        auth="bearer",
        timeout_seconds=30.0,
    ),
    request=RequestSpec(
        body_type="json",
        declarations=[
            DeclarationEntry(name="display_name", path="$.display_name", type="string",
                              ui_kind="text"),
            DeclarationEntry(name="password", path="$.password", type="string",
                              ui_kind="text", required=True),
            DeclarationEntry(name="role", path="$.role", type="string", ui_kind="text"),
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
        module="users",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
        business_notes="responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）",
    ),
)
