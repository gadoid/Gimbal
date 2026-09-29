"""platform.data_sets.get_root —— List Data Sets

`GET /api/data-sets`

List summaries scoped to the caller.

Data-set rows are business parameter matrices — listing every user's
data (the previous behaviour) is a cross-user disclosure, so non-admin
callers only see data-sets whose parent scenario they own.

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

DATA_SETS_GET_ROOT: Final[EndpointSpec] = EndpointSpec(
    id="platform.data_sets.get_root",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="List Data Sets",
    description="List summaries scoped to the caller.\n\nData-set rows are business parameter matrices — listing every user's\ndata (the previous behaviour) is a cross-user disclosure, so non-admin\ncallers only see data-sets whose parent scenario they own.",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/data-sets",
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
                DeclarationEntry(name="datasetId", path="$.datasetId", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="name", path="$.name", type="string", ui_kind="text",
                                  required=True, assertable=True),
                DeclarationEntry(name="preview", path="$.preview", type="array",
                                  ui_kind="json", assertable=True),
                DeclarationEntry(name="rowCount", path="$.rowCount", type="integer",
                                  ui_kind="number", assertable=True),
                DeclarationEntry(name="scenarioId", path="$.scenarioId", type="string",
                                  ui_kind="text", required=True, assertable=True),
            ]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="data-sets",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
