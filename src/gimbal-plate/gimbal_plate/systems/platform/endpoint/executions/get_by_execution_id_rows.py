"""platform.executions.get_by_execution_id_rows —— Get Execution Rows

`GET /api/executions/{execution_id}/rows`

行级状态(M6 转正,债 5 消除):活跃执行读 dispatcher 内存
registry;历史执行读 execution_rows DB 分页;M6 前的存量单回放
JSONL(只读归档)兜底。信封 {items,total,page,pageSize}。

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

EXECUTIONS_GET_BY_EXECUTION_ID_ROWS: Final[EndpointSpec] = EndpointSpec(
    id="platform.executions.get_by_execution_id_rows",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Get Execution Rows",
    description="行级状态(M6 转正,债 5 消除):活跃执行读 dispatcher 内存\nregistry;历史执行读 execution_rows DB 分页;M6 前的存量单回放\nJSONL(只读归档)兜底。信封 {items,total,page,pageSize}。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/executions/{execution_id}/rows",
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
                DeclarationEntry(name="items", path="$.items", type="array", ui_kind="json",
                                  required=True, assertable=True, children=[
                                     DeclarationEntry(name="caseDir",
                                                       path="$.items.caseDir",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="datasetId",
                                                       path="$.items.datasetId",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="datasetName",
                                                       path="$.items.datasetName",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="finishedAt",
                                                       path="$.items.finishedAt",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="injectionId",
                                                       path="$.items.injectionId",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="rep", path="$.items.rep",
                                                       type="integer", ui_kind="number",
                                                       assertable=True),
                                     DeclarationEntry(name="rowIndex",
                                                       path="$.items.rowIndex",
                                                       type="integer", ui_kind="number",
                                                       assertable=True),
                                     DeclarationEntry(name="seq", path="$.items.seq",
                                                       type="integer", ui_kind="number",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="startedAt",
                                                       path="$.items.startedAt",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="status", path="$.items.status",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                 ]
                ),
                DeclarationEntry(name="page", path="$.page", type="integer",
                                  ui_kind="number", assertable=True),
                DeclarationEntry(name="pageSize", path="$.pageSize", type="integer",
                                  ui_kind="number", assertable=True),
                DeclarationEntry(name="total", path="$.total", type="integer",
                                  ui_kind="number", assertable=True),
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
