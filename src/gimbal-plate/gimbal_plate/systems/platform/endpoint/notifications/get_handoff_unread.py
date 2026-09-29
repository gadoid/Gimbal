"""platform.notifications.get_handoff_unread —— Handoff Unread

`GET /api/notifications/handoff-unread`

未读分享列表(F1 悬浮标签数据源):场景行渲染 O(1) 查 Set 用。

查询走 0005 已建的 (user_id, id) 索引,量级足够(方案 §1.4)。

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

NOTIFICATIONS_GET_HANDOFF_UNREAD: Final[EndpointSpec] = EndpointSpec(
    id="platform.notifications.get_handoff_unread",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Handoff Unread",
    description="未读分享列表(F1 悬浮标签数据源):场景行渲染 O(1) 查 Set 用。\n\n查询走 0005 已建的 (user_id, id) 索引,量级足够(方案 §1.4)。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/notifications/handoff-unread",
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
                                  assertable=True, children=[
                                     DeclarationEntry(name="id", path="$.items.id",
                                                       type="integer", ui_kind="number",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="resourceId",
                                                       path="$.items.resourceId",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="senderName",
                                                       path="$.items.senderName",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                 ]
                ),
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
