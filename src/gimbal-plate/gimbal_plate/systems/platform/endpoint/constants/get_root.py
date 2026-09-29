"""platform.constants.get_root —— List Constants

`GET /api/constants`

Page 信封 + 服务端过滤(M4,§6.3):``q``(name/description 子串)、
``kind``(literal/generator 精确)。条目小但也会长,先立信封契约。

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

CONSTANTS_GET_ROOT: Final[EndpointSpec] = EndpointSpec(
    id="platform.constants.get_root",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="List Constants",
    description="Page 信封 + 服务端过滤(M4,§6.3):``q``(name/description 子串)、\n``kind``(literal/generator 精确)。条目小但也会长,先立信封契约。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/constants",
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
                                     DeclarationEntry(name="created_at",
                                                       path="$.items.created_at",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="description",
                                                       path="$.items.description",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="entry_kind",
                                                       path="$.items.entry_kind",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="id", path="$.items.id",
                                                       type="integer", ui_kind="number",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="name", path="$.items.name",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="spec", path="$.items.spec",
                                                       type="object", ui_kind="json",
                                                       assertable=True),
                                     DeclarationEntry(name="updated_at",
                                                       path="$.items.updated_at",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="value", path="$.items.value",
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
        module="constants",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
