"""platform.scenarios.delete_by_scenario_id_run_schemes_by_s_6a5300 —— Delete Run Scheme

`DELETE /api/scenarios/{scenario_id}/run-schemes/{scheme_id}`

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

_RESPONSE_DECLS: Final[list[DeclarationEntry]] = []

SCENARIOS_DELETE_BY_SCENARIO_ID_RUN_SCHEMES_BY_S_6A5300: Final[EndpointSpec] = EndpointSpec(
    id="platform.scenarios.delete_by_scenario_id_run_schemes_by_s_6a5300",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Delete Run Scheme",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="DELETE",
        path="/api/scenarios/{scenario_id}/run-schemes/{scheme_id}",
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
        204: ResponseSpec(
            status=204,
            description="Successful Response",
            declarations=_RESPONSE_DECLS,
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="scenarios",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
        business_notes="responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）",
    ),
)
