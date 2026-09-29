"""platform.endpoint_catalog.post_by_endpoint_id_field_state_60b108 —— Validate Step Field States

`POST /api/endpoint-catalog/{endpoint_id}/field-states/validate`

§3.5 配置编辑校验:plate 目录 + step.field_states 增量 → 合成态裁决。

编辑器在改字段状态时调用:``errors`` 非空 = 拒(树一致性),
``warnings`` 仅提示(required 落 carry / DESCRIPTIVE 进 form /
目录外 stale path)。校验跑在合成态上 —— 目录本身一致但增量
破坏整传一致性同样拒。目录拉取复用 /full 代理语义(错误映射
同款:plate 不可达 502 / 404 endpoint_not_found)。

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

ENDPOINT_CATALOG_POST_BY_ENDPOINT_ID_FIELD_STATE_60B108: Final[EndpointSpec] = EndpointSpec(
    id="platform.endpoint_catalog.post_by_endpoint_id_field_state_60b108",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Validate Step Field States",
    description="§3.5 配置编辑校验:plate 目录 + step.field_states 增量 → 合成态裁决。\n\n编辑器在改字段状态时调用:``errors`` 非空 = 拒(树一致性),\n``warnings`` 仅提示(required 落 carry / DESCRIPTIVE 进 form /\n目录外 stale path)。校验跑在合成态上 —— 目录本身一致但增量\n破坏整传一致性同样拒。目录拉取复用 /full 代理语义(错误映射\n同款:plate 不可达 502 / 404 endpoint_not_found)。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="POST",
        path="/api/endpoint-catalog/{endpoint_id}/field-states/validate",
        auth="bearer",
        timeout_seconds=30.0,
    ),
    request=RequestSpec(
        body_type="json",
        declarations=[
            DeclarationEntry(name="field_states", path="$.field_states", type="object",
                              ui_kind="json"),
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
        module="endpoint-catalog",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
