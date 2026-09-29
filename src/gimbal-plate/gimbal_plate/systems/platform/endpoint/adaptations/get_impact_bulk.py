"""platform.adaptations.get_impact_bulk —— Impact Bulk

`GET /api/adaptations/impact-bulk`

批量 impact(M5,债 12):一次请求回全部 pending 端点的受影响
清单 —— 前端 useInterfaceChange 的「每端点一次 × 限并发 4」N+1
消除。返回 {endpointId: [ImpactItem...]}(与单端点 /impact 同条目
形状,未命中端点给空数组)。

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

ADAPTATIONS_GET_IMPACT_BULK: Final[EndpointSpec] = EndpointSpec(
    id="platform.adaptations.get_impact_bulk",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Impact Bulk",
    description="批量 impact(M5,债 12):一次请求回全部 pending 端点的受影响\n清单 —— 前端 useInterfaceChange 的「每端点一次 × 限并发 4」N+1\n消除。返回 {endpointId: [ImpactItem...]}(与单端点 /impact 同条目\n形状,未命中端点给空数组)。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/adaptations/impact-bulk",
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
        module="adaptations",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
