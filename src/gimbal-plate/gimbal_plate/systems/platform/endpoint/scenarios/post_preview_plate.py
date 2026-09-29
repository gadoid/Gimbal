"""platform.scenarios.post_preview_plate —— Preview Plate

`POST /api/scenarios/preview-plate`

Forward the draft to Plate's ``/convert`` and return the verdict.

Does NOT persist anything — the draft is treated as ephemeral so the
user can preview before saving.  The converted payload (Plate
/convert 的归一化结果) 也一并返回,前端导出按钮直接用它作为
"GIMBAL 可执行" 的场景 JSON/YAML。

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

SCENARIOS_POST_PREVIEW_PLATE: Final[EndpointSpec] = EndpointSpec(
    id="platform.scenarios.post_preview_plate",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Preview Plate",
    description="Forward the draft to Plate's ``/convert`` and return the verdict.\n\nDoes NOT persist anything — the draft is treated as ephemeral so the\nuser can preview before saving.  The converted payload (Plate\n/convert 的归一化结果) 也一并返回,前端导出按钮直接用它作为\n\"GIMBAL 可执行\" 的场景 JSON/YAML。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="POST",
        path="/api/scenarios/preview-plate",
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
            DeclarationEntry(name="overlay", path="$.overlay", type="object", ui_kind="json",
                             children=[
                                 DeclarationEntry(name="serviceBindings",
                                                   path="$.overlay.serviceBindings",
                                                   type="object", ui_kind="json"),
                             ]
            ),
        ]
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="Successful Response",
            declarations=[
                DeclarationEntry(name="converted", path="$.converted", type="object",
                                  ui_kind="json", assertable=True),
                DeclarationEntry(name="errors", path="$.errors", type="array",
                                  ui_kind="json", assertable=True, children=[
                                     DeclarationEntry(name="message",
                                                       path="$.errors.message",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="path", path="$.errors.path",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                 ]
                ),
                DeclarationEntry(name="ok", path="$.ok", type="boolean", ui_kind="boolean",
                                  required=True, assertable=True),
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
