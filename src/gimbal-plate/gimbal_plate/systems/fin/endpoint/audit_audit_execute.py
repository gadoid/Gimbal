"""fin.audit.audit_execute —— 执行审批接口契约。在 scen_test_14 中出现2次。"""

from typing import Final

from gimbal_plate.systems.fin.system_info import (
    FIN_DEFAULT_AUTHOR,
    FIN_DEFAULT_MODULE,
    FIN_DEFAULT_OWNER,
    FIN_DEFAULT_PRIORITY,
    FIN_DEFAULT_TAGS,
    FIN_DEFAULT_VERSION,
    FIN_SYSTEM,
)
from gimbal_plate.schema.endpoint import (
    ApiSpec,
    EndpointSpec,
    DeclarationEntry,
    RequestSpec,
    ResponseSpec,
    EndpointMetadata,
)


AUDIT_AUDIT_EXECUTE: Final[EndpointSpec] = EndpointSpec(
    id="fin.audit.audit_execute",
    system=FIN_SYSTEM,
    service="fin-service",
    name="执行审批",
    description="由 Scenario_Test_14 提取: 执行审批",
    api=ApiSpec(service="fin-service", method="POST", path="/api/home/audit/auditExecute", auth="bearer", timeout_seconds=30.0),
    request=RequestSpec(
        body_type="json",
        declarations=[
        DeclarationEntry(name='audit_ids', path='audit_ids', type='array', required=True, example=[''], ui_kind='json'),
        DeclarationEntry(name='audit_status', path='audit_status', type='integer', required=True, example=2, ui_kind='number'),
        DeclarationEntry(name='audit_remark', path='audit_remark', type='string', required=True, example=None, ui_kind='text'),
        ],
        
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="成功",
        ),
    },
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module=FIN_DEFAULT_MODULE,
        owner=FIN_DEFAULT_OWNER,
        tags=list(FIN_DEFAULT_TAGS),
    ),
)
