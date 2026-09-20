"""fin.receive_invoice.invoice_list —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): create_time, invoice_number, invoice_type, invoice_date, currency, writeoff_status, create_id, invoice_status, receive_invoice_apply_no, cancel_time, receive_invoice_batch_no, cancel_status, customer_id, put_settle_object_id, main_id, invoice_no, pay_settle_object_id, pay_invoice_apply_no, bl_no, page_no, page_size, sort_field, sort_order
溯源统计: frontend=20, derived=10, lang=6, column=4, builtin=4, 无zh=3, rule=2 | fe_high=27, enum=1
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

RECEIVE_INVOICE_INVOICE_LIST: Final[EndpointSpec] = EndpointSpec(
    id='fin.receive_invoice.invoice_list',
    system='fin',
    service='fin-service',
    name='ReceiveInvoice.invoiceList',
    description='ReceiveInvoice.invoiceList' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/receiveInvoice/invoiceList',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='receive_settle_object_id', path=f'$.receive_settle_object_id', type='integer', state='form', ui_kind='text', required=True, default='0', description='应收结算对象ID'),
            DeclarationEntry(name='fee_main_id', path=f'$.fee_main_id', type='integer', state='form', ui_kind='select', required=True, default='0', description='费用主ID'),
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='text', default='0', description='创建时间'),  # zh_ambiguous
            DeclarationEntry(name='invoice_number', path=f'$.invoice_number', type='string', state='form', ui_kind='text', description='发票号码'),  # zh_ambiguous
            DeclarationEntry(name='invoice_type', path=f'$.invoice_type', type='string', state='form', ui_kind='select', description='发票类型'),  # zh_ambiguous
            DeclarationEntry(name='invoice_date', path=f'$.invoice_date', type='string', state='carry', ui_kind='text', description='开票日期'),  # zh_ambiguous
            DeclarationEntry(name='currency', path=f'$.currency', type='string', state='form', ui_kind='select', description='发票币制'),  # zh_ambiguous
            DeclarationEntry(name='writeoff_status', path=f'$.writeoff_status', type='integer', state='form', ui_kind='select', default='1', description='核销状态'),  # zh_ambiguous
            DeclarationEntry(name='invoice_use_status', path=f'$.invoice_use_status', type='string', state='form', ui_kind='select', description='发票使用状态'),
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='form', ui_kind='select', default='0', description='创建人'),  # zh_ambiguous
            DeclarationEntry(name='invoice_status', path=f'$.invoice_status', type='integer', state='form', ui_kind='select', default='0', description='发票状态'),  # zh_ambiguous
            DeclarationEntry(name='receive_invoice_apply_no', path=f'$.receive_invoice_apply_no', type='string', state='form', ui_kind='text', description='开票申请ID'),  # zh_ambiguous
            DeclarationEntry(name='cancel_id', path=f'$.cancel_id', type='integer', state='form', ui_kind='select', default='0', description='作废人'),
            DeclarationEntry(name='cancel_time', path=f'$.cancel_time', type='integer', state='carry', ui_kind='text', default='0', description='作废时间'),  # zh_ambiguous
            DeclarationEntry(name='receive_invoice_batch_no', path=f'$.receive_invoice_batch_no', type='string', state='carry', ui_kind='text', description='开票批次ID'),  # zh_ambiguous
            DeclarationEntry(name='cancel_status', path=f'$.cancel_status', type='integer', state='carry', ui_kind='select', description='开票申请状态'),  # zh_ambiguous
            DeclarationEntry(name='bl_nos', path=f'$.bl_nos', type='string', state='carry', ui_kind='text', description='提单号批量'),
            DeclarationEntry(name='invoice_apply_name', path=f'$.invoice_apply_name', type='string', state='carry', ui_kind='text', description='开票申请名称'),
            DeclarationEntry(name='link_role', path=f'$.link_role', type='integer', state='carry', ui_kind='select', default='0', description='关联身份'),
            DeclarationEntry(name='link_batch_no', path=f'$.link_batch_no', type='string', state='carry', ui_kind='text', description='关联对向批次ID'),
            DeclarationEntry(name='link_apply_no', path=f'$.link_apply_no', type='string', state='carry', ui_kind='text', description='关联对向申请ID'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='carry', ui_kind='select', default='0', description='下单客户名称'),  # zh_ambiguous
            DeclarationEntry(name='put_settle_object_id', path=f'$.put_settle_object_id', type='integer', state='carry', ui_kind='select', default='0', description='应收结算对象'),  # zh_ambiguous
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='carry', ui_kind='select', default='0', description='费用主体'),  # zh_ambiguous
            DeclarationEntry(name='invoice_no', path=f'$.invoice_no', type='string', state='form', ui_kind='text', description='关联发票号'),  # zh_ambiguous
            DeclarationEntry(name='pay_settle_object_id', path=f'$.pay_settle_object_id', type='integer', state='carry', ui_kind='text', default='0', description='应付结算对象'),  # zh_ambiguous
            DeclarationEntry(name='pay_invoice_apply_no', path=f'$.pay_invoice_apply_no', type='string', state='carry', ui_kind='text', description='开票申请ID'),  # zh_ambiguous
            DeclarationEntry(name='relation_id', path=f'$.relation_id', type='integer', state='form', ui_kind='number', description='关联ID'),
            DeclarationEntry(name='receive_invoice_ids', path=f'$.receive_invoice_ids', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='check_ids', path=f'$.check_ids', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='invoice_style', path=f'$.invoice_style', type='integer', state='form', ui_kind='number', default='1', description='发票样式 1正式发票 2Debit Note'),
            DeclarationEntry(name='invoice_amount_start', path=f'$.invoice_amount_start', type='string', state='form', ui_kind='text', description='发票金额开始'),
            DeclarationEntry(name='invoice_amount_end', path=f'$.invoice_amount_end', type='string', state='form', ui_kind='text', description='发票金额结束'),
            DeclarationEntry(name='invoice_date_start', path=f'$.invoice_date_start', type='string', state='form', ui_kind='text', description='开票日期开始'),
            DeclarationEntry(name='invoice_date_end', path=f'$.invoice_date_end', type='string', state='form', ui_kind='text', description='开票日期结束'),
            DeclarationEntry(name='usd_amount_start', path=f'$.usd_amount_start', type='string', state='form', ui_kind='text', description='美元金额开始'),
            DeclarationEntry(name='usd_amount_end', path=f'$.usd_amount_end', type='string', state='form', ui_kind='text', description='美元金额结束'),
            DeclarationEntry(name='bl_no', path=f'$.bl_no', type='string', state='form', ui_kind='text', description='提单号'),  # zh_ambiguous
            DeclarationEntry(name='is_replace', path=f'$.is_replace', type='integer', state='form', ui_kind='number', default='0', description='是否被替换'),
            DeclarationEntry(name='create_time_start', path=f'$.create_time_start', type='string', state='form', ui_kind='text', description='创建时间开始'),
            DeclarationEntry(name='create_time_end', path=f'$.create_time_end', type='string', state='form', ui_kind='text', description='创建时间结束'),
            DeclarationEntry(name='cancel_time_start', path=f'$.cancel_time_start', type='string', state='form', ui_kind='text', description='作废时间开始'),
            DeclarationEntry(name='cancel_time_end', path=f'$.cancel_time_end', type='string', state='form', ui_kind='text', description='作废时间结束'),
            DeclarationEntry(name='un_amount', path=f'$.un_amount', type='number', state='form', ui_kind='number', default='0.00', description='未使用金额'),
            DeclarationEntry(name='is_no_tax_amount', path=f'$.is_no_tax_amount', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='page_no', path=f'$.page_no', type='string', state='carry', ui_kind='text', required=True, description='页码'),  # needs_capture:value_source
            DeclarationEntry(name='page_size', path=f'$.page_size', type='string', state='carry', ui_kind='text', required=True, description='每页条数'),  # needs_capture:value_source
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
