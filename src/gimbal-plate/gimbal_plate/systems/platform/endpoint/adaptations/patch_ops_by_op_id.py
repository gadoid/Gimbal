"""platform.adaptations.patch_ops_by_op_id —— Patch Op

`PATCH /api/adaptations/ops/{op_id}`

仅 pending 可整包替换 payload(mapValue 骨架补值 / 参数修正)。

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

ADAPTATIONS_PATCH_OPS_BY_OP_ID: Final[EndpointSpec] = EndpointSpec(
    id="platform.adaptations.patch_ops_by_op_id",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Patch Op",
    description="仅 pending 可整包替换 payload(mapValue 骨架补值 / 参数修正)。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="PATCH",
        path="/api/adaptations/ops/{op_id}",
        auth="bearer",
        timeout_seconds=30.0,
    ),
    request=RequestSpec(
        body_type="json",
        declarations=[
            DeclarationEntry(name="payload", path="$.payload", type="object", ui_kind="json"),
        ]
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
