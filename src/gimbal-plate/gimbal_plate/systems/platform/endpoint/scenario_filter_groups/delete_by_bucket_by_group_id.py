"""platform.scenario_filter_groups.delete_by_bucket_by_group_id —— Delete Group

`DELETE /api/scenario-filter-groups/{bucket}/{group_id}`

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

SCENARIO_FILTER_GROUPS_DELETE_BY_BUCKET_BY_GROUP_ID: Final[EndpointSpec] = EndpointSpec(
    id="platform.scenario_filter_groups.delete_by_bucket_by_group_id",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Delete Group",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="DELETE",
        path="/api/scenario-filter-groups/{bucket}/{group_id}",
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
            declarations=[]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="scenario-filter-groups",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
