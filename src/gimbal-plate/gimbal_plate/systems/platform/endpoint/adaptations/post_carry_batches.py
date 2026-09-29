"""platform.adaptations.post_carry_batches —— Open Carry Batch

`POST /api/adaptations/carry-batches`

开 carry 值表批(漂移面板入口,spec §7);ops 经既有
POST /batches/{id}/ops,apply/rollback 走既有逐条/整批端点。

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
    DeclarationEntry(name="batchId", path="$.batchId", type="string", ui_kind="text",
                      required=True, assertable=True),
    DeclarationEntry(name="closedAt", path="$.closedAt", type="string", ui_kind="text",
                      assertable=True),
    DeclarationEntry(name="createdAt", path="$.createdAt", type="string", ui_kind="text",
                      required=True, assertable=True),
    DeclarationEntry(name="endpointId", path="$.endpointId", type="string", ui_kind="text",
                      required=True, assertable=True),
    DeclarationEntry(name="endpointMethod", path="$.endpointMethod", type="string",
                      ui_kind="text", assertable=True),
    DeclarationEntry(name="endpointName", path="$.endpointName", type="string",
                      ui_kind="text", assertable=True),
    DeclarationEntry(name="endpointPath", path="$.endpointPath", type="string",
                      ui_kind="text", assertable=True),
    DeclarationEntry(name="fromVersion", path="$.fromVersion", type="string",
                      ui_kind="text", required=True, assertable=True),
    DeclarationEntry(name="opCounts", path="$.opCounts", type="object", ui_kind="json",
                      assertable=True),
    DeclarationEntry(name="operatorId", path="$.operatorId", type="integer",
                      ui_kind="number", required=True, assertable=True),
    DeclarationEntry(name="ops", path="$.ops", type="array", ui_kind="json", assertable=True,
                     children=[
                         DeclarationEntry(name="appliedAt", path="$.ops.appliedAt",
                                           type="string", ui_kind="text", assertable=True),
                         DeclarationEntry(name="batchId", path="$.ops.batchId",
                                           type="string", ui_kind="text", required=True,
                                           assertable=True),
                         DeclarationEntry(name="datasetId", path="$.ops.datasetId",
                                           type="string", ui_kind="text", assertable=True),
                         DeclarationEntry(name="datasetName", path="$.ops.datasetName",
                                           type="string", ui_kind="text", assertable=True),
                         DeclarationEntry(name="id", path="$.ops.id", type="integer",
                                           ui_kind="number", required=True, assertable=True),
                         DeclarationEntry(name="note", path="$.ops.note", type="string",
                                           ui_kind="text", assertable=True),
                         DeclarationEntry(name="opType", path="$.ops.opType", type="string",
                                           ui_kind="text", required=True, assertable=True),
                         DeclarationEntry(name="payload", path="$.ops.payload",
                                           type="object", ui_kind="json", assertable=True),
                         DeclarationEntry(name="scenarioDisplayName",
                                           path="$.ops.scenarioDisplayName", type="string",
                                           ui_kind="text", assertable=True),
                         DeclarationEntry(name="scenarioId", path="$.ops.scenarioId",
                                           type="string", ui_kind="text", assertable=True),
                         DeclarationEntry(name="status", path="$.ops.status", type="string",
                                           ui_kind="text", required=True, assertable=True),
                     ]
    ),
    DeclarationEntry(name="snapshots", path="$.snapshots", type="array", ui_kind="json",
                      assertable=True, children=[
                         DeclarationEntry(name="entityId", path="$.snapshots.entityId",
                                           type="string", ui_kind="text", required=True,
                                           assertable=True),
                         DeclarationEntry(name="entityType", path="$.snapshots.entityType",
                                           type="string", ui_kind="text", required=True,
                                           assertable=True),
                     ]
    ),
    DeclarationEntry(name="status", path="$.status", type="string", ui_kind="text",
                      required=True, assertable=True),
    DeclarationEntry(name="toVersion", path="$.toVersion", type="string", ui_kind="text",
                      required=True, assertable=True),
]

ADAPTATIONS_POST_CARRY_BATCHES: Final[EndpointSpec] = EndpointSpec(
    id="platform.adaptations.post_carry_batches",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Open Carry Batch",
    description="开 carry 值表批(漂移面板入口,spec §7);ops 经既有\nPOST /batches/{id}/ops,apply/rollback 走既有逐条/整批端点。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="POST",
        path="/api/adaptations/carry-batches",
        auth="bearer",
        timeout_seconds=30.0,
    ),
    request=RequestSpec(
        body_type="json",
        declarations=[
            DeclarationEntry(name="service", path="$.service", type="string", ui_kind="text"),
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
        module="adaptations",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
        business_notes="responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）",
    ),
)
