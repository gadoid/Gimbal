"""platform.notifications.get_unread_count —— Unread Count

`GET /api/notifications/unread-count`

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

NOTIFICATIONS_GET_UNREAD_COUNT: Final[EndpointSpec] = EndpointSpec(
    id="platform.notifications.get_unread_count",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Unread Count",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/notifications/unread-count",
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
                DeclarationEntry(name="count", path="$.count", type="integer",
                                  ui_kind="number", required=True, assertable=True),
                DeclarationEntry(name="roleVersion", path="$.roleVersion", type="string",
                                  ui_kind="text", assertable=True),
            ]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="notifications",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
