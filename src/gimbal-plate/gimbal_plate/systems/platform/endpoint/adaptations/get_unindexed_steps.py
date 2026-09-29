"""platform.adaptations.get_unindexed_steps —— Unindexed Steps

`GET /api/adaptations/unindexed-steps`

C10:缺 endpoint_id 的步骤清单(只读警示,不产生任何写)。

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

ADAPTATIONS_GET_UNINDEXED_STEPS: Final[EndpointSpec] = EndpointSpec(
    id="platform.adaptations.get_unindexed_steps",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Unindexed Steps",
    description="C10:缺 endpoint_id 的步骤清单(只读警示,不产生任何写)。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/adaptations/unindexed-steps",
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
                DeclarationEntry(name="reason", path="$.reason", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="scenarioId", path="$.scenarioId", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="stepIndex", path="$.stepIndex", type="integer",
                                  ui_kind="number", required=True, assertable=True),
            ]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="adaptations",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
