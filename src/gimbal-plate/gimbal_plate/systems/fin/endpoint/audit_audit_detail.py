"""fin.audit.audit_detail —— 查询审批详情接口契约。在 scen_test_14 中出现1次。"""

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


AUDIT_AUDIT_DETAIL: Final[EndpointSpec] = EndpointSpec(
    id="fin.audit.audit_detail",
    system=FIN_SYSTEM,
    service="fin-service",
    name="查询审批详情",
    description="由 Scenario_Test_14 提取: 查询审批详情",
    api=ApiSpec(service="fin-service", method="POST", path="/api/home/audit/auditDetail", auth="bearer", timeout_seconds=30.0),
    request=RequestSpec(
        body_type="json",
        declarations=[
        DeclarationEntry(name='audit_id', path='audit_id', type='string', required=True, example='', ui_kind='text'),
        ],
        
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="成功",
            declarations=[
        DeclarationEntry(name='relation_id', path='$.data.audit_content.relation_id', type='string', required=False, ui_kind="unknown", assertable=True),
            ],
        ),
    },
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module=FIN_DEFAULT_MODULE,
        owner=FIN_DEFAULT_OWNER,
        tags=list(FIN_DEFAULT_TAGS),
    ),
)
