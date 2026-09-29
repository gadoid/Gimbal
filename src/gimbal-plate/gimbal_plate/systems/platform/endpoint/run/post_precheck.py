"""platform.run.post_precheck —— Precheck Run

`POST /api/run/precheck`

批量预检:队列 N 条一次发回判定面,逐条独立结论(一条 404 不连坐)。

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

RUN_POST_PRECHECK: Final[EndpointSpec] = EndpointSpec(
    id="platform.run.post_precheck",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Precheck Run",
    description="批量预检:队列 N 条一次发回判定面,逐条独立结论(一条 404 不连坐)。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="POST",
        path="/api/run/precheck",
        auth="bearer",
        timeout_seconds=30.0,
    ),
    request=RequestSpec(
        body_type="json",
        declarations=[
            DeclarationEntry(name="scenarioId", path="$.scenarioId", type="string",
                              ui_kind="text", required=True),
            DeclarationEntry(name="schemeId", path="$.schemeId", type="string",
                              ui_kind="text", required=True),
        ]
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="Successful Response",
            declarations=[
                DeclarationEntry(name="danglingEntryIds", path="$.danglingEntryIds",
                                  type="array", ui_kind="json", assertable=True),
                DeclarationEntry(name="deadDatasetIds", path="$.deadDatasetIds",
                                  type="array", ui_kind="json", assertable=True),
                DeclarationEntry(name="found", path="$.found", type="boolean",
                                  ui_kind="boolean", assertable=True),
                DeclarationEntry(name="scenarioId", path="$.scenarioId", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="schemeFound", path="$.schemeFound", type="boolean",
                                  ui_kind="boolean", assertable=True),
                DeclarationEntry(name="schemeId", path="$.schemeId", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="schemeValid", path="$.schemeValid", type="boolean",
                                  ui_kind="boolean", assertable=True),
                DeclarationEntry(name="unboundServices", path="$.unboundServices",
                                  type="array", ui_kind="json", assertable=True),
            ]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="run",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
