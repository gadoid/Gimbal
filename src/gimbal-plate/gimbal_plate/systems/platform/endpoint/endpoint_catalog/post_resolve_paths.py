"""platform.endpoint_catalog.post_resolve_paths —— Resolve Paths

`POST /api/endpoint-catalog/resolve-paths`

Proxy ``POST {plate}/api/endpoint/action/resolve-paths``.

B1 路径推断: 响应样本 → 候选 JSONPath(数组展开下标),供编排页
策略路径字段(assertion.target / extract.expression)点选 — 替代
断言面缺失时的静默猜测。action 名是连字符(fin 系统
endpoint dim 注册名)。解 ``data.paths`` 返回数组(前端下拉直接用)。

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

ENDPOINT_CATALOG_POST_RESOLVE_PATHS: Final[EndpointSpec] = EndpointSpec(
    id="platform.endpoint_catalog.post_resolve_paths",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Resolve Paths",
    description="Proxy ``POST {plate}/api/endpoint/action/resolve-paths``.\n\nB1 路径推断: 响应样本 → 候选 JSONPath(数组展开下标),供编排页\n策略路径字段(assertion.target / extract.expression)点选 — 替代\n断言面缺失时的静默猜测。action 名是连字符(fin 系统\nendpoint dim 注册名)。解 ``data.paths`` 返回数组(前端下拉直接用)。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="POST",
        path="/api/endpoint-catalog/resolve-paths",
        auth="bearer",
        timeout_seconds=30.0,
    ),
    request=RequestSpec(
        body_type="json",
        declarations=[
            DeclarationEntry(name="path_prefix", path="$.path_prefix", type="string",
                              ui_kind="text"),
            DeclarationEntry(name="response_body_sample", path="$.response_body_sample",
                              type="string", ui_kind="text", required=True),
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
