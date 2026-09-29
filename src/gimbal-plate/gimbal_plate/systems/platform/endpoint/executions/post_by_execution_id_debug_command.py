"""platform.executions.post_by_execution_id_debug_command —— Debug Session Command

`POST /api/executions/{execution_id}/debug/command`

代理结构化调试命令（N6：与引擎 DebugCommand 同形）。

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

EXECUTIONS_POST_BY_EXECUTION_ID_DEBUG_COMMAND: Final[EndpointSpec] = EndpointSpec(
    id="platform.executions.post_by_execution_id_debug_command",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Debug Session Command",
    description="代理结构化调试命令（N6：与引擎 DebugCommand 同形）。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="POST",
        path="/api/executions/{execution_id}/debug/command",
        auth="bearer",
        timeout_seconds=30.0,
    ),
    request=RequestSpec(
        body_type="json",
        declarations=[
            DeclarationEntry(name="kind", path="$.kind", type="string", ui_kind="text",
                              required=True),
            DeclarationEntry(name="path", path="$.path", type="string", ui_kind="text"),
            DeclarationEntry(name="value", path="$.value", type="string", ui_kind="text"),
            DeclarationEntry(name="variable", path="$.variable", type="string",
                              ui_kind="text"),
        ]
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="Successful Response",
            declarations=[
                DeclarationEntry(name="accepted", path="$.accepted", type="boolean",
                                  ui_kind="boolean", required=True, assertable=True),
                DeclarationEntry(name="output", path="$.output", type="array",
                                  ui_kind="json", assertable=True),
            ]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="executions",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
