"""platform.users.get_roster —— Get Roster

`GET /api/users/roster`

分发对话框的成员选择器:CurrentUser 可调(分发是 member 级能力,
现有 GET /users 是 operator+ 且带管理字段,不能降级复用)。

仅 ``is_active`` 用户、排除自己;User 表无 email 列,不为选人器
加列 —— ``display_name (username)`` 对内部平台足够定位人。
不分页、上限 200,前端本地过滤(团队规模下比搜索接口省事)。

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

USERS_GET_ROSTER: Final[EndpointSpec] = EndpointSpec(
    id="platform.users.get_roster",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Get Roster",
    description="分发对话框的成员选择器:CurrentUser 可调(分发是 member 级能力,\n现有 GET /users 是 operator+ 且带管理字段,不能降级复用)。\n\n仅 ``is_active`` 用户、排除自己;User 表无 email 列,不为选人器\n加列 —— ``display_name (username)`` 对内部平台足够定位人。\n不分页、上限 200,前端本地过滤(团队规模下比搜索接口省事)。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/users/roster",
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
        module="users",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
