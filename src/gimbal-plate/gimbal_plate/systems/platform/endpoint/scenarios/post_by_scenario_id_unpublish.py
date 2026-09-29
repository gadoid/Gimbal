"""platform.scenarios.post_by_scenario_id_unpublish —— Unpublish Scenario

`POST /api/scenarios/{scenario_id}/unpublish`

下架:visibility → private,仅 owner/admin 可读。

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

SCENARIOS_POST_BY_SCENARIO_ID_UNPUBLISH: Final[EndpointSpec] = EndpointSpec(
    id="platform.scenarios.post_by_scenario_id_unpublish",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Unpublish Scenario",
    description="下架:visibility → private,仅 owner/admin 可读。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="POST",
        path="/api/scenarios/{scenario_id}/unpublish",
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
                DeclarationEntry(name="config", path="$.config", type="object",
                                  ui_kind="json", assertable=True),
                DeclarationEntry(name="dataSetCount", path="$.dataSetCount", type="integer",
                                  ui_kind="number", assertable=True),
                DeclarationEntry(name="meta", path="$.meta", type="object", ui_kind="json",
                                  required=True,
                                  description="Scenario metadata; one Scenario has exactly one Meta.",
                                  assertable=True, children=[
                                     DeclarationEntry(name="author", path="$.meta.author",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="createTime",
                                                       path="$.meta.createTime",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="description",
                                                       path="$.meta.description",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="expire", path="$.meta.expire",
                                                       type="boolean", ui_kind="boolean",
                                                       assertable=True),
                                     DeclarationEntry(name="module", path="$.meta.module",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="name", path="$.meta.name",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="owner", path="$.meta.owner",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="priority",
                                                       path="$.meta.priority",
                                                       type="integer", ui_kind="number",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="scenarioId",
                                                       path="$.meta.scenarioId",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="system", path="$.meta.system",
                                                       type="array", ui_kind="json",
                                                       assertable=True),
                                     DeclarationEntry(name="tags", path="$.meta.tags",
                                                       type="array", ui_kind="json",
                                                       assertable=True),
                                     DeclarationEntry(name="updateTime",
                                                       path="$.meta.updateTime",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="version", path="$.meta.version",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                 ]
                ),
                DeclarationEntry(name="orchestration", path="$.orchestration",
                                  type="object", ui_kind="json", assertable=True, children=[
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
                DeclarationEntry(name="resource", path="$.resource", type="object",
                                  ui_kind="json", assertable=True),
                DeclarationEntry(name="schemeCount", path="$.schemeCount", type="integer",
                                  ui_kind="number", assertable=True),
                DeclarationEntry(name="starred", path="$.starred", type="boolean",
                                  ui_kind="boolean", assertable=True),
                DeclarationEntry(name="stepCount", path="$.stepCount", type="integer",
                                  ui_kind="number", assertable=True),
                DeclarationEntry(name="steps", path="$.steps", type="array", ui_kind="json",
                                  assertable=True),
                DeclarationEntry(name="tags", path="$.tags", type="array", ui_kind="json",
                                  assertable=True),
                DeclarationEntry(name="visibility", path="$.visibility", type="string",
                                  ui_kind="text", assertable=True),
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
