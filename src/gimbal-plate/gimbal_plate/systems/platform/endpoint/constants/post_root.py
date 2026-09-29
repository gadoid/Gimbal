"""platform.constants.post_root —— Create Constant

`POST /api/constants`

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
    DeclarationEntry(name="created_at", path="$.created_at", type="string", ui_kind="text",
                      required=True, assertable=True),
    DeclarationEntry(name="description", path="$.description", type="string",
                      ui_kind="text", required=True, assertable=True),
    DeclarationEntry(name="entry_kind", path="$.entry_kind", type="string", ui_kind="text",
                      required=True, assertable=True),
    DeclarationEntry(name="id", path="$.id", type="integer", ui_kind="number",
                      required=True, assertable=True),
    DeclarationEntry(name="name", path="$.name", type="string", ui_kind="text",
                      required=True, assertable=True),
    DeclarationEntry(name="spec", path="$.spec", type="object", ui_kind="json",
                      assertable=True),
    DeclarationEntry(name="updated_at", path="$.updated_at", type="string", ui_kind="text",
                      required=True, assertable=True),
    DeclarationEntry(name="value", path="$.value", type="string", ui_kind="text",
                      assertable=True),
]

CONSTANTS_POST_ROOT: Final[EndpointSpec] = EndpointSpec(
    id="platform.constants.post_root",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Create Constant",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="POST",
        path="/api/constants",
        auth="bearer",
        timeout_seconds=30.0,
    ),
    request=RequestSpec(
        body_type="json",
        declarations=[
            DeclarationEntry(name="description", path="$.description", type="string",
                              ui_kind="text"),
            DeclarationEntry(name="entry_kind", path="$.entry_kind", type="string",
                              ui_kind="text", required=True),
            DeclarationEntry(name="name", path="$.name", type="string", ui_kind="text",
                              required=True),
            DeclarationEntry(name="spec", path="$.spec", type="object", ui_kind="json"),
            DeclarationEntry(name="value", path="$.value", type="string", ui_kind="text"),
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
        module="constants",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
        business_notes="responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）",
    ),
)
