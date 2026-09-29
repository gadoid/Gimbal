"""platform.report_definitions.post_root —— Create Definition

`POST /api/report-definitions`

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

_RESPONSE_DECLS: Final[list[DeclarationEntry]] = []

REPORT_DEFINITIONS_POST_ROOT: Final[EndpointSpec] = EndpointSpec(
    id="platform.report_definitions.post_root",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Create Definition",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="POST",
        path="/api/report-definitions",
        auth="bearer",
        timeout_seconds=30.0,
    ),
    request=RequestSpec(
        body_type="json",
        declarations=[
            DeclarationEntry(name="definition", path="$.definition", type="object",
                              ui_kind="json"),
            DeclarationEntry(name="description", path="$.description", type="string",
                              ui_kind="text"),
            DeclarationEntry(name="name", path="$.name", type="string", ui_kind="text",
                              required=True),
            DeclarationEntry(name="presentation", path="$.presentation", type="object",
                              ui_kind="json"),
            DeclarationEntry(name="projection", path="$.projection", type="object",
                              ui_kind="json"),
            DeclarationEntry(name="public", path="$.public", type="boolean",
                              ui_kind="boolean"),
            DeclarationEntry(name="selection", path="$.selection", type="object",
                              ui_kind="json"),
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
        module="report-definitions",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
        business_notes="responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）",
    ),
)
