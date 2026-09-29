"""platform.endpoints.get_by_endpoint_id_board —— Endpoint Board

`GET /api/endpoints/{endpoint_id}/board`

接口级线索板:主体 + 测试象限 + 自建卡 + trails(§3)。

``?expand=<nodeId>`` 拉该节点的二度关联(P1 支持场景节点 → 它引用
的其他接口),默认只拉一度,避免一次拉巨图。

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

ENDPOINTS_GET_BY_ENDPOINT_ID_BOARD: Final[EndpointSpec] = EndpointSpec(
    id="platform.endpoints.get_by_endpoint_id_board",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Endpoint Board",
    description="接口级线索板:主体 + 测试象限 + 自建卡 + trails(§3)。\n\n``?expand=<nodeId>`` 拉该节点的二度关联(P1 支持场景节点 → 它引用\n的其他接口),默认只拉一度,避免一次拉巨图。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/endpoints/{endpoint_id}/board",
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
                DeclarationEntry(name="edges", path="$.edges", type="array", ui_kind="json",
                                  assertable=True, children=[
                                     DeclarationEntry(name="from", path="$.edges.from",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="kind", path="$.edges.kind",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="to", path="$.edges.to",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                 ]
                ),
                DeclarationEntry(name="nodes", path="$.nodes", type="array", ui_kind="json",
                                  assertable=True, children=[
                                     DeclarationEntry(name="id", path="$.nodes.id",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="kind", path="$.nodes.kind",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="label", path="$.nodes.label",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="meta", path="$.nodes.meta",
                                                       type="object", ui_kind="json",
                                                       assertable=True),
                                     DeclarationEntry(name="quadrant",
                                                       path="$.nodes.quadrant",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                 ]
                ),
                DeclarationEntry(name="quadrants", path="$.quadrants", type="object",
                                  ui_kind="json", assertable=True),
                DeclarationEntry(name="subject", path="$.subject", type="object",
                                  ui_kind="json", required=True, assertable=True, children=[
                                     DeclarationEntry(name="degraded",
                                                       path="$.subject.degraded",
                                                       type="boolean", ui_kind="boolean",
                                                       assertable=True),
                                     DeclarationEntry(name="fieldCount",
                                                       path="$.subject.fieldCount",
                                                       type="integer", ui_kind="number",
                                                       assertable=True),
                                     DeclarationEntry(name="id", path="$.subject.id",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="method",
                                                       path="$.subject.method",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="name", path="$.subject.name",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="path", path="$.subject.path",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="version",
                                                       path="$.subject.version",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                 ]
                ),
                DeclarationEntry(name="trails", path="$.trails", type="array",
                                  ui_kind="json", assertable=True, children=[
                                     DeclarationEntry(name="kind", path="$.trails.kind",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="path", path="$.trails.path",
                                                       type="array", ui_kind="json",
                                                       required=True, assertable=True),
                                 ]
                ),
            ]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="endpoints",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
