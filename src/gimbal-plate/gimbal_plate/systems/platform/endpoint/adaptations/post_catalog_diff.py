"""platform.adaptations.post_catalog_diff —— Catalog Diff

`POST /api/adaptations/catalog/diff`

拉 plate 目录对戳:待适配 / 异常(C12 忘 bump、下架)/ 本次新落基线数。

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

ADAPTATIONS_POST_CATALOG_DIFF: Final[EndpointSpec] = EndpointSpec(
    id="platform.adaptations.post_catalog_diff",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Catalog Diff",
    description="拉 plate 目录对戳:待适配 / 异常(C12 忘 bump、下架)/ 本次新落基线数。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="POST",
        path="/api/adaptations/catalog/diff",
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
                DeclarationEntry(name="anomalies", path="$.anomalies", type="array",
                                  ui_kind="json", assertable=True, children=[
                                     DeclarationEntry(name="detail",
                                                       path="$.anomalies.detail",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="endpointId",
                                                       path="$.anomalies.endpointId",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="reason",
                                                       path="$.anomalies.reason",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                 ]
                ),
                DeclarationEntry(name="baselinedNow", path="$.baselinedNow", type="integer",
                                  ui_kind="number", assertable=True),
                DeclarationEntry(name="pending", path="$.pending", type="array",
                                  ui_kind="json", assertable=True, children=[
                                     DeclarationEntry(name="endpointId",
                                                       path="$.pending.endpointId",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="fromVersion",
                                                       path="$.pending.fromVersion",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="toVersion",
                                                       path="$.pending.toVersion",
                                                       type="string", ui_kind="text",
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
