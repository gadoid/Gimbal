"""platform.scenarios.post_by_scenario_id_run_schemes —— Create Run Scheme

`POST /api/scenarios/{scenario_id}/run-schemes`

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

SCENARIOS_POST_BY_SCENARIO_ID_RUN_SCHEMES: Final[EndpointSpec] = EndpointSpec(
    id="platform.scenarios.post_by_scenario_id_run_schemes",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Create Run Scheme",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="POST",
        path="/api/scenarios/{scenario_id}/run-schemes",
        auth="bearer",
        timeout_seconds=30.0,
    ),
    request=RequestSpec(
        body_type="json",
        declarations=[
            DeclarationEntry(name="dataSetIds", path="$.dataSetIds", type="array",
                              ui_kind="json"),
            DeclarationEntry(name="dataSetSelection", path="$.dataSetSelection",
                              type="array", ui_kind="json", children=[
                                 DeclarationEntry(name="datasetId",
                                                   path="$.dataSetSelection.datasetId",
                                                   type="string", ui_kind="text",
                                                   required=True),
                                 DeclarationEntry(name="rowIndexes",
                                                   path="$.dataSetSelection.rowIndexes",
                                                   type="array", ui_kind="json"),
                             ]
            ),
            DeclarationEntry(name="injectionEntryIds", path="$.injectionEntryIds",
                              type="array", ui_kind="json"),
            DeclarationEntry(name="isDefault", path="$.isDefault", type="boolean",
                              ui_kind="boolean"),
            DeclarationEntry(name="logSub", path="$.logSub", type="string", ui_kind="text"),
            DeclarationEntry(name="nRuns", path="$.nRuns", type="integer", ui_kind="number"),
            DeclarationEntry(name="name", path="$.name", type="string", ui_kind="text",
                              required=True),
            DeclarationEntry(name="parallel", path="$.parallel", type="integer",
                              ui_kind="number"),
            DeclarationEntry(name="plugins", path="$.plugins", type="string", ui_kind="text"),
            DeclarationEntry(name="serviceBindings", path="$.serviceBindings",
                              type="object", ui_kind="json"),
            DeclarationEntry(name="stepTo", path="$.stepTo", type="integer",
                              ui_kind="number"),
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
