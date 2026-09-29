"""platform.adaptations.post_batches_by_batch_id_rollback —— Rollback Batch

`POST /api/adaptations/batches/{batch_id}/rollback`

整批回滚:before+重放乐观比对,冲突实体跳过不盲写。

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

ADAPTATIONS_POST_BATCHES_BY_BATCH_ID_ROLLBACK: Final[EndpointSpec] = EndpointSpec(
    id="platform.adaptations.post_batches_by_batch_id_rollback",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Rollback Batch",
    description="整批回滚:before+重放乐观比对,冲突实体跳过不盲写。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="POST",
        path="/api/adaptations/batches/{batch_id}/rollback",
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
                DeclarationEntry(name="conflicts", path="$.conflicts", type="array",
                                  ui_kind="json", assertable=True, children=[
                                     DeclarationEntry(name="entityId",
                                                       path="$.conflicts.entityId",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="entityType",
                                                       path="$.conflicts.entityType",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="note", path="$.conflicts.note",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                 ]
                ),
                DeclarationEntry(name="restored", path="$.restored", type="array",
                                  ui_kind="json", assertable=True, children=[
                                     DeclarationEntry(name="entityId",
                                                       path="$.restored.entityId",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="entityType",
                                                       path="$.restored.entityType",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                 ]
                ),
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
