"""platform.executions.get_by_execution_id_case_artifact —— Get Case Artifact

`GET /api/executions/{execution_id}/case-artifact`

白名单工件:engine.log(引擎日志)/ result.json(步骤级明细)。
case.json 刻意不暴露 — 含明文凭证,无前端消费场景。Task 13 前端消费。

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

EXECUTIONS_GET_BY_EXECUTION_ID_CASE_ARTIFACT: Final[EndpointSpec] = EndpointSpec(
    id="platform.executions.get_by_execution_id_case_artifact",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Get Case Artifact",
    description="白名单工件:engine.log(引擎日志)/ result.json(步骤级明细)。\ncase.json 刻意不暴露 — 含明文凭证,无前端消费场景。Task 13 前端消费。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/executions/{execution_id}/case-artifact",
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
