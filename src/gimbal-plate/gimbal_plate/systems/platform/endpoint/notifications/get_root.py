"""platform.notifications.get_root —— List Notifications

`GET /api/notifications`

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

NOTIFICATIONS_GET_ROOT: Final[EndpointSpec] = EndpointSpec(
    id="platform.notifications.get_root",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="List Notifications",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/notifications",
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
                                     DeclarationEntry(name="batchId",
                                                       path="$.items.batchId",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="body", path="$.items.body",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="created_at",
                                                       path="$.items.created_at",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="id", path="$.items.id",
                                                       type="integer", ui_kind="number",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="link", path="$.items.link",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="readAt", path="$.items.readAt",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="title", path="$.items.title",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="type", path="$.items.type",
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
                DeclarationEntry(name="unread", path="$.unread", type="integer",
                                  ui_kind="number", required=True, assertable=True),
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
