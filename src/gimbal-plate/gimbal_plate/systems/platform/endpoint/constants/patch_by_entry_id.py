"""platform.constants.patch_by_entry_id —— Patch Constant

`PATCH /api/constants/{entry_id}`

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

CONSTANTS_PATCH_BY_ENTRY_ID: Final[EndpointSpec] = EndpointSpec(
    id="platform.constants.patch_by_entry_id",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Patch Constant",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="PATCH",
        path="/api/constants/{entry_id}",
        auth="bearer",
        timeout_seconds=30.0,
    ),
    request=RequestSpec(
        body_type="json",
        declarations=[
            DeclarationEntry(name="description", path="$.description", type="string",
                              ui_kind="text"),
            DeclarationEntry(name="spec", path="$.spec", type="object", ui_kind="json"),
            DeclarationEntry(name="value", path="$.value", type="string", ui_kind="text"),
        ]
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="Successful Response",
            declarations=[
                DeclarationEntry(name="created_at", path="$.created_at", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="description", path="$.description", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="entry_kind", path="$.entry_kind", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="id", path="$.id", type="integer", ui_kind="number",
                                  required=True, assertable=True),
                DeclarationEntry(name="name", path="$.name", type="string", ui_kind="text",
                                  required=True, assertable=True),
                DeclarationEntry(name="spec", path="$.spec", type="object", ui_kind="json",
                                  assertable=True),
                DeclarationEntry(name="updated_at", path="$.updated_at", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="value", path="$.value", type="string",
                                  ui_kind="text", assertable=True),
            ]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="constants",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
