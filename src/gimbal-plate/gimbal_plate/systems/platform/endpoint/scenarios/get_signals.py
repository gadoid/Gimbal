"""platform.scenarios.get_signals —— Scenario Signals

`GET /api/scenarios/signals`

批量健康趋势(M5,§7 M5-2):``?ids=a,b,c``(≤20,对齐关注上限)
→ 每场景 {trend(近5,旧→新), lastRun}。

口径与前端 useScenarioRuns.trend 逐字对齐:我的来源锁**默认方案**
的执行;公共原件锁自身全部(验证执行);执行池 = 调用者自己的
(owner 隔离,同 GET /executions)。一次 SQL 圈全集,替换关注页
每对象一次 listExecutions 的 N+1。

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

SCENARIOS_GET_SIGNALS: Final[EndpointSpec] = EndpointSpec(
    id="platform.scenarios.get_signals",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Scenario Signals",
    description="批量健康趋势(M5,§7 M5-2):``?ids=a,b,c``(≤20,对齐关注上限)\n→ 每场景 {trend(近5,旧→新), lastRun}。\n\n口径与前端 useScenarioRuns.trend 逐字对齐:我的来源锁**默认方案**\n的执行;公共原件锁自身全部(验证执行);执行池 = 调用者自己的\n(owner 隔离,同 GET /executions)。一次 SQL 圈全集,替换关注页\n每对象一次 listExecutions 的 N+1。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/scenarios/signals",
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
        module="scenarios",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
