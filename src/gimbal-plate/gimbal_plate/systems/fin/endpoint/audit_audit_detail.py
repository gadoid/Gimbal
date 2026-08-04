"""fin.audit.audit_detail —— 查询审批详情接口契约。在 scen_test_14 中出现1次。"""
from gimbal_plate.schema.endpoint import (
    ApiSpec,
    EndpointSpec,
    IOFieldBinding,
    RequestSpec,
    ResponseSpec,
)


AUDIT_AUDIT_DETAIL = EndpointSpec(
    id="fin.audit.audit_detail",
    system="fin",
    service="audit",
    name="查询审批详情",
    description="由 Scenario_Test_14 提取: 查询审批详情",
    api=ApiSpec(service="audit", method="POST", path="/api/home/audit/auditDetail", auth="bearer", timeout_seconds=30.0),
    request=RequestSpec(
        body_type="json",
        fields=[
        IOFieldBinding(name='audit_id', path='audit_id', required=True, example='', ui_kind='text'),
        ],
        schema_={},
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="成功",
            fields=[
        IOFieldBinding(name='relation_id', path='$.data.audit_content.relation_id', required=False, ui_kind="unknown"),
            ],
            assertable_fields=['$.data.audit_content.relation_id'],
        ),
    },
    version="1.0.0",
)
