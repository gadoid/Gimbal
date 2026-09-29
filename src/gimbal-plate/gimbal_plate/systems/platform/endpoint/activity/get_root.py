"""platform.activity.get_root —— Get Activity

`GET /api/activity`

本人活动轴:我的执行 + 我的私有场景改动 + 触碰我场景的适配批次,
按 at 倒序合并,截 ``limit``。

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

ACTIVITY_GET_ROOT: Final[EndpointSpec] = EndpointSpec(
    id="platform.activity.get_root",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Get Activity",
    description="本人活动轴:我的执行 + 我的私有场景改动 + 触碰我场景的适配批次,\n按 at 倒序合并,截 ``limit``。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/activity",
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
                DeclarationEntry(name="events", path="$.events", type="array",
                                  ui_kind="json", assertable=True, children=[
                                     DeclarationEntry(name="action", path="$.events.action",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="at", path="$.events.at",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="batchId",
                                                       path="$.events.batchId",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="detail", path="$.events.detail",
                                                       type="object", ui_kind="json",
                                                       assertable=True),
                                     DeclarationEntry(name="endpointId",
                                                       path="$.events.endpointId",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="executionId",
                                                       path="$.events.executionId",
                                                       type="integer", ui_kind="number",
                                                       assertable=True),
                                     DeclarationEntry(name="fromVersion",
                                                       path="$.events.fromVersion",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="kind", path="$.events.kind",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="module", path="$.events.module",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="name", path="$.events.name",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="opCount",
                                                       path="$.events.opCount",
                                                       type="integer", ui_kind="number",
                                                       assertable=True),
                                     DeclarationEntry(name="scenarioId",
                                                       path="$.events.scenarioId",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="status", path="$.events.status",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="toVersion",
                                                       path="$.events.toVersion",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                 ]
                ),
                DeclarationEntry(name="sources", path="$.sources", type="object",
                                  ui_kind="json", assertable=True),
            ]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="activity",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
