"""platform.scenarios.get_by_scenario_id_draft —— Get Scenario Draft

`GET /api/scenarios/{scenario_id}/draft`

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

SCENARIOS_GET_BY_SCENARIO_ID_DRAFT: Final[EndpointSpec] = EndpointSpec(
    id="platform.scenarios.get_by_scenario_id_draft",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Get Scenario Draft",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/scenarios/{scenario_id}/draft",
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
                DeclarationEntry(name="assertion_registry", path="$.assertion_registry",
                                  type="object", ui_kind="json", assertable=True),
                DeclarationEntry(name="definition", path="$.definition", type="object",
                                  ui_kind="json", required=True, assertable=True),
                DeclarationEntry(name="orchestration", path="$.orchestration",
                                  type="object", ui_kind="json",
                                  description="Platform rendering/orchestration container.\n\nsteps is index-aligned with definition.steps (same order, same length).\nresourceMeta is name-aligned with definition.resource keys.\n(runSchemes sidecar 键已随阶段④下线 — 方案不经场景 payload,唯一\n读写面是 /run-schemes CRUD;存量 payload 中的同键被 extra=ignore\n静默忽略。)",
                                  assertable=True, children=[
                                     DeclarationEntry(name="resourceMeta",
                                                       path="$.orchestration.resourceMeta",
                                                       type="object", ui_kind="json",
                                                       assertable=True),
                                     DeclarationEntry(name="steps",
                                                       path="$.orchestration.steps",
                                                       type="array", ui_kind="json",
                                                       assertable=True, children=[
                                                          DeclarationEntry(name="enabled",
                                                                            path="$.orchestration.steps.enabled",
                                                                            type="boolean",
                                                                            ui_kind="boolean",
                                                                            assertable=True),
                                                          DeclarationEntry(name="name",
                                                                            path="$.orchestration.steps.name",
                                                                            type="string",
                                                                            ui_kind="text",
                                                                            assertable=True),
                                                      ]
                                     ),
                                 ]
                ),
            ]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="scenarios",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
