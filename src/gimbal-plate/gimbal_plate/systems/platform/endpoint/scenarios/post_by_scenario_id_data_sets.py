"""platform.scenarios.post_by_scenario_id_data_sets —— Create Data Set

`POST /api/scenarios/{scenario_id}/data-sets`

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

_RESPONSE_DECLS: Final[list[DeclarationEntry]] = [
    DeclarationEntry(name="datasetId", path="$.datasetId", type="string", ui_kind="text",
                      required=True, assertable=True),
    DeclarationEntry(name="description", path="$.description", type="string",
                      ui_kind="text", assertable=True),
    DeclarationEntry(name="name", path="$.name", type="string", ui_kind="text",
                      required=True, assertable=True),
    DeclarationEntry(name="rowCount", path="$.rowCount", type="integer", ui_kind="number",
                      assertable=True),
    DeclarationEntry(name="rows", path="$.rows", type="array", ui_kind="json",
                      assertable=True),
    DeclarationEntry(name="scenarioId", path="$.scenarioId", type="string", ui_kind="text",
                      required=True, assertable=True),
    DeclarationEntry(name="varUnlocks", path="$.varUnlocks", type="array", ui_kind="json",
                      assertable=True),
]

SCENARIOS_POST_BY_SCENARIO_ID_DATA_SETS: Final[EndpointSpec] = EndpointSpec(
    id="platform.scenarios.post_by_scenario_id_data_sets",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Create Data Set",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="POST",
        path="/api/scenarios/{scenario_id}/data-sets",
        auth="bearer",
        timeout_seconds=30.0,
    ),
    request=RequestSpec(
        body_type="json",
        declarations=[
            DeclarationEntry(name="description", path="$.description", type="string",
                              ui_kind="text"),
            DeclarationEntry(name="name", path="$.name", type="string", ui_kind="text",
                              required=True),
            DeclarationEntry(name="rows", path="$.rows", type="array", ui_kind="json"),
            DeclarationEntry(name="varUnlocks", path="$.varUnlocks", type="array",
                              ui_kind="json"),
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
        module="scenarios",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
        business_notes="responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）",
    ),
)
