"""fin.audit.audit_page —— 查询待审批记录接口契约。在 scen_test_14 中出现2次。"""

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


AUDIT_AUDIT_PAGE: Final[EndpointSpec] = EndpointSpec(
    id="fin.audit.audit_page",
    system=FIN_SYSTEM,
    service="fin-service",
    name="查询待审批记录",
    description="由 Scenario_Test_14 提取: 查询待审批记录",
    api=ApiSpec(service="fin-service", method="POST", path="/api/home/audit/auditPage", auth="bearer", timeout_seconds=30.0),
    request=RequestSpec(
        body_type="json",
        declarations=[
        DeclarationEntry(name='page_no', path='page_no', channel='binding', required=True, example=1, ui_kind='number', description='页码,从 1 开始'),
        DeclarationEntry(name='page_size', path='page_size', channel='binding', required=True, example=20, ui_kind='number', description='每页条数,默认 20'),
        DeclarationEntry(name='active_tab', path='active_tab', channel='binding', required=True, example='examine_wait', ui_kind='text', description='审批页签: examine_wait=待审批 / examine_done=已审批'),
        DeclarationEntry(name='sort_field', path='sort_field', channel='binding', required=True, example='expedite_num', ui_kind='text', description='排序字段,如 expedite_num(催办次数)'),
        DeclarationEntry(name='sort_order', path='sort_order', channel='binding', required=True, example='desc', ui_kind='text', description='排序方向: asc / desc', enum=['asc', 'desc']),
        DeclarationEntry(name='params', path='params', channel='binding', required=True, example={}, ui_kind='json', description='业务过滤条件,如单号/客户/日期范围'),
        ],
        # schema 携带的非绑定字段(Type C):不生成声明条目,
        # 前端「其他字段」折叠区以「契约」行渲染 — 可编辑,编辑后随请求发送。
        schema_={
            "type": "object",
            "properties": {
                "risk_note": {
                    "type": "string",
                    "description": "演示:plate 契约携带的非绑定字段",
                    "default": "正常",
                },
            },
        },
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="成功",
            declarations=[
        DeclarationEntry(name='audit_id', path='$.data.data[0].audit_id', channel='view_only', required=False, ui_kind="unknown", assertable=True),
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
