"""platform.adaptations.get_refs_drift —— Refs Drift

`GET /api/adaptations/refs-drift`

倒排索引 vs plate 接口目录 diff(只读):悬空引用 / 全网零引用。

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

ADAPTATIONS_GET_REFS_DRIFT: Final[EndpointSpec] = EndpointSpec(
    id="platform.adaptations.get_refs_drift",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Refs Drift",
    description="倒排索引 vs plate 接口目录 diff(只读):悬空引用 / 全网零引用。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/adaptations/refs-drift",
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
                DeclarationEntry(name="dangling", path="$.dangling", type="array",
                                  ui_kind="json", assertable=True),
                DeclarationEntry(name="plateReachable", path="$.plateReachable",
                                  type="boolean", ui_kind="boolean", required=True,
                                  assertable=True),
                DeclarationEntry(name="zeroRef", path="$.zeroRef", type="array",
                                  ui_kind="json", assertable=True),
            ]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="adaptations",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
