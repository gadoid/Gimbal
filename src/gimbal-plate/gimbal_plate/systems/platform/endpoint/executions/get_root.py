"""platform.executions.get_root —— List Executions

`GET /api/executions`

分页列表(P:此前全量返回,无界)。默认 200 与前端现状兼容。

M1(§4.1):``page``/``page_size`` 是 Page 信封的正参(limit/offset
保留为旧调用兼容;两者并传时 page 优先),信封补齐 page/pageSize。
列表行形态去 ``config``(凭证引用面不随行下发,详情页保留),
只带窄投影 ``configSummary``。

``scenario_id`` 叠加在 owner 过滤之上(前端「上次运行」数据源)。
执行设计 §3.4 增补:``status`` / 发起时间范围(锚 ``created_at``,
queued 单 started_at 可空不作锚)/ ``batch_id``(队列归并视图)筛选。
M4(§6.3):``q`` 下推(scenario_name ILIKE / id 前缀)——列表页
检索框不再拉全量在客户端过滤。

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

EXECUTIONS_GET_ROOT: Final[EndpointSpec] = EndpointSpec(
    id="platform.executions.get_root",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="List Executions",
    description="分页列表(P:此前全量返回,无界)。默认 200 与前端现状兼容。\n\nM1(§4.1):``page``/``page_size`` 是 Page 信封的正参(limit/offset\n保留为旧调用兼容;两者并传时 page 优先),信封补齐 page/pageSize。\n列表行形态去 ``config``(凭证引用面不随行下发,详情页保留),\n只带窄投影 ``configSummary``。\n\n``scenario_id`` 叠加在 owner 过滤之上(前端「上次运行」数据源)。\n执行设计 §3.4 增补:``status`` / 发起时间范围(锚 ``created_at``,\nqueued 单 started_at 可空不作锚)/ ``batch_id``(队列归并视图)筛选。\nM4(§6.3):``q`` 下推(scenario_name ILIKE / id 前缀)——列表页\n检索框不再拉全量在客户端过滤。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/executions",
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
                                  required=True, assertable=True, children=[
                                     DeclarationEntry(name="batch_id",
                                                       path="$.items.batch_id",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="configSummary",
                                                       path="$.items.configSummary",
                                                       type="object", ui_kind="json",
                                                       assertable=True),
                                     DeclarationEntry(name="consecutive_failures",
                                                       path="$.items.consecutive_failures",
                                                       type="integer", ui_kind="number",
                                                       assertable=True),
                                     DeclarationEntry(name="failed", path="$.items.failed",
                                                       type="integer", ui_kind="number",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="finished_at",
                                                       path="$.items.finished_at",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="has_scenario_snapshot",
                                                       path="$.items.has_scenario_snapshot",
                                                       type="boolean", ui_kind="boolean",
                                                       assertable=True),
                                     DeclarationEntry(name="id", path="$.items.id",
                                                       type="integer", ui_kind="number",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="passed", path="$.items.passed",
                                                       type="integer", ui_kind="number",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="scenario_deleted",
                                                       path="$.items.scenario_deleted",
                                                       type="boolean", ui_kind="boolean",
                                                       assertable=True),
                                     DeclarationEntry(name="scenario_display_name",
                                                       path="$.items.scenario_display_name",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="scenario_id",
                                                       path="$.items.scenario_id",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="skipped",
                                                       path="$.items.skipped",
                                                       type="integer", ui_kind="number",
                                                       assertable=True),
                                     DeclarationEntry(name="started_at",
                                                       path="$.items.started_at",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="status", path="$.items.status",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="total_runs",
                                                       path="$.items.total_runs",
                                                       type="integer", ui_kind="number",
                                                       required=True, assertable=True),
                                 ]
                ),
                DeclarationEntry(name="page", path="$.page", type="integer",
                                  ui_kind="number", assertable=True),
                DeclarationEntry(name="pageSize", path="$.pageSize", type="integer",
                                  ui_kind="number", assertable=True),
                DeclarationEntry(name="total", path="$.total", type="integer",
                                  ui_kind="number", required=True, assertable=True),
            ]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="executions",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
