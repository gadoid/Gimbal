"""platform.scenarios.get_by_scenario_id_run_schemes —— List Run Schemes

`GET /api/scenarios/{scenario_id}/run-schemes`

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

SCENARIOS_GET_BY_SCENARIO_ID_RUN_SCHEMES: Final[EndpointSpec] = EndpointSpec(
    id="platform.scenarios.get_by_scenario_id_run_schemes",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="List Run Schemes",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/scenarios/{scenario_id}/run-schemes",
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
        module="scenarios",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
