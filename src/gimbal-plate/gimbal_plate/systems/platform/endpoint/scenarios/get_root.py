"""platform.scenarios.get_root —— List Scenarios

`GET /api/scenarios`

列表(Page 信封 + M1 响应投影,PG迁移方案 §4.1/§7 M1)。

读侧收紧:admin 全量;普通用户 = public + 自己的。可选
``visibility=public|private`` 再过滤一层,供前端"公共 / 我的"分组
标签使用。

属主过滤直接在 store 已加载的行上做(此前为 readable_ids 再跑
一趟全表投影,单请求双全表扫描)。

多值筛选参数(system/module/priority/tag/author)收逗号联合字符串,
语义与前端 ``utils/filters.ts`` 对齐(system/tag=OR 携带,其余精确
命中其一);``updated_within`` 锚 DB 行 updated_at。排序服务端定死
``updated_at DESC``(§4.1,不接受任意 sort)。分页在 Python 侧切片
——M1 的服务端查询仍全表加载 payload,SQL 端过滤/排序是 M3 的事。
``fields=options`` 返回轻量元数据形态(选择器/名称映射专用)。

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

SCENARIOS_GET_ROOT: Final[EndpointSpec] = EndpointSpec(
    id="platform.scenarios.get_root",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="List Scenarios",
    description="列表(Page 信封 + M1 响应投影,PG迁移方案 §4.1/§7 M1)。\n\n读侧收紧:admin 全量;普通用户 = public + 自己的。可选\n``visibility=public|private`` 再过滤一层,供前端\"公共 / 我的\"分组\n标签使用。\n\n属主过滤直接在 store 已加载的行上做(此前为 readable_ids 再跑\n一趟全表投影,单请求双全表扫描)。\n\n多值筛选参数(system/module/priority/tag/author)收逗号联合字符串,\n语义与前端 ``utils/filters.ts`` 对齐(system/tag=OR 携带,其余精确\n命中其一);``updated_within`` 锚 DB 行 updated_at。排序服务端定死\n``updated_at DESC``(§4.1,不接受任意 sort)。分页在 Python 侧切片\n——M1 的服务端查询仍全表加载 payload,SQL 端过滤/排序是 M3 的事。\n``fields=options`` 返回轻量元数据形态(选择器/名称映射专用)。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/scenarios",
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
                                  assertable=True, children=[
                                     DeclarationEntry(name="dataSetCount",
                                                       path="$.items.dataSetCount",
                                                       type="integer", ui_kind="number",
                                                       assertable=True),
                                     DeclarationEntry(name="meta", path="$.items.meta",
                                                       type="object", ui_kind="json",
                                                       required=True,
                                                       description="Scenario metadata; one Scenario has exactly one Meta.",
                                                       assertable=True, children=[
                                                          DeclarationEntry(name="author",
                                                                            path="$.items.meta.author",
                                                                            type="string",
                                                                            ui_kind="text",
                                                                            assertable=True),
                                                          DeclarationEntry(name="createTime",
                                                                            path="$.items.meta.createTime",
                                                                            type="string",
                                                                            ui_kind="text",
                                                                            assertable=True),
                                                          DeclarationEntry(name="description",
                                                                            path="$.items.meta.description",
                                                                            type="string",
                                                                            ui_kind="text",
                                                                            assertable=True),
                                                          DeclarationEntry(name="expire",
                                                                            path="$.items.meta.expire",
                                                                            type="boolean",
                                                                            ui_kind="boolean",
                                                                            assertable=True),
                                                          DeclarationEntry(name="module",
                                                                            path="$.items.meta.module",
                                                                            type="string",
                                                                            ui_kind="text",
                                                                            required=True,
                                                                            assertable=True),
                                                          DeclarationEntry(name="name",
                                                                            path="$.items.meta.name",
                                                                            type="string",
                                                                            ui_kind="text",
                                                                            required=True,
                                                                            assertable=True),
                                                          DeclarationEntry(name="owner",
                                                                            path="$.items.meta.owner",
                                                                            type="string",
                                                                            ui_kind="text",
                                                                            assertable=True),
                                                          DeclarationEntry(name="priority",
                                                                            path="$.items.meta.priority",
                                                                            type="integer",
                                                                            ui_kind="number",
                                                                            required=True,
                                                                            assertable=True),
                                                          DeclarationEntry(name="scenarioId",
                                                                            path="$.items.meta.scenarioId",
                                                                            type="string",
                                                                            ui_kind="text",
                                                                            required=True,
                                                                            assertable=True),
                                                          DeclarationEntry(name="system",
                                                                            path="$.items.meta.system",
                                                                            type="array",
                                                                            ui_kind="json",
                                                                            assertable=True),
                                                          DeclarationEntry(name="tags",
                                                                            path="$.items.meta.tags",
                                                                            type="array",
                                                                            ui_kind="json",
                                                                            assertable=True),
                                                          DeclarationEntry(name="updateTime",
                                                                            path="$.items.meta.updateTime",
                                                                            type="string",
                                                                            ui_kind="text",
                                                                            assertable=True),
                                                          DeclarationEntry(name="version",
                                                                            path="$.items.meta.version",
                                                                            type="string",
                                                                            ui_kind="text",
                                                                            assertable=True),
                                                      ]
                                     ),
                                     DeclarationEntry(name="schemeCount",
                                                       path="$.items.schemeCount",
                                                       type="integer", ui_kind="number",
                                                       assertable=True),
                                     DeclarationEntry(name="starred",
                                                       path="$.items.starred",
                                                       type="boolean", ui_kind="boolean",
                                                       assertable=True),
                                     DeclarationEntry(name="stepCount",
                                                       path="$.items.stepCount",
                                                       type="integer", ui_kind="number",
                                                       assertable=True),
                                     DeclarationEntry(name="tags", path="$.items.tags",
                                                       type="array", ui_kind="json",
                                                       assertable=True),
                                     DeclarationEntry(name="varCount",
                                                       path="$.items.varCount",
                                                       type="integer", ui_kind="number",
                                                       assertable=True),
                                     DeclarationEntry(name="visibility",
                                                       path="$.items.visibility",
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
        module="scenarios",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
