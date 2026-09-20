"""fin.order_order.order_sub_export —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): customer_id, order_no, status, service_project, customer_put_date, create_time, currency, fee_type, fund_code, create_id, invoice_number, put_settle_object_id, main_id, pay_settle_object_id, fee_lock_status, pay_account_status, pay_invoice_status, pay_writeoff_status, receive_account_no, account_batch_name, account_status, invoice_status, writeoff_status, track_bl_no, discount_status
溯源统计: frontend=53, lang=28, derived=12, column=7, 无zh=1 | fe_high=68, enum=0
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

ORDER_ORDER_SUB_EXPORT: Final[EndpointSpec] = EndpointSpec(
    id='fin.order_order.order_sub_export',
    system='fin',
    service='fin-service',
    name='Order.orderSubExport',
    description='Order.orderSubExport' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/order/order/orderSubExport',
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
            DeclarationEntry(name='fund_code', path=f'$.fund_code', type='string', state='carry', ui_kind='select', description='资方'),  # zh_ambiguous
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='form', ui_kind='select', default='0', description='创建人'),  # zh_ambiguous
            DeclarationEntry(name='contain_fee_type', path=f'$.contain_fee_type', type='string', state='carry', ui_kind='select', description='包含费用类型'),
            DeclarationEntry(name='invoice_number', path=f'$.invoice_number', type='string', state='carry', ui_kind='text', description='发票号'),  # needs_capture:value_source
            DeclarationEntry(name='payment_type', path=f'$.payment_type', type='integer', state='carry', ui_kind='select', default='0', description='费用付款类型'),
            DeclarationEntry(name='track_bl_nos', path=f'$.track_bl_nos', type='string', state='form', ui_kind='text', description='提单号(运踪)批量'),
            DeclarationEntry(name='business_no', path=f'$.business_no', type='string', state='form', ui_kind='text', description='业务编号'),
            DeclarationEntry(name='put_settle_object_id', path=f'$.put_settle_object_id', type='integer', state='form', ui_kind='text', default='0', description='应收结算对象'),  # zh_ambiguous
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='form', ui_kind='select', default='0', description='费用主体'),  # zh_ambiguous
            DeclarationEntry(name='pay_settle_object_id', path=f'$.pay_settle_object_id', type='integer', state='form', ui_kind='text', default='0', description='应付结算对象'),  # zh_ambiguous
            DeclarationEntry(name='real_fee_status', path=f'$.real_fee_status', type='integer', state='form', ui_kind='select', default='0', description='业务订单状态'),
            DeclarationEntry(name='fee_lock_status', path=f'$.fee_lock_status', type='integer', state='form', ui_kind='select', default='0', description='费用状态'),  # zh_ambiguous
            DeclarationEntry(name='atd', path=f'$.atd', type='integer', state='carry', ui_kind='text', default='0', description='实际开航日'),
            DeclarationEntry(name='finance_date', path=f'$.finance_date', type='integer', state='carry', ui_kind='text', default='0', description='财务日期'),
            DeclarationEntry(name='client_expand_id', path=f'$.client_expand_id', type='integer', state='carry', ui_kind='select', default='0', description='直客拓展'),
            DeclarationEntry(name='sale_id', path=f'$.sale_id', type='integer', state='form', ui_kind='select', default='0', description='销售'),
            DeclarationEntry(name='is_loan_before_invoice', path=f'$.is_loan_before_invoice', type='integer', state='form', ui_kind='select', default='0', description='未放款开票申请'),
            DeclarationEntry(name='is_special_pay', path=f'$.is_special_pay', type='integer', state='form', ui_kind='select', default='0', description='供应商垫付申请'),
            DeclarationEntry(name='put_account_status', path=f'$.put_account_status', type='integer', state='form', ui_kind='select', description='应收对账状态'),
            DeclarationEntry(name='put_invoice_status', path=f'$.put_invoice_status', type='integer', state='form', ui_kind='select', description='应收开票状态'),
            DeclarationEntry(name='put_writeoff_status', path=f'$.put_writeoff_status', type='integer', state='form', ui_kind='select', description='应收核销状态'),
            DeclarationEntry(name='pay_account_status', path=f'$.pay_account_status', type='integer', state='form', ui_kind='select', default='0', description='应付对账状态'),  # zh_ambiguous
            DeclarationEntry(name='pay_invoice_status', path=f'$.pay_invoice_status', type='integer', state='form', ui_kind='select', description='应付开票状态'),  # zh_ambiguous
            DeclarationEntry(name='pay_writeoff_status', path=f'$.pay_writeoff_status', type='integer', state='form', ui_kind='select', default='1', description='应付核销状态'),  # zh_ambiguous
            DeclarationEntry(name='pay_invoice_batch_no', path=f'$.pay_invoice_batch_no', type='string', state='carry', ui_kind='text', description='开票批次ID'),
            DeclarationEntry(name='batch_apply_name', path=f'$.batch_apply_name', type='string', state='carry', ui_kind='text', description='开票申请名称'),
            DeclarationEntry(name='link_role', path=f'$.link_role', type='integer', state='carry', ui_kind='select', default='0', description='关联身份'),
            DeclarationEntry(name='link_apply_no', path=f'$.link_apply_no', type='string', state='carry', ui_kind='text', description='关联对向申请ID'),
            DeclarationEntry(name='batch_status', path=f'$.batch_status', type='string', state='carry', ui_kind='select', description='批次状态'),
            DeclarationEntry(name='receive_account_no', path=f'$.receive_account_no', type='string', state='carry', ui_kind='text', description='对账批次ID'),  # needs_capture:value_source
            DeclarationEntry(name='account_batch_name', path=f'$.account_batch_name', type='string', state='carry', ui_kind='text', description='对账批次名称'),  # needs_capture:value_source
            DeclarationEntry(name='etd', path=f'$.etd', type='integer', state='carry', ui_kind='text', default='0', description='预计开航日'),
            DeclarationEntry(name='batch_identity', path=f'$.batch_identity', type='string', state='carry', ui_kind='select', description='批次身份'),
            DeclarationEntry(name='main_batch_no', path=f'$.main_batch_no', type='string', state='carry', ui_kind='text', description='对账主批次ID'),
            DeclarationEntry(name='account_status', path=f'$.account_status', type='integer', state='carry', ui_kind='select', default='0', description='对账轮次状态'),  # zh_ambiguous
            DeclarationEntry(name='account_by', path=f'$.account_by', type='integer', state='carry', ui_kind='select', description='对账完成人'),
            DeclarationEntry(name='account_time', path=f'$.account_time', type='integer', state='carry', ui_kind='text', description='对账完成时间'),
            DeclarationEntry(name='receive_invoice_apply_no', path=f'$.receive_invoice_apply_no', type='string', state='carry', ui_kind='text', description='开票申请ID'),
            DeclarationEntry(name='receive_invoice_batch_no', path=f'$.receive_invoice_batch_no', type='string', state='carry', ui_kind='text', description='开票批次ID'),
            DeclarationEntry(name='cancel_status', path=f'$.cancel_status', type='integer', state='carry', ui_kind='select', description='开票申请状态'),
            DeclarationEntry(name='invoice_apply_name', path=f'$.invoice_apply_name', type='string', state='carry', ui_kind='text', description='开票申请名称'),
            DeclarationEntry(name='link_batch_no', path=f'$.link_batch_no', type='string', state='carry', ui_kind='text', description='关联对向批次ID'),
            DeclarationEntry(name='invoice_status', path=f'$.invoice_status', type='integer', state='carry', ui_kind='select', default='0', description='登记状态'),  # zh_ambiguous
            DeclarationEntry(name='invoice_no', path=f'$.invoice_no', type='string', state='carry', ui_kind='text', description='关联发票号'),
            DeclarationEntry(name='writeoff_status', path=f'$.writeoff_status', type='integer', state='carry', ui_kind='select', default='1', description='核销状态'),  # zh_ambiguous
            DeclarationEntry(name='order_sub_ids', path=f'$.order_sub_ids', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='track_bl_no', path=f'$.track_bl_no', type='string', state='form', ui_kind='text', description='运踪提单号'),  # zh_ambiguous
            DeclarationEntry(name='is_traverse', path=f'$.is_traverse', type='integer', state='form', ui_kind='number', default='0', description='是否生成子订单'),
            DeclarationEntry(name='book_supplier_id', path=f'$.book_supplier_id', type='integer', state='form', ui_kind='number', default='0', description='订舱供应商'),
            DeclarationEntry(name='policy_id', path=f'$.policy_id', type='integer', state='form', ui_kind='number', description='服务策略'),
            DeclarationEntry(name='service_items', path=f'$.service_items', type='string', state='form', ui_kind='text', description='服务项目'),
            DeclarationEntry(name='business_type', path=f'$.business_type', type='string', state='form', ui_kind='text', description='业务类型'),
            DeclarationEntry(name='carrier', path=f'$.carrier', type='string', state='form', ui_kind='text', description='承运人'),
            DeclarationEntry(name='etd_start', path=f'$.etd_start', type='string', state='form', ui_kind='text', description='预计开航日开始'),
            DeclarationEntry(name='etd_end', path=f'$.etd_end', type='string', state='form', ui_kind='text', description='预计开航日结束'),
            DeclarationEntry(name='atd_start', path=f'$.atd_start', type='string', state='form', ui_kind='text', description='实际开航日开始'),
            DeclarationEntry(name='atd_end', path=f'$.atd_end', type='string', state='form', ui_kind='text', description='实际开航日结束'),
            DeclarationEntry(name='finance_date_start', path=f'$.finance_date_start', type='string', state='form', ui_kind='text', description='财务日期开始'),
            DeclarationEntry(name='finance_date_end', path=f'$.finance_date_end', type='string', state='form', ui_kind='text', description='财务日期结束'),
            DeclarationEntry(name='volume', path=f'$.volume', type='string', state='form', ui_kind='text', description='箱型箱量'),
            DeclarationEntry(name='ship_name', path=f'$.ship_name', type='string', state='form', ui_kind='text', description='船名'),
            DeclarationEntry(name='voy', path=f'$.voy', type='string', state='form', ui_kind='text', description='航次'),
            DeclarationEntry(name='pol', path=f'$.pol', type='string', state='form', ui_kind='text', description='起运港'),
            DeclarationEntry(name='del', path=f'$.del', type='string', state='form', ui_kind='text', description='目的地'),
            DeclarationEntry(name='customer_put_date_start', path=f'$.customer_put_date_start', type='string', state='form', ui_kind='text', description='客户应收日开始'),
            DeclarationEntry(name='customer_put_date_end', path=f'$.customer_put_date_end', type='string', state='form', ui_kind='text', description='客户应收日结束'),
            DeclarationEntry(name='book_supplier_pay_date_start', path=f'$.book_supplier_pay_date_start', type='string', state='form', ui_kind='text', description='供应商应付日开始'),
            DeclarationEntry(name='book_supplier_pay_date_end', path=f'$.book_supplier_pay_date_end', type='string', state='form', ui_kind='text', description='供应商应付日结束'),
            DeclarationEntry(name='discount_rule', path=f'$.discount_rule', type='string', state='form', ui_kind='text', description='折扣规则'),
            DeclarationEntry(name='discount_currency', path=f'$.discount_currency', type='string', state='form', ui_kind='text', description='折扣币种'),
            DeclarationEntry(name='discount_status', path=f'$.discount_status', type='integer', state='form', ui_kind='number', default='2', description='折扣标识   0正常  1异常  2全不参与补贴 3不符合的折扣规则 4折扣规则过期 5未维护ATD'),  # zh_ambiguous
            DeclarationEntry(name='is_delayed_recovery', path=f'$.is_delayed_recovery', type='integer', state='form', ui_kind='number', default='0', description='是否超期回款 1是'),
            DeclarationEntry(name='service_id', path=f'$.service_id', type='integer', state='form', ui_kind='number', default='0', description='客服'),
            DeclarationEntry(name='operator_id', path=f'$.operator_id', type='integer', state='form', ui_kind='number', default='0', description='操作人'),
            DeclarationEntry(name='is_fee_miss', path=f'$.is_fee_miss', type='integer', state='form', ui_kind='number', default='0', description='是否费用缺失 1是'),
            DeclarationEntry(name='cancel_remark', path=f'$.cancel_remark', type='string', state='form', ui_kind='text', description='作废原因'),
            DeclarationEntry(name='create_time_start', path=f'$.create_time_start', type='string', state='form', ui_kind='text', description='业务订单创建时间开始'),
            DeclarationEntry(name='create_time_end', path=f'$.create_time_end', type='string', state='form', ui_kind='text', description='业务订单创建时间结束'),
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
