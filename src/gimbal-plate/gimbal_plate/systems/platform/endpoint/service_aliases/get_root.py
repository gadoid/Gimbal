"""platform.service_aliases.get_root —— List Aliases

`GET /api/service-aliases`

M4(§6.3):Page 信封 + ``q``(alias/base/credential 子串)下推。

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

SERVICE_ALIASES_GET_ROOT: Final[EndpointSpec] = EndpointSpec(
    id="platform.service_aliases.get_root",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="List Aliases",
    description="M4(§6.3):Page 信封 + ``q``(alias/base/credential 子串)下推。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/service-aliases",
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
                DeclarationEntry(name="items", path="$.items", type="array", ui_kind="json",
                                  required=True, assertable=True, children=[
                                     DeclarationEntry(name="aliasName",
                                                       path="$.items.aliasName",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="baseService",
                                                       path="$.items.baseService",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="baseUrl",
                                                       path="$.items.baseUrl",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="createdAt",
                                                       path="$.items.createdAt",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="credentialAlias",
                                                       path="$.items.credentialAlias",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="groupTag",
                                                       path="$.items.groupTag",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="ownerUserId",
                                                       path="$.items.ownerUserId",
                                                       type="integer", ui_kind="number",
                                                       assertable=True),
                                     DeclarationEntry(name="updatedAt",
                                                       path="$.items.updatedAt",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                 ]
                ),
                DeclarationEntry(name="page", path="$.page", type="integer",
                                  ui_kind="number", assertable=True),
                DeclarationEntry(name="pageSize", path="$.pageSize", type="integer",
                                  ui_kind="number", assertable=True),
                DeclarationEntry(name="total", path="$.total", type="integer",
                                  ui_kind="number", assertable=True),
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
