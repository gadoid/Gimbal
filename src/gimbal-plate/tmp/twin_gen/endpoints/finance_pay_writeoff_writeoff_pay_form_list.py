"""fin.pay_writeoff.writeoff_pay_form_list —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): create_time, customer_id, customer_main_id, main_id, pay_settle_object_id, currency, status, writeoff_status, create_id, pay_invoice_apply_no, pay_invoice_batch_no, cancel_status, link_audit_status, invoice_status, invoice_no, receive_invoice_apply_no, receive_invoice_batch_no, put_settle_object_id, page_no, page_size, sort_field
溯源统计: frontend=30, 无zh=6, derived=4, builtin=4, column=3, lang=1 | fe_high=31, enum=1
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

PAY_WRITEOFF_WRITEOFF_PAY_FORM_LIST: Final[EndpointSpec] = EndpointSpec(
    id='fin.pay_writeoff.writeoff_pay_form_list',
    system='fin',
    service='fin-service',
    name='PayWriteoff.writeoffPayFormList',
    description='PayWriteoff.writeoffPayFormList' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/payWriteoff/writeoffPayFormList',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='pay_form_ids', path=f'$.pay_form_ids', type='string', state='form', ui_kind='text', required=True),
            DeclarationEntry(name='pay_form_no', path=f'$.pay_form_no', type='string', state='form', ui_kind='text', description='付款单ID'),
            DeclarationEntry(name='pay_form_name', path=f'$.pay_form_name', type='string', state='form', ui_kind='text', description='付款单名称'),
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='text', default='0', description='付款需求创建时间'),  # zh_ambiguous
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', ui_kind='text', default='0', description='下单客户名称'),  # zh_ambiguous
            DeclarationEntry(name='customer_main_id', path=f'$.customer_main_id', type='integer', state='form', ui_kind='select', default='0', description='对客订单主体'),  # zh_ambiguous
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='form', ui_kind='select', default='0', description='费用主体'),  # zh_ambiguous
            DeclarationEntry(name='pay_settle_object_id', path=f'$.pay_settle_object_id', type='integer', state='form', ui_kind='text', default='0', description='应付结算对象'),  # zh_ambiguous
            DeclarationEntry(name='supplier_number', path=f'$.supplier_number', type='string', state='form', ui_kind='text', description='供应商编号'),
            DeclarationEntry(name='currency', path=f'$.currency', type='string', state='form', ui_kind='select', description='币制'),  # zh_ambiguous
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='form', ui_kind='select', default='0', description='付款单状态'),  # zh_ambiguous
            DeclarationEntry(name='writeoff_status', path=f'$.writeoff_status', type='integer', state='form', ui_kind='select', default='1', description='核销状态'),  # zh_ambiguous
            DeclarationEntry(name='currency_is_turn', path=f'$.currency_is_turn', type='integer', state='form', ui_kind='select', description='发票是否折币'),
            DeclarationEntry(name='account_create_id', path=f'$.account_create_id', type='string', state='form', ui_kind='select', description='对账人'),
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='form', ui_kind='select', default='0', description='付款需求创建人'),  # zh_ambiguous
            DeclarationEntry(name='generate_time', path=f'$.generate_time', type='integer', state='carry', ui_kind='text', description='生成时间'),
            DeclarationEntry(name='pay_invoice_apply_no', path=f'$.pay_invoice_apply_no', type='string', state='carry', ui_kind='text', description='开票申请ID'),  # zh_ambiguous
            DeclarationEntry(name='pay_invoice_batch_no', path=f'$.pay_invoice_batch_no', type='string', state='carry', ui_kind='text', description='开票批次ID'),  # zh_ambiguous
            DeclarationEntry(name='cancel_status', path=f'$.cancel_status', type='integer', state='carry', ui_kind='select', description='开票申请状态'),  # zh_ambiguous
            DeclarationEntry(name='bl_nos', path=f'$.bl_nos', type='string', state='carry', ui_kind='text', description='提单号批量'),
            DeclarationEntry(name='invoice_apply_name', path=f'$.invoice_apply_name', type='string', state='carry', ui_kind='text', description='开票申请名称'),
            DeclarationEntry(name='link_role', path=f'$.link_role', type='integer', state='carry', ui_kind='select', default='0', description='关联身份'),
            DeclarationEntry(name='link_batch_no', path=f'$.link_batch_no', type='string', state='carry', ui_kind='text', description='关联对向批次ID'),
            DeclarationEntry(name='link_apply_no', path=f'$.link_apply_no', type='string', state='carry', ui_kind='text', description='关联对向申请ID'),
            DeclarationEntry(name='link_audit_status', path=f'$.link_audit_status', type='integer', state='carry', ui_kind='select', default='0', description='关联应收审核状态'),  # zh_ambiguous
            DeclarationEntry(name='invoice_status', path=f'$.invoice_status', type='integer', state='carry', ui_kind='select', default='0', description='登记状态'),  # zh_ambiguous
            DeclarationEntry(name='invoice_no', path=f'$.invoice_no', type='string', state='carry', ui_kind='text', description='关联发票号'),  # zh_ambiguous
            DeclarationEntry(name='batch_apply_name', path=f'$.batch_apply_name', type='string', state='carry', ui_kind='text', description='开票申请名称'),
            DeclarationEntry(name='batch_status', path=f'$.batch_status', type='integer', state='carry', ui_kind='select', description='批次状态'),
            DeclarationEntry(name='receive_invoice_apply_no', path=f'$.receive_invoice_apply_no', type='string', state='carry', ui_kind='text', description='开票申请ID'),  # zh_ambiguous
            DeclarationEntry(name='receive_invoice_batch_no', path=f'$.receive_invoice_batch_no', type='string', state='carry', ui_kind='text', description='开票批次ID'),  # zh_ambiguous
            DeclarationEntry(name='put_settle_object_id', path=f'$.put_settle_object_id', type='integer', state='carry', ui_kind='select', default='0', description='应收结算对象'),  # zh_ambiguous
            DeclarationEntry(name='relation_id', path=f'$.relation_id', type='integer', state='form', ui_kind='number', description='关联ID'),
            DeclarationEntry(name='check_ids', path=f'$.check_ids', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='real_total_start', path=f'$.real_total_start', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='real_total_end', path=f'$.real_total_end', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='pay_settle_object_receive_account', path=f'$.pay_settle_object_receive_account', type='string', state='form', ui_kind='text', description='应付结算对象收款账户'),
            DeclarationEntry(name='create_time_start', path=f'$.create_time_start', type='string', state='form', ui_kind='text', description='付款需求创建时间开始'),
            DeclarationEntry(name='create_time_end', path=f'$.create_time_end', type='string', state='form', ui_kind='text', description='付款需求创建时间结束'),
            DeclarationEntry(name='generate_time_start', path=f'$.generate_time_start', type='string', state='form', ui_kind='text', description='生成时间开始'),
            DeclarationEntry(name='generate_time_end', path=f'$.generate_time_end', type='string', state='form', ui_kind='text', description='生成时间结束'),
            DeclarationEntry(name='download_num', path=f'$.download_num', type='integer', state='form', ui_kind='number', default='0', description='付款单下载次数'),
            DeclarationEntry(name='statement_receipt_time_start', path=f'$.statement_receipt_time_start', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='statement_receipt_time_end', path=f'$.statement_receipt_time_end', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='sort_order', path=f'$.sort_order', type='string', state='form', ui_kind='select', required=True, default='desc', description='排序方向', enum=['asc', 'desc']),
            DeclarationEntry(name='page_no', path=f'$.page_no', type='string', state='carry', ui_kind='text', required=True, description='页码'),  # needs_capture:value_source
            DeclarationEntry(name='page_size', path=f'$.page_size', type='string', state='carry', ui_kind='text', required=True, description='每页条数'),  # needs_capture:value_source
            DeclarationEntry(name='sort_field', path=f'$.sort_field', type='string', state='carry', ui_kind='text', required=True, description='排序字段'),  # needs_capture:value_source
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
