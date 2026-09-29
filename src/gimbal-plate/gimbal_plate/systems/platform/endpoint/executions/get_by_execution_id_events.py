"""platform.executions.get_by_execution_id_events —— Get Execution Events

`GET /api/executions/{execution_id}/events`

事件/日志组合筛选查询(P2-07/C10 日志分析页的读面)。

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

EXECUTIONS_GET_BY_EXECUTION_ID_EVENTS: Final[EndpointSpec] = EndpointSpec(
    id="platform.executions.get_by_execution_id_events",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Get Execution Events",
    description="事件/日志组合筛选查询(P2-07/C10 日志分析页的读面)。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/executions/{execution_id}/events",
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
            declarations=[]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="executions",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
