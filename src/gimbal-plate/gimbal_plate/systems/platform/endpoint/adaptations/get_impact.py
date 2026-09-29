"""platform.adaptations.get_impact —— Impact

`GET /api/adaptations/impact`

endpoint(可选 field)→ 受影响清单(直填/模板、数据集列标注)。

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

ADAPTATIONS_GET_IMPACT: Final[EndpointSpec] = EndpointSpec(
    id="platform.adaptations.get_impact",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Impact",
    description="endpoint(可选 field)→ 受影响清单(直填/模板、数据集列标注)。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/adaptations/impact",
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
                DeclarationEntry(name="datasetColumn", path="$.datasetColumn",
                                  type="string", ui_kind="text", assertable=True),
                DeclarationEntry(name="datasetId", path="$.datasetId", type="string",
                                  ui_kind="text", assertable=True),
                DeclarationEntry(name="field", path="$.field", type="string",
                                  ui_kind="text", assertable=True),
                DeclarationEntry(name="scenarioId", path="$.scenarioId", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="source", path="$.source", type="string",
                                  ui_kind="text", assertable=True),
                DeclarationEntry(name="stepIndex", path="$.stepIndex", type="integer",
                                  ui_kind="number", required=True, assertable=True),
                DeclarationEntry(name="viaVar", path="$.viaVar", type="string",
                                  ui_kind="text", assertable=True),
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
