"""fin.audit.audit_page —— 查询待审批记录接口契约。在 scen_test_14 中出现2次。"""
from gimbal_plate.schema.endpoint import (
    ApiSpec,
    EndpointSpec,
    IOFieldBinding,
    RequestSpec,
    ResponseSpec,
)


AUDIT_AUDIT_PAGE = EndpointSpec(
    id="fin.audit.audit_page",
    system="fin",
    service="audit",
    name="查询待审批记录",
    description="由 Scenario_Test_14 提取: 查询待审批记录",
    api=ApiSpec(service="audit", method="POST", path="/api/home/audit/auditPage", auth="bearer", timeout_seconds=30.0),
    request=RequestSpec(
        body_type="json",
        fields=[
        IOFieldBinding(name='page_no', path='page_no', required=True, example=1, ui_kind='number'),
        IOFieldBinding(name='page_size', path='page_size', required=True, example=20, ui_kind='number'),
        IOFieldBinding(name='active_tab', path='active_tab', required=True, example='examine_wait', ui_kind='text'),
        IOFieldBinding(name='sort_field', path='sort_field', required=True, example='expedite_num', ui_kind='text'),
        IOFieldBinding(name='sort_order', path='sort_order', required=True, example='desc', ui_kind='text'),
        IOFieldBinding(name='params', path='params', required=True, example={}, ui_kind='json'),
        ],
        schema_={},
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="成功",
            fields=[
        IOFieldBinding(name='audit_id', path='$.data.data[0].audit_id', required=False, ui_kind="unknown"),
            ],
            assertable_fields=['$.data.data[0].audit_id'],
        ),
    },
    version="1.0.0",
)
