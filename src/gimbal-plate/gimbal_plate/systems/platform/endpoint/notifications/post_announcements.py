"""platform.notifications.post_announcements —— Post Announcement

`POST /api/notifications/announcements`

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

_RESPONSE_DECLS: Final[list[DeclarationEntry]] = []

NOTIFICATIONS_POST_ANNOUNCEMENTS: Final[EndpointSpec] = EndpointSpec(
    id="platform.notifications.post_announcements",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Post Announcement",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="POST",
        path="/api/notifications/announcements",
        auth="bearer",
        timeout_seconds=30.0,
    ),
    request=RequestSpec(
        body_type="json",
        declarations=[
            DeclarationEntry(name="body", path="$.body", type="string", ui_kind="text"),
            DeclarationEntry(name="hours", path="$.hours", type="integer", ui_kind="number",
                              description="有效小时数;0 = 永不过期"),
            DeclarationEntry(name="title", path="$.title", type="string", ui_kind="text",
                              required=True),
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
        module="notifications",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
        business_notes="responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）",
    ),
)
