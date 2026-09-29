"""platform.notifications.put_preferences —— Put Prefs

`PUT /api/notifications/preferences`

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

NOTIFICATIONS_PUT_PREFERENCES: Final[EndpointSpec] = EndpointSpec(
    id="platform.notifications.put_preferences",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Put Prefs",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="PUT",
        path="/api/notifications/preferences",
        auth="bearer",
        timeout_seconds=30.0,
    ),
    request=RequestSpec(
        body_type="json",
        declarations=[
            DeclarationEntry(name="off", path="$.off", type="array", ui_kind="json"),
        ]
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="Successful Response",
            declarations=[
                DeclarationEntry(name="off", path="$.off", type="array", ui_kind="json",
                                  required=True, assertable=True),
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
