"""platform.adaptations.post_batches_by_batch_id_ops —— Create Op

`POST /api/adaptations/batches/{batch_id}/ops`

人工补 op(renameVar / 数据集 op —— 自动草案之外,§5.4)。

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
    DeclarationEntry(name="appliedAt", path="$.appliedAt", type="string", ui_kind="text",
                      assertable=True),
    DeclarationEntry(name="batchId", path="$.batchId", type="string", ui_kind="text",
                      required=True, assertable=True),
    DeclarationEntry(name="datasetId", path="$.datasetId", type="string", ui_kind="text",
                      assertable=True),
    DeclarationEntry(name="datasetName", path="$.datasetName", type="string",
                      ui_kind="text", assertable=True),
    DeclarationEntry(name="id", path="$.id", type="integer", ui_kind="number",
                      required=True, assertable=True),
    DeclarationEntry(name="note", path="$.note", type="string", ui_kind="text",
                      assertable=True),
    DeclarationEntry(name="opType", path="$.opType", type="string", ui_kind="text",
                      required=True, assertable=True),
    DeclarationEntry(name="payload", path="$.payload", type="object", ui_kind="json",
                      assertable=True),
    DeclarationEntry(name="scenarioDisplayName", path="$.scenarioDisplayName",
                      type="string", ui_kind="text", assertable=True),
    DeclarationEntry(name="scenarioId", path="$.scenarioId", type="string", ui_kind="text",
                      assertable=True),
    DeclarationEntry(name="status", path="$.status", type="string", ui_kind="text",
                      required=True, assertable=True),
]

ADAPTATIONS_POST_BATCHES_BY_BATCH_ID_OPS: Final[EndpointSpec] = EndpointSpec(
    id="platform.adaptations.post_batches_by_batch_id_ops",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Create Op",
    description="人工补 op(renameVar / 数据集 op —— 自动草案之外,§5.4)。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="POST",
        path="/api/adaptations/batches/{batch_id}/ops",
        auth="bearer",
        timeout_seconds=30.0,
    ),
    request=RequestSpec(
        body_type="json",
        declarations=[
            DeclarationEntry(name="datasetId", path="$.datasetId", type="string",
                              ui_kind="text"),
            DeclarationEntry(name="opType", path="$.opType", type="string", ui_kind="text",
                              required=True),
            DeclarationEntry(name="payload", path="$.payload", type="object", ui_kind="json"),
            DeclarationEntry(name="scenarioId", path="$.scenarioId", type="string",
                              ui_kind="text"),
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
