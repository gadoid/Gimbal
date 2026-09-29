"""platform.executions.get_by_execution_id —— Get Execution

`GET /api/executions/{execution_id}`

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

EXECUTIONS_GET_BY_EXECUTION_ID: Final[EndpointSpec] = EndpointSpec(
    id="platform.executions.get_by_execution_id",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Get Execution",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/executions/{execution_id}",
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
                DeclarationEntry(name="batch_id", path="$.batch_id", type="string",
                                  ui_kind="text", assertable=True),
                DeclarationEntry(name="config", path="$.config", type="object",
                                  ui_kind="json", required=True, assertable=True),
                DeclarationEntry(name="consecutive_failures", path="$.consecutive_failures",
                                  type="integer", ui_kind="number", assertable=True),
                DeclarationEntry(name="failed", path="$.failed", type="integer",
                                  ui_kind="number", required=True, assertable=True),
                DeclarationEntry(name="finished_at", path="$.finished_at", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="has_scenario_snapshot",
                                  path="$.has_scenario_snapshot", type="boolean",
                                  ui_kind="boolean", assertable=True),
                DeclarationEntry(name="id", path="$.id", type="integer", ui_kind="number",
                                  required=True, assertable=True),
                DeclarationEntry(name="ownerName", path="$.ownerName", type="string",
                                  ui_kind="text", assertable=True),
                DeclarationEntry(name="passed", path="$.passed", type="integer",
                                  ui_kind="number", required=True, assertable=True),
                DeclarationEntry(name="scenario_deleted", path="$.scenario_deleted",
                                  type="boolean", ui_kind="boolean", assertable=True),
                DeclarationEntry(name="scenario_display_name",
                                  path="$.scenario_display_name", type="string",
                                  ui_kind="text", assertable=True),
                DeclarationEntry(name="scenario_id", path="$.scenario_id", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="skipped", path="$.skipped", type="integer",
                                  ui_kind="number", assertable=True),
                DeclarationEntry(name="started_at", path="$.started_at", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="status", path="$.status", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="total_runs", path="$.total_runs", type="integer",
                                  ui_kind="number", required=True, assertable=True),
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
