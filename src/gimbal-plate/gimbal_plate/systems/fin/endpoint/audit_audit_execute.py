"""fin.audit.audit_execute —— 执行审批接口契约。在 scen_test_14 中出现2次。"""
from gimbal_plate.schema.endpoint import (
    ApiSpec,
    EndpointSpec,
    IOFieldBinding,
    RequestSpec,
    ResponseSpec,
)


AUDIT_AUDIT_EXECUTE = EndpointSpec(
    id="fin.audit.audit_execute",
    system="fin",
    service="audit",
    name="执行审批",
    description="由 Scenario_Test_14 提取: 执行审批",
    api=ApiSpec(service="audit", method="POST", path="/api/home/audit/auditExecute", auth="bearer", timeout_seconds=30.0),
    request=RequestSpec(
        body_type="json",
        fields=[
        IOFieldBinding(name='audit_ids', path='audit_ids', required=True, example=[''], ui_kind='json'),
        IOFieldBinding(name='audit_status', path='audit_status', required=True, example=2, ui_kind='number'),
        IOFieldBinding(name='audit_remark', path='audit_remark', required=True, example=None, ui_kind='text'),
        ],
        schema_={},
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="成功",
        ),
    },
    version="1.0.0",
)
