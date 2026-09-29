"""platform.users.get_root —— List Users

`GET /api/users`

List every user(M2.5 收紧:operator+ 可见;原「任何登录用户全量
可见」的 spec-1 遗留闭合 —— 权限方案 §5.3)。M4(§6.3):q
(username/display_name 子串)+ role 精确 + Page 信封。

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

USERS_GET_ROOT: Final[EndpointSpec] = EndpointSpec(
    id="platform.users.get_root",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="List Users",
    description="List every user(M2.5 收紧:operator+ 可见;原「任何登录用户全量\n可见」的 spec-1 遗留闭合 —— 权限方案 §5.3)。M4(§6.3):q\n(username/display_name 子串)+ role 精确 + Page 信封。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/users",
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
                DeclarationEntry(name="items", path="$.items", type="array", ui_kind="json",
                                  required=True, assertable=True, children=[
                                     DeclarationEntry(name="created_at",
                                                       path="$.items.created_at",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="display_name",
                                                       path="$.items.display_name",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="id", path="$.items.id",
                                                       type="integer", ui_kind="number",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="is_active",
                                                       path="$.items.is_active",
                                                       type="boolean", ui_kind="boolean",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="is_admin",
                                                       path="$.items.is_admin",
                                                       type="boolean", ui_kind="boolean",
                                                       assertable=True),
                                     DeclarationEntry(name="role", path="$.items.role",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="updated_at",
                                                       path="$.items.updated_at",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="username",
                                                       path="$.items.username",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                 ]
                ),
                DeclarationEntry(name="page", path="$.page", type="integer",
                                  ui_kind="number", assertable=True),
                DeclarationEntry(name="pageSize", path="$.pageSize", type="integer",
                                  ui_kind="number", assertable=True),
                DeclarationEntry(name="total", path="$.total", type="integer",
                                  ui_kind="number", assertable=True),
            ]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="users",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
