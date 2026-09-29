"""platform.adaptations.get_batches —— List Batches

`GET /api/adaptations/batches`

批次列表:operator/admin 全量;member 仅 ``scope=mine``(C13 owner
知情视图;M2.5 起技术运营权归 operator,权限方案 §1.2)。M4(§6.3):
status 精确 + Page 信封。

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

ADAPTATIONS_GET_BATCHES: Final[EndpointSpec] = EndpointSpec(
    id="platform.adaptations.get_batches",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="List Batches",
    description="批次列表:operator/admin 全量;member 仅 ``scope=mine``(C13 owner\n知情视图;M2.5 起技术运营权归 operator,权限方案 §1.2)。M4(§6.3):\nstatus 精确 + Page 信封。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/adaptations/batches",
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
                                     DeclarationEntry(name="batchId",
                                                       path="$.items.batchId",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="closedAt",
                                                       path="$.items.closedAt",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="createdAt",
                                                       path="$.items.createdAt",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="endpointId",
                                                       path="$.items.endpointId",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="endpointMethod",
                                                       path="$.items.endpointMethod",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="endpointName",
                                                       path="$.items.endpointName",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="endpointPath",
                                                       path="$.items.endpointPath",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="fromVersion",
                                                       path="$.items.fromVersion",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="opCounts",
                                                       path="$.items.opCounts",
                                                       type="object", ui_kind="json",
                                                       assertable=True),
                                     DeclarationEntry(name="operatorId",
                                                       path="$.items.operatorId",
                                                       type="integer", ui_kind="number",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="status", path="$.items.status",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="toVersion",
                                                       path="$.items.toVersion",
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
        module="adaptations",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
