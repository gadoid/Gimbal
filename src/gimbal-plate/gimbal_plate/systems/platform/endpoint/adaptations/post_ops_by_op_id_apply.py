"""platform.adaptations.post_ops_by_op_id_apply —— Apply Op

`POST /api/adaptations/ops/{op_id}/apply`

逐条应用:幂等重放 / C5 冲突标 conflict / 末条完成推戳。

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

ADAPTATIONS_POST_OPS_BY_OP_ID_APPLY: Final[EndpointSpec] = EndpointSpec(
    id="platform.adaptations.post_ops_by_op_id_apply",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Apply Op",
    description="逐条应用:幂等重放 / C5 冲突标 conflict / 末条完成推戳。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="POST",
        path="/api/adaptations/ops/{op_id}/apply",
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
                DeclarationEntry(name="appliedAt", path="$.appliedAt", type="string",
                                  ui_kind="text", assertable=True),
                DeclarationEntry(name="batchId", path="$.batchId", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="datasetId", path="$.datasetId", type="string",
                                  ui_kind="text", assertable=True),
                DeclarationEntry(name="datasetName", path="$.datasetName", type="string",
                                  ui_kind="text", assertable=True),
                DeclarationEntry(name="id", path="$.id", type="integer", ui_kind="number",
                                  required=True, assertable=True),
                DeclarationEntry(name="note", path="$.note", type="string", ui_kind="text",
                                  assertable=True),
                DeclarationEntry(name="opType", path="$.opType", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="payload", path="$.payload", type="object",
                                  ui_kind="json", assertable=True),
                DeclarationEntry(name="scenarioDisplayName", path="$.scenarioDisplayName",
                                  type="string", ui_kind="text", assertable=True),
                DeclarationEntry(name="scenarioId", path="$.scenarioId", type="string",
                                  ui_kind="text", assertable=True),
                DeclarationEntry(name="status", path="$.status", type="string",
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
