"""fin.monthly_reconciliation.list —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): main_name, update_by, update_time, from, order_customer, sort_field, sort_order
溯源统计: frontend=17, derived=6, builtin=4 | fe_high=17, enum=1
"""
from typing import Final

from gimbal_plate.systems.fin.system_info import (
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
    ValueSource,
)

MONTHLY_RECONCILIATION_LIST: Final[EndpointSpec] = EndpointSpec(
    id='fin.monthly_reconciliation.list',
    system='fin',
    service='fin-service',
    name='MonthlyReconciliation.list',
    description='MonthlyReconciliation.list' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/operation/monthlyReconciliation/list',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='batch_code', path=f'$.batch_code', type='string', state='form', ui_kind='text', description='对账批次ID'),
            DeclarationEntry(name='customer_name', path=f'$.customer_name', type='string', state='form', ui_kind='text', description='下单客户名称'),
            DeclarationEntry(name='booking_opt_branch', path=f'$.booking_opt_branch', type='string', state='form', ui_kind='text', description='订舱供应商'),
            DeclarationEntry(name='main_name', path=f'$.main_name', type='string', state='form', ui_kind='text', description='结算主体'),  # zh_ambiguous
            DeclarationEntry(name='bl_no', path=f'$.bl_no', type='string', state='form', ui_kind='text', description='提单号'),
            DeclarationEntry(name='update_by', path=f'$.update_by', type='string', state='form', ui_kind='text', description='更新人'),  # zh_ambiguous
            DeclarationEntry(name='update_time', path=f'$.update_time', type='integer', state='carry', ui_kind='text', default='0', description='更新时间'),  # zh_ambiguous
            DeclarationEntry(name='bl_nos', path=f'$.bl_nos', type='string', state='form', ui_kind='text', description='提单号批量'),
            DeclarationEntry(name='schedule_actual_delivery_date', path=f'$.schedule_actual_delivery_date', type='integer', state='carry', ui_kind='text', default='0', description='实际开航时间'),
            DeclarationEntry(name='settlement_date', path=f'$.settlement_date', type='string', state='carry', ui_kind='text', default='10', description='应结算日期'),
            DeclarationEntry(name='batch_status', path=f'$.batch_status', type='string', state='form', ui_kind='select', description='批次对账状态'),
            DeclarationEntry(name='from', path=f'$.from', type='integer', state='carry', ui_kind='select', default='0', description='订单来源'),  # zh_ambiguous
            DeclarationEntry(name='order_no', path=f'$.order_no', type='string', state='carry', ui_kind='text', description='订单号'),
            DeclarationEntry(name='order_customer', path=f'$.order_customer', type='string', state='carry', ui_kind='text', description='客户名称'),  # needs_capture:value_source
            DeclarationEntry(name='order_opt_operation', path=f'$.order_opt_operation', type='string', state='carry', ui_kind='select', description='履约操作姓名'),
            DeclarationEntry(name='upload_file_time', path=f'$.upload_file_time', type='integer', state='carry', ui_kind='text', default='0', description='对账单上传日期'),
            DeclarationEntry(name='ou_time', path=f'$.ou_time', type='string', state='carry', ui_kind='text', description='最新状态日期'),
            DeclarationEntry(name='page_no', path=f'$.page_no', type='string', state='form', ui_kind='text', required=True, description='页码'),
            DeclarationEntry(name='page_size', path=f'$.page_size', type='string', state='form', ui_kind='text', required=True, description='每页条数'),
            DeclarationEntry(name='update_time_start', path=f'$.update_time_start', type='string', state='form', ui_kind='text', description='更新时间开始'),
            DeclarationEntry(name='update_time_end', path=f'$.update_time_end', type='string', state='form', ui_kind='text', description='更新时间结束'),
            DeclarationEntry(name='schedule_actual_delivery_date_start', path=f'$.schedule_actual_delivery_date_start', type='string', state='form', ui_kind='text', description='实际开航时间开始'),
            DeclarationEntry(name='schedule_actual_delivery_date_end', path=f'$.schedule_actual_delivery_date_end', type='string', state='form', ui_kind='text', description='实际开航时间结束'),
            DeclarationEntry(name='settlement_date_start', path=f'$.settlement_date_start', type='string', state='form', ui_kind='text', description='应结算日期开始'),
            DeclarationEntry(name='settlement_date_end', path=f'$.settlement_date_end', type='string', state='form', ui_kind='text', description='应结算日期结束'),
            DeclarationEntry(name='sort_field', path=f'$.sort_field', type='string', state='carry', ui_kind='text', required=True, description='排序字段'),  # needs_capture:value_source
            DeclarationEntry(name='sort_order', path=f'$.sort_order', type='string', state='carry', ui_kind='select', required=True, description='排序方向', enum=['asc', 'desc']),  # needs_capture:enum_required
        ],
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description='成功(信封统一;data 行形状归场景用例)',
            declarations=[
            DeclarationEntry(name='code', path='$.code', type='number',
                             required=False, ui_kind='number',
                             description='业务状态码(200=成功)', assertable=True),
            DeclarationEntry(name='msg', path='$.msg', type='string',
                             required=False, ui_kind='text',
                             description='业务提示信息', assertable=True),
            DeclarationEntry(name='data', path='$.data', type='object',
                             required=False, ui_kind='json',
                             description='业务数据(行形状归场景用例)', assertable=True),
            DeclarationEntry(name='request_id', path='$.request_id', type='string',
                             required=False, ui_kind='text',
                             description='请求追踪ID', assertable=True),

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
