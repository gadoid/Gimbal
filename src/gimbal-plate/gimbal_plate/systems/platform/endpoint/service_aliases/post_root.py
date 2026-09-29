"""platform.service_aliases.post_root —— Create Alias

`POST /api/service-aliases`

登记别名(M2.5,权限方案 §1.2 两类归属拆行):
团队共享(owner_user_id 空)= operator+;个人默认(owner_user_id
非空,即「归属字段」)= admin —— 人事/内容权不落进技术运营角色。

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
    DeclarationEntry(name="aliasName", path="$.aliasName", type="string", ui_kind="text",
                      required=True, assertable=True),
    DeclarationEntry(name="baseService", path="$.baseService", type="string",
                      ui_kind="text", required=True, assertable=True),
    DeclarationEntry(name="baseUrl", path="$.baseUrl", type="string", ui_kind="text",
                      assertable=True),
    DeclarationEntry(name="createdAt", path="$.createdAt", type="string", ui_kind="text",
                      assertable=True),
    DeclarationEntry(name="credentialAlias", path="$.credentialAlias", type="string",
                      ui_kind="text", assertable=True),
    DeclarationEntry(name="groupTag", path="$.groupTag", type="string", ui_kind="text",
                      assertable=True),
    DeclarationEntry(name="ownerUserId", path="$.ownerUserId", type="integer",
                      ui_kind="number", assertable=True),
    DeclarationEntry(name="updatedAt", path="$.updatedAt", type="string", ui_kind="text",
                      assertable=True),
]

SERVICE_ALIASES_POST_ROOT: Final[EndpointSpec] = EndpointSpec(
    id="platform.service_aliases.post_root",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Create Alias",
    description="登记别名(M2.5,权限方案 §1.2 两类归属拆行):\n团队共享(owner_user_id 空)= operator+;个人默认(owner_user_id\n非空,即「归属字段」)= admin —— 人事/内容权不落进技术运营角色。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="POST",
        path="/api/service-aliases",
        auth="bearer",
        timeout_seconds=30.0,
    ),
    request=RequestSpec(
        body_type="json",
        declarations=[
            DeclarationEntry(name="aliasName", path="$.aliasName", type="string",
                              ui_kind="text", required=True),
            DeclarationEntry(name="baseUrl", path="$.baseUrl", type="string",
                              ui_kind="text", required=True),
            DeclarationEntry(name="credentialAlias", path="$.credentialAlias",
                              type="string", ui_kind="text"),
            DeclarationEntry(name="groupTag", path="$.groupTag", type="string",
                              ui_kind="text"),
            DeclarationEntry(name="ownerUserId", path="$.ownerUserId", type="integer",
                              ui_kind="number"),
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
        module="service-aliases",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
        business_notes="responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）",
    ),
)
