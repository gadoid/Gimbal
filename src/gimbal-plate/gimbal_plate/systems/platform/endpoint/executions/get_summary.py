"""platform.executions.get_summary —— Executions Summary

`GET /api/executions/summary`

顶部 KPI 带(执行设计 §3.5):Execution 计数器/时间戳就能算的量。

口径 = 查询者自己的执行(owner 隔离,§5.1 — 聚合不得突破个体);
窗口锚 ``created_at``(发起时间;queued/running 单 started_at 可空)。
行级分布(耗时/失败原因)不落库,这里给不了(§0 纪律 3)。

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

EXECUTIONS_GET_SUMMARY: Final[EndpointSpec] = EndpointSpec(
    id="platform.executions.get_summary",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Executions Summary",
    description="顶部 KPI 带(执行设计 §3.5):Execution 计数器/时间戳就能算的量。\n\n口径 = 查询者自己的执行(owner 隔离,§5.1 — 聚合不得突破个体);\n窗口锚 ``created_at``(发起时间;queued/running 单 started_at 可空)。\n行级分布(耗时/失败原因)不落库,这里给不了(§0 纪律 3)。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/executions/summary",
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
                DeclarationEntry(name="activeExecutions", path="$.activeExecutions",
                                  type="integer", ui_kind="number", assertable=True),
                DeclarationEntry(name="avgDurationSec", path="$.avgDurationSec",
                                  type="number", ui_kind="number", assertable=True),
                DeclarationEntry(name="failedRuns", path="$.failedRuns", type="integer",
                                  ui_kind="number", assertable=True),
                DeclarationEntry(name="passRate", path="$.passRate", type="number",
                                  ui_kind="number", assertable=True),
                DeclarationEntry(name="passedRuns", path="$.passedRuns", type="integer",
                                  ui_kind="number", assertable=True),
                DeclarationEntry(name="repeatFailureScenarios",
                                  path="$.repeatFailureScenarios", type="integer",
                                  ui_kind="number", assertable=True),
                DeclarationEntry(name="totalExecutions", path="$.totalExecutions",
                                  type="integer", ui_kind="number", assertable=True),
                DeclarationEntry(name="totalRuns", path="$.totalRuns", type="integer",
                                  ui_kind="number", assertable=True),
                DeclarationEntry(name="windowDays", path="$.windowDays", type="integer",
                                  ui_kind="number", assertable=True),
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
