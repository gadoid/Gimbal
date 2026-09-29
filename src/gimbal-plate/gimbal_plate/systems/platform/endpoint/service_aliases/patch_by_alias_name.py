"""platform.service_aliases.patch_by_alias_name —— Patch Alias

`PATCH /api/service-aliases/{alias_name}`

改别名:共享行 operator+;个人行 admin(归属域的写权只属 admin)。

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

SERVICE_ALIASES_PATCH_BY_ALIAS_NAME: Final[EndpointSpec] = EndpointSpec(
    id="platform.service_aliases.patch_by_alias_name",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Patch Alias",
    description="改别名:共享行 operator+;个人行 admin(归属域的写权只属 admin)。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="PATCH",
        path="/api/service-aliases/{alias_name}",
        auth="bearer",
        timeout_seconds=30.0,
    ),
    request=RequestSpec(
        body_type="json",
        declarations=[
            DeclarationEntry(name="baseUrl", path="$.baseUrl", type="string", ui_kind="text"),
            DeclarationEntry(name="credentialAlias", path="$.credentialAlias",
                              type="string", ui_kind="text"),
            DeclarationEntry(name="groupTag", path="$.groupTag", type="string",
                              ui_kind="text"),
        ]
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="Successful Response",
            declarations=[
                DeclarationEntry(name="aliasName", path="$.aliasName", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="baseService", path="$.baseService", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="baseUrl", path="$.baseUrl", type="string",
                                  ui_kind="text", assertable=True),
                DeclarationEntry(name="createdAt", path="$.createdAt", type="string",
                                  ui_kind="text", assertable=True),
                DeclarationEntry(name="credentialAlias", path="$.credentialAlias",
                                  type="string", ui_kind="text", assertable=True),
                DeclarationEntry(name="groupTag", path="$.groupTag", type="string",
                                  ui_kind="text", assertable=True),
                DeclarationEntry(name="ownerUserId", path="$.ownerUserId", type="integer",
                                  ui_kind="number", assertable=True),
                DeclarationEntry(name="updatedAt", path="$.updatedAt", type="string",
                                  ui_kind="text", assertable=True),
            ]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="service-aliases",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
