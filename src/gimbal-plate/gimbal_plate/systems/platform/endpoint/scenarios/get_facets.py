"""platform.scenarios.get_facets —— Scenario Facets

`GET /api/scenarios/facets`

五维 facets:modules/systems/tags/authors/priorities 可选值+计数。

替代前端「全量拉回 FilterPopover unique」的 M1 过渡形态。PG 走
GROUP BY + jsonb unnest;SQLite Python 兜底(方言分派同 list)。

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

SCENARIOS_GET_FACETS: Final[EndpointSpec] = EndpointSpec(
    id="platform.scenarios.get_facets",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Scenario Facets",
    description="五维 facets:modules/systems/tags/authors/priorities 可选值+计数。\n\n替代前端「全量拉回 FilterPopover unique」的 M1 过渡形态。PG 走\nGROUP BY + jsonb unnest;SQLite Python 兜底(方言分派同 list)。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/scenarios/facets",
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
