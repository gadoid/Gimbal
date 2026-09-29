"""platform.scenarios.post_by_scenario_id_copy —— Copy Scenario To Me

`POST /api/scenarios/{scenario_id}/copy`

深拷贝场景+用例+数据集;新属主 = 调用者,visibility=private。
需要读权限(public 或自己的场景才可复制)。

带 ``name``(另存为,2026-09-23 批次 F2):与本人已有场景重名 →
409 ``name_taken``,detail 带 ``suggestion``(计数后缀名),前端
确认后带 suggestion 重发;重名判定走 resolve_name_conflict 唯一实现。

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

SCENARIOS_POST_BY_SCENARIO_ID_COPY: Final[EndpointSpec] = EndpointSpec(
    id="platform.scenarios.post_by_scenario_id_copy",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Copy Scenario To Me",
    description="深拷贝场景+用例+数据集;新属主 = 调用者,visibility=private。\n需要读权限(public 或自己的场景才可复制)。\n\n带 ``name``(另存为,2026-09-23 批次 F2):与本人已有场景重名 →\n409 ``name_taken``,detail 带 ``suggestion``(计数后缀名),前端\n确认后带 suggestion 重发;重名判定走 resolve_name_conflict 唯一实现。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="POST",
        path="/api/scenarios/{scenario_id}/copy",
        auth="bearer",
        timeout_seconds=30.0,
    ),
    request=RequestSpec(
        body_type="json",
        declarations=[
            DeclarationEntry(name="name", path="$.name", type="string", ui_kind="text"),
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
