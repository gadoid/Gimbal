"""platform.adaptations.get_impact_summary —— Impact Summary

`GET /api/adaptations/impact-summary`

本批影响面摘要(配套方案 §3.2):pending 端点集(客户端从
catalog/diff 拿到后传入)→ 按服务聚合的 波及用例 / 最近失败 数。
纯读 —— 不复算 diff(catalog_diff 带基线写副作用,不藏进 GET);
recentFail 全站口径(跨 owner 聚合数,方案 §3.5)。

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

ADAPTATIONS_GET_IMPACT_SUMMARY: Final[EndpointSpec] = EndpointSpec(
    id="platform.adaptations.get_impact_summary",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Impact Summary",
    description="本批影响面摘要(配套方案 §3.2):pending 端点集(客户端从\ncatalog/diff 拿到后传入)→ 按服务聚合的 波及用例 / 最近失败 数。\n纯读 —— 不复算 diff(catalog_diff 带基线写副作用,不藏进 GET);\nrecentFail 全站口径(跨 owner 聚合数,方案 §3.5)。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/adaptations/impact-summary",
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
                DeclarationEntry(name="services", path="$.services", type="array",
                                  ui_kind="json", assertable=True, children=[
                                     DeclarationEntry(name="caseCount",
                                                       path="$.services.caseCount",
                                                       type="integer", ui_kind="number",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="changeCount",
                                                       path="$.services.changeCount",
                                                       type="integer", ui_kind="number",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="name", path="$.services.name",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="recentFailCount",
                                                       path="$.services.recentFailCount",
                                                       type="integer", ui_kind="number",
                                                       required=True, assertable=True),
                                 ]
                ),
                DeclarationEntry(name="totals", path="$.totals", type="object",
                                  ui_kind="json", required=True, assertable=True, children=[
                                     DeclarationEntry(name="caseCount",
                                                       path="$.totals.caseCount",
                                                       type="integer", ui_kind="number",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="changeCount",
                                                       path="$.totals.changeCount",
                                                       type="integer", ui_kind="number",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="recentFailCount",
                                                       path="$.totals.recentFailCount",
                                                       type="integer", ui_kind="number",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="serviceCount",
                                                       path="$.totals.serviceCount",
                                                       type="integer", ui_kind="number",
                                                       required=True, assertable=True),
                                 ]
                ),
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
