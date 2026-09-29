"""platform.report_definitions.put_by_definition_id —— Update Definition

`PUT /api/report-definitions/{definition_id}`

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

REPORT_DEFINITIONS_PUT_BY_DEFINITION_ID: Final[EndpointSpec] = EndpointSpec(
    id="platform.report_definitions.put_by_definition_id",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Update Definition",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="PUT",
        path="/api/report-definitions/{definition_id}",
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
            DeclarationEntry(name="name", path="$.name", type="string", ui_kind="text"),
            DeclarationEntry(name="public", path="$.public", type="boolean",
                              ui_kind="boolean"),
        ]
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="Successful Response",
            declarations=[]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="report-definitions",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
