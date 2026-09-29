"""platform.executions.post_by_execution_id_rerun —— Rerun Execution

`POST /api/executions/{execution_id}/rerun`

按 ``config_json`` 里的完整配方重建一次发起(设计 §3.4:配方已存,
重建即可)。语义与 ``POST /api/runs`` 完全同链(dispatch_run):同样过
owner 闸、总量闸、数据集存在性 — 场景已删 / 数据集已删 / 方案参数
越界分别 404/409,与新鲜发起一致。

重跑是**新的一次独立发起**:不带原单批次键(原批归并视图不被新单
混入),也不带 judgeDegraded 等上次运行的审计标记(那些描述上一次,
不描述这一次)。注入条目 id 随配方一并重放(dispatch 侧悬空 skip 兜
底 — 上次以后条目被删的重跑会少注入,JSONL/告警可见)。

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
    DeclarationEntry(name="executionId", path="$.executionId", type="integer",
                      ui_kind="number", required=True, assertable=True),
    DeclarationEntry(name="runId", path="$.runId", type="string", ui_kind="text",
                      required=True, assertable=True),
]

EXECUTIONS_POST_BY_EXECUTION_ID_RERUN: Final[EndpointSpec] = EndpointSpec(
    id="platform.executions.post_by_execution_id_rerun",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Rerun Execution",
    description="按 ``config_json`` 里的完整配方重建一次发起(设计 §3.4:配方已存,\n重建即可)。语义与 ``POST /api/runs`` 完全同链(dispatch_run):同样过\nowner 闸、总量闸、数据集存在性 — 场景已删 / 数据集已删 / 方案参数\n越界分别 404/409,与新鲜发起一致。\n\n重跑是**新的一次独立发起**:不带原单批次键(原批归并视图不被新单\n混入),也不带 judgeDegraded 等上次运行的审计标记(那些描述上一次,\n不描述这一次)。注入条目 id 随配方一并重放(dispatch 侧悬空 skip 兜\n底 — 上次以后条目被删的重跑会少注入,JSONL/告警可见)。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="POST",
        path="/api/executions/{execution_id}/rerun",
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
        module="executions",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
        business_notes="responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）",
    ),
)
