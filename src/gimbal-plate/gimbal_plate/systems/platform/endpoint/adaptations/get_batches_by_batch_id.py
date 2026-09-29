"""platform.adaptations.get_batches_by_batch_id —— Get Batch

`GET /api/adaptations/batches/{batch_id}`

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

ADAPTATIONS_GET_BATCHES_BY_BATCH_ID: Final[EndpointSpec] = EndpointSpec(
    id="platform.adaptations.get_batches_by_batch_id",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Get Batch",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/adaptations/batches/{batch_id}",
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
                DeclarationEntry(name="batchId", path="$.batchId", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="closedAt", path="$.closedAt", type="string",
                                  ui_kind="text", assertable=True),
                DeclarationEntry(name="createdAt", path="$.createdAt", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="endpointId", path="$.endpointId", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="endpointMethod", path="$.endpointMethod",
                                  type="string", ui_kind="text", assertable=True),
                DeclarationEntry(name="endpointName", path="$.endpointName", type="string",
                                  ui_kind="text", assertable=True),
                DeclarationEntry(name="endpointPath", path="$.endpointPath", type="string",
                                  ui_kind="text", assertable=True),
                DeclarationEntry(name="fromVersion", path="$.fromVersion", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="opCounts", path="$.opCounts", type="object",
                                  ui_kind="json", assertable=True),
                DeclarationEntry(name="operatorId", path="$.operatorId", type="integer",
                                  ui_kind="number", required=True, assertable=True),
                DeclarationEntry(name="ops", path="$.ops", type="array", ui_kind="json",
                                  assertable=True, children=[
                                     DeclarationEntry(name="appliedAt",
                                                       path="$.ops.appliedAt",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="batchId", path="$.ops.batchId",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="datasetId",
                                                       path="$.ops.datasetId",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="datasetName",
                                                       path="$.ops.datasetName",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="id", path="$.ops.id",
                                                       type="integer", ui_kind="number",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="note", path="$.ops.note",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="opType", path="$.ops.opType",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="payload", path="$.ops.payload",
                                                       type="object", ui_kind="json",
                                                       assertable=True),
                                     DeclarationEntry(name="scenarioDisplayName",
                                                       path="$.ops.scenarioDisplayName",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="scenarioId",
                                                       path="$.ops.scenarioId",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="status", path="$.ops.status",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                 ]
                ),
                DeclarationEntry(name="snapshots", path="$.snapshots", type="array",
                                  ui_kind="json", assertable=True, children=[
                                     DeclarationEntry(name="entityId",
                                                       path="$.snapshots.entityId",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="entityType",
                                                       path="$.snapshots.entityType",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                 ]
                ),
                DeclarationEntry(name="status", path="$.status", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="toVersion", path="$.toVersion", type="string",
                                  ui_kind="text", required=True, assertable=True),
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
