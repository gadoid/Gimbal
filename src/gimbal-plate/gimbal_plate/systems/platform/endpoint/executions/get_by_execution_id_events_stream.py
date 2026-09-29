"""platform.executions.get_by_execution_id_events_stream —— Stream Execution Events

`GET /api/executions/{execution_id}/events/stream`

SSE 推送已入库事件(P2-06/C9;替代执行页 1s 轮询)。

* ``Last-Event-ID`` 请求头续传(断线重连不重复不丢失);
* 事件到达即推;无事件时 ~15s 心跳注释帧保活;
* 终态 + run.finished 已推(或终态但本就无事件流的存量执行)
  → 发 ``event: done`` 后关流;客户端断开即停。

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

EXECUTIONS_GET_BY_EXECUTION_ID_EVENTS_STREAM: Final[EndpointSpec] = EndpointSpec(
    id="platform.executions.get_by_execution_id_events_stream",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Stream Execution Events",
    description="SSE 推送已入库事件(P2-06/C9;替代执行页 1s 轮询)。\n\n* ``Last-Event-ID`` 请求头续传(断线重连不重复不丢失);\n* 事件到达即推;无事件时 ~15s 心跳注释帧保活;\n* 终态 + run.finished 已推(或终态但本就无事件流的存量执行)\n  → 发 ``event: done`` 后关流;客户端断开即停。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/executions/{execution_id}/events/stream",
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
        business_notes="responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）",
    ),
)
