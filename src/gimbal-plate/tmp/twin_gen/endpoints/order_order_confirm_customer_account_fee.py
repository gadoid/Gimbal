"""fin.order_order.confirm_customer_account_fee —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): customer_id, order_no, status, service_project, customer_put_date, create_time, currency, fee_type, fund_code, create_id, invoice_number
溯源统计: frontend=20, lang=8, builtin=2, derived=1 | fe_high=28, enum=0
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

ORDER_CONFIRM_CUSTOMER_ACCOUNT_FEE: Final[EndpointSpec] = EndpointSpec(
    id='fin.order_order.confirm_customer_account_fee',
    system='fin',
    service='fin-service',
    name='Order.confirmCustomerAccountFee',
    description='Order.confirmCustomerAccountFee' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/order/order/confirmCustomerAccountFee',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', ui_kind='select', default='0', description='下单客户'),  # zh_ambiguous
            DeclarationEntry(name='order_module', path=f'$.order_module', type='string', state='carry', ui_kind='select', description='模块名称'),
            DeclarationEntry(name='bl_no', path=f'$.bl_no', type='string', state='form', ui_kind='text', description='提单号'),
            DeclarationEntry(name='order_no', path=f'$.order_no', type='string', state='form', ui_kind='text', description='业务订单ID'),  # zh_ambiguous
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='form', ui_kind='select', default='2', description='订单状态'),  # zh_ambiguous
            DeclarationEntry(name='service_project', path=f'$.service_project', type='string', state='carry', ui_kind='select', description='服务项目'),  # zh_ambiguous
            DeclarationEntry(name='bl_nos', path=f'$.bl_nos', type='string', state='form', ui_kind='text', description='提单号批量'),
            DeclarationEntry(name='order_sub_no', path=f'$.order_sub_no', type='string', state='form', ui_kind='text', description='子订单ID'),
            DeclarationEntry(name='customer_main_id', path=f'$.customer_main_id', type='integer', state='form', ui_kind='select', default='0', description='对客订单主体'),
            DeclarationEntry(name='business_main_id', path=f'$.business_main_id', type='integer', state='form', ui_kind='select', default='0', description='对商订单主体'),
            DeclarationEntry(name='supplier_id', path=f'$.supplier_id', type='integer', state='form', ui_kind='text', default='0', description='订单包含供应商'),
            DeclarationEntry(name='policy_type', path=f'$.policy_type', type='string', state='form', ui_kind='select', description='政策类型'),
            DeclarationEntry(name='trade_term', path=f'$.trade_term', type='string', state='form', ui_kind='select', description='成交方式'),
            DeclarationEntry(name='customer_period', path=f'$.customer_period', type='integer', state='form', ui_kind='text', description='客户账期'),
            DeclarationEntry(name='customer_put_date', path=f'$.customer_put_date', type='integer', state='carry', ui_kind='text', default='0', description='客户应收日'),  # zh_ambiguous
            DeclarationEntry(name='book_supplier_period', path=f'$.book_supplier_period', type='integer', state='form', ui_kind='text', default='0', description='供应商账期'),
            DeclarationEntry(name='book_supplier_pay_date', path=f'$.book_supplier_pay_date', type='integer', state='carry', ui_kind='text', default='0', description='供应商应付日'),
            DeclarationEntry(name='atd_time', path=f'$.atd_time', type='string', state='carry', ui_kind='text', description='ATD范围'),
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='text', default='0', description='业务订单创建时间'),  # zh_ambiguous
            DeclarationEntry(name='finance_time', path=f'$.finance_time', type='string', state='carry', ui_kind='text', description='财务日期'),
            DeclarationEntry(name='currency', path=f'$.currency', type='string', state='carry', ui_kind='select', description='币制'),  # zh_ambiguous
            DeclarationEntry(name='fee_type', path=f'$.fee_type', type='integer', state='carry', ui_kind='select', default='0', description='费用种类'),  # zh_ambiguous
            DeclarationEntry(name='cost_ids', path=f'$.cost_ids', type='string', state='carry', ui_kind='select', description='费用名称'),
            DeclarationEntry(name='fund_code', path=f'$.fund_code', type='string', state='form', ui_kind='select', description='资方'),  # zh_ambiguous
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='form', ui_kind='select', default='0', description='创建人'),  # zh_ambiguous
            DeclarationEntry(name='contain_fee_type', path=f'$.contain_fee_type', type='string', state='carry', ui_kind='select', description='包含费用类型'),
            DeclarationEntry(name='invoice_number', path=f'$.invoice_number', type='string', state='carry', ui_kind='text', description='发票号'),  # needs_capture:value_source
            DeclarationEntry(name='payment_type', path=f'$.payment_type', type='integer', state='carry', ui_kind='select', default='0', description='费用付款类型'),
            DeclarationEntry(name='order_ids', path=f'$.order_ids', type='string', state='form', ui_kind='text', description='订单ID列表'),
            DeclarationEntry(name='page_no', path=f'$.page_no', type='string', state='form', ui_kind='text', description='页码'),
            DeclarationEntry(name='page_size', path=f'$.page_size', type='string', state='form', ui_kind='text', description='每页条数'),
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
