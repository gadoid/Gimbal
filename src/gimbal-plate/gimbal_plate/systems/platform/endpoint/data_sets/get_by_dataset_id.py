"""platform.data_sets.get_by_dataset_id —— Get Data Set

`GET /api/data-sets/{dataset_id}`

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

DATA_SETS_GET_BY_DATASET_ID: Final[EndpointSpec] = EndpointSpec(
    id="platform.data_sets.get_by_dataset_id",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Get Data Set",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/data-sets/{dataset_id}",
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
                DeclarationEntry(name="description", path="$.description", type="string",
                                  ui_kind="text", assertable=True),
                DeclarationEntry(name="name", path="$.name", type="string", ui_kind="text",
                                  required=True, assertable=True),
                DeclarationEntry(name="rowCount", path="$.rowCount", type="integer",
                                  ui_kind="number", assertable=True),
                DeclarationEntry(name="rows", path="$.rows", type="array", ui_kind="json",
                                  assertable=True),
                DeclarationEntry(name="scenarioId", path="$.scenarioId", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="varUnlocks", path="$.varUnlocks", type="array",
                                  ui_kind="json", assertable=True),
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
