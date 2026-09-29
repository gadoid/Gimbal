"""platform.scenarios.post_root —— Create Scenario

`POST /api/scenarios`

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

_RESPONSE_DECLS: Final[list[DeclarationEntry]] = [
    DeclarationEntry(name="config", path="$.config", type="object", ui_kind="json",
                      assertable=True),
    DeclarationEntry(name="dataSetCount", path="$.dataSetCount", type="integer",
                      ui_kind="number", assertable=True),
    DeclarationEntry(name="meta", path="$.meta", type="object", ui_kind="json",
                      required=True,
                      description="Scenario metadata; one Scenario has exactly one Meta.",
                      assertable=True, children=[
                         DeclarationEntry(name="author", path="$.meta.author",
                                           type="string", ui_kind="text", assertable=True),
                         DeclarationEntry(name="createTime", path="$.meta.createTime",
                                           type="string", ui_kind="text", assertable=True),
                         DeclarationEntry(name="description", path="$.meta.description",
                                           type="string", ui_kind="text", assertable=True),
                         DeclarationEntry(name="expire", path="$.meta.expire",
                                           type="boolean", ui_kind="boolean",
                                           assertable=True),
                         DeclarationEntry(name="module", path="$.meta.module",
                                           type="string", ui_kind="text", required=True,
                                           assertable=True),
                         DeclarationEntry(name="name", path="$.meta.name", type="string",
                                           ui_kind="text", required=True, assertable=True),
                         DeclarationEntry(name="owner", path="$.meta.owner", type="string",
                                           ui_kind="text", assertable=True),
                         DeclarationEntry(name="priority", path="$.meta.priority",
                                           type="integer", ui_kind="number", required=True,
                                           assertable=True),
                         DeclarationEntry(name="scenarioId", path="$.meta.scenarioId",
                                           type="string", ui_kind="text", required=True,
                                           assertable=True),
                         DeclarationEntry(name="system", path="$.meta.system", type="array",
                                           ui_kind="json", assertable=True),
                         DeclarationEntry(name="tags", path="$.meta.tags", type="array",
                                           ui_kind="json", assertable=True),
                         DeclarationEntry(name="updateTime", path="$.meta.updateTime",
                                           type="string", ui_kind="text", assertable=True),
                         DeclarationEntry(name="version", path="$.meta.version",
                                           type="string", ui_kind="text", assertable=True),
                     ]
    ),
    DeclarationEntry(name="orchestration", path="$.orchestration", type="object",
                      ui_kind="json", assertable=True, children=[
                         DeclarationEntry(name="resourceMeta",
                                           path="$.orchestration.resourceMeta",
                                           type="object", ui_kind="json", assertable=True),
                         DeclarationEntry(name="steps", path="$.orchestration.steps",
                                           type="array", ui_kind="json", assertable=True,
                                          children=[
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
    DeclarationEntry(name="resource", path="$.resource", type="object", ui_kind="json",
                      assertable=True),
    DeclarationEntry(name="schemeCount", path="$.schemeCount", type="integer",
                      ui_kind="number", assertable=True),
    DeclarationEntry(name="starred", path="$.starred", type="boolean", ui_kind="boolean",
                      assertable=True),
    DeclarationEntry(name="stepCount", path="$.stepCount", type="integer", ui_kind="number",
                      assertable=True),
    DeclarationEntry(name="steps", path="$.steps", type="array", ui_kind="json",
                      assertable=True),
    DeclarationEntry(name="tags", path="$.tags", type="array", ui_kind="json",
                      assertable=True),
    DeclarationEntry(name="visibility", path="$.visibility", type="string", ui_kind="text",
                      assertable=True),
]

SCENARIOS_POST_ROOT: Final[EndpointSpec] = EndpointSpec(
    id="platform.scenarios.post_root",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Create Scenario",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="POST",
        path="/api/scenarios",
        auth="bearer",
        timeout_seconds=30.0,
    ),
    request=RequestSpec(
        body_type="json",
        declarations=[
            DeclarationEntry(name="assertion_registry", path="$.assertion_registry",
                              type="object", ui_kind="json"),
            DeclarationEntry(name="definition", path="$.definition", type="object",
                              ui_kind="json", required=True),
            DeclarationEntry(name="orchestration", path="$.orchestration", type="object",
                              ui_kind="json",
                              description="Platform rendering/orchestration container.\n\nsteps is index-aligned with definition.steps (same order, same length).\nresourceMeta is name-aligned with definition.resource keys.\n(runSchemes sidecar 键已随阶段④下线 — 方案不经场景 payload,唯一\n读写面是 /run-schemes CRUD;存量 payload 中的同键被 extra=ignore\n静默忽略。)",
                             children=[
                                 DeclarationEntry(name="resourceMeta",
                                                   path="$.orchestration.resourceMeta",
                                                   type="object", ui_kind="json"),
                                 DeclarationEntry(name="steps",
                                                   path="$.orchestration.steps",
                                                   type="array", ui_kind="json", children=[
                                                      DeclarationEntry(name="enabled",
                                                                        path="$.orchestration.steps.enabled",
                                                                        type="boolean",
                                                                        ui_kind="boolean"),
                                                      DeclarationEntry(name="name",
                                                                        path="$.orchestration.steps.name",
                                                                        type="string",
                                                                        ui_kind="text"),
                                                  ]
                                 ),
                             ]
            ),
        ]
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="成功",
            declarations=_RESPONSE_DECLS,
        ),
        201: ResponseSpec(
            status=201,
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
