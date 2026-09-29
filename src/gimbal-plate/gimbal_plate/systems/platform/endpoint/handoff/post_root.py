"""platform.handoff.post_root —— Handoff Resource

`POST /api/handoff`

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

HANDOFF_POST_ROOT: Final[EndpointSpec] = EndpointSpec(
    id="platform.handoff.post_root",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Handoff Resource",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="POST",
        path="/api/handoff",
        auth="bearer",
        timeout_seconds=30.0,
    ),
    request=RequestSpec(
        body_type="json",
        declarations=[
            DeclarationEntry(name="resource_id", path="$.resource_id", type="string",
                              ui_kind="text", required=True),
            DeclarationEntry(name="resource_type", path="$.resource_type", type="string",
                              ui_kind="text"),
            DeclarationEntry(name="target_user_id", path="$.target_user_id", type="integer",
                              ui_kind="number", required=True),
        ]
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="Successful Response",
            declarations=[
                DeclarationEntry(name="new_name", path="$.new_name", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="new_resource_id", path="$.new_resource_id",
                                  type="string", ui_kind="text", required=True,
                                  assertable=True),
                DeclarationEntry(name="renamed", path="$.renamed", type="boolean",
                                  ui_kind="boolean", required=True, assertable=True),
                DeclarationEntry(name="status", path="$.status", type="string",
                                  ui_kind="text", assertable=True),
            ]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="handoff",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
