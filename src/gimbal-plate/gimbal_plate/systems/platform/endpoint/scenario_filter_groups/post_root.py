"""platform.scenario_filter_groups.post_root —— Create Group

`POST /api/scenario-filter-groups`

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

SCENARIO_FILTER_GROUPS_POST_ROOT: Final[EndpointSpec] = EndpointSpec(
    id="platform.scenario_filter_groups.post_root",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Create Group",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="POST",
        path="/api/scenario-filter-groups",
        auth="bearer",
        timeout_seconds=30.0,
    ),
    request=RequestSpec(
        body_type="json",
        declarations=[
            DeclarationEntry(name="bucket", path="$.bucket", type="string", ui_kind="text",
                              required=True),
            DeclarationEntry(name="filters", path="$.filters", type="object", ui_kind="json"),
            DeclarationEntry(name="name", path="$.name", type="string", ui_kind="text",
                              required=True),
            DeclarationEntry(name="q", path="$.q", type="string", ui_kind="text"),
        ]
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="Successful Response",
            declarations=[
                DeclarationEntry(name="createdAt", path="$.createdAt", type="string",
                                  ui_kind="text", assertable=True),
                DeclarationEntry(name="filters", path="$.filters", type="object",
                                  ui_kind="json", assertable=True),
                DeclarationEntry(name="id", path="$.id", type="string", ui_kind="text",
                                  required=True, assertable=True),
                DeclarationEntry(name="name", path="$.name", type="string", ui_kind="text",
                                  required=True, assertable=True),
                DeclarationEntry(name="q", path="$.q", type="string", ui_kind="text",
                                  assertable=True),
            ]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="scenario-filter-groups",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
