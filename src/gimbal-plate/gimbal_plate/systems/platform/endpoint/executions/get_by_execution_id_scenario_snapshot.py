"""platform.executions.get_by_execution_id_scenario_snapshot —— Get Scenario Snapshot

`GET /api/executions/{execution_id}/scenario-snapshot`

执行时的场景 draft 容器({definition, orchestration})原样返回。

dispatch 同拍快照(见 run_dispatcher._create_execution)— 场景此后
被编辑不影响本端点内容。原样透传、不经 ScenarioDraft 重校验:快照是
历史事实,schema 漂移不应让旧快照不可读(与 GET /scenarios/{id}/draft
的校验语义不同,那是对"活草稿"的校验)。存量行无快照 → 404 带明确
code(前端据此区分"无快照"与"无权限",两者对用户都呈现为不可导出)。

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

EXECUTIONS_GET_BY_EXECUTION_ID_SCENARIO_SNAPSHOT: Final[EndpointSpec] = EndpointSpec(
    id="platform.executions.get_by_execution_id_scenario_snapshot",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Get Scenario Snapshot",
    description="执行时的场景 draft 容器({definition, orchestration})原样返回。\n\ndispatch 同拍快照(见 run_dispatcher._create_execution)— 场景此后\n被编辑不影响本端点内容。原样透传、不经 ScenarioDraft 重校验:快照是\n历史事实,schema 漂移不应让旧快照不可读(与 GET /scenarios/{id}/draft\n的校验语义不同,那是对\"活草稿\"的校验)。存量行无快照 → 404 带明确\ncode(前端据此区分\"无快照\"与\"无权限\",两者对用户都呈现为不可导出)。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/executions/{execution_id}/scenario-snapshot",
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
        module="executions",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
