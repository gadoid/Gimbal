"""platform.services.get_by_service_grid —— Service Grid

`GET /api/services/{service}/grid`

服务级热力网格:一屏全接口 + 四格信号 + 盲区统计(§2)。

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

SERVICES_GET_BY_SERVICE_GRID: Final[EndpointSpec] = EndpointSpec(
    id="platform.services.get_by_service_grid",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Service Grid",
    description="服务级热力网格:一屏全接口 + 四格信号 + 盲区统计(§2)。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/services/{service}/grid",
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
                DeclarationEntry(name="endpoints", path="$.endpoints", type="array",
                                  ui_kind="json", assertable=True, children=[
                                     DeclarationEntry(name="caseCount",
                                                       path="$.endpoints.caseCount",
                                                       type="integer", ui_kind="number",
                                                       assertable=True),
                                     DeclarationEntry(name="id", path="$.endpoints.id",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="lastRunAt",
                                                       path="$.endpoints.lastRunAt",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="method",
                                                       path="$.endpoints.method",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="name", path="$.endpoints.name",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="path", path="$.endpoints.path",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="signals",
                                                       path="$.endpoints.signals",
                                                       type="object", ui_kind="json",
                                                       description="四格状态条(§2.3)。位置固定:①需求 ②用例 ③最近执行 ④适配告警。",
                                                       assertable=True, children=[
                                                          DeclarationEntry(name="alarm",
                                                                            path="$.endpoints.signals.alarm",
                                                                            type="boolean",
                                                                            ui_kind="boolean",
                                                                            assertable=True),
                                                          DeclarationEntry(name="cases",
                                                                            path="$.endpoints.signals.cases",
                                                                            type="boolean",
                                                                            ui_kind="boolean",
                                                                            assertable=True),
                                                          DeclarationEntry(name="lastRun",
                                                                            path="$.endpoints.signals.lastRun",
                                                                            type="string",
                                                                            ui_kind="text",
                                                                            assertable=True),
                                                          DeclarationEntry(name="req",
                                                                            path="$.endpoints.signals.req",
                                                                            type="string",
                                                                            ui_kind="text",
                                                                            assertable=True),
                                                      ]
                                     ),
                                 ]
                ),
                DeclarationEntry(name="plateReachable", path="$.plateReachable",
                                  type="boolean", ui_kind="boolean", required=True,
                                  assertable=True),
                DeclarationEntry(name="service", path="$.service", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="stats", path="$.stats", type="object",
                                  ui_kind="json",
                                  description="顶部统计条(§2.1)。`noRequirement` 随 P2 reference dim 再加。",
                                  assertable=True, children=[
                                     DeclarationEntry(name="hasAlarm",
                                                       path="$.stats.hasAlarm",
                                                       type="integer", ui_kind="number",
                                                       assertable=True),
                                     DeclarationEntry(name="neverRun",
                                                       path="$.stats.neverRun",
                                                       type="integer", ui_kind="number",
                                                       assertable=True),
                                     DeclarationEntry(name="noCases",
                                                       path="$.stats.noCases",
                                                       type="integer", ui_kind="number",
                                                       assertable=True),
                                     DeclarationEntry(name="total", path="$.stats.total",
                                                       type="integer", ui_kind="number",
                                                       assertable=True),
                                 ]
                ),
            ]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="services",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
