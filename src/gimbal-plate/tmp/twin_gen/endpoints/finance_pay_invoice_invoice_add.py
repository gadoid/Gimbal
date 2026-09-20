"""fin.pay_invoice.invoice_add —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): invoice_number, invoice_type, invoice_amount, invoice_tax_amount, invoice_date, currency, invoice_exchange_rate, invoice_original, buyer_chinese_header, buyer_identifier_no, buyer_identity, seller_chinese_header, seller_identifier_no, seller_identity, fee_main_name, sorce, replace_invoice_original, cancel_by, invoice_image_name
溯源统计: column=31, rule=13, 无zh=6 | fe_high=0, enum=2
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

PAY_INVOICE_INVOICE_ADD: Final[EndpointSpec] = EndpointSpec(
    id='fin.pay_invoice.invoice_add',
    system='fin',
    service='fin-service',
    name='PayInvoice.invoiceAdd',
    description='PayInvoice.invoiceAdd' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/payInvoice/invoiceAdd',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='invoice_number', path=f'$.invoice_number', type='string', state='carry', ui_kind='text', required=True, description='发票号码'),  # zh_ambiguous, needs_capture:value_source
            DeclarationEntry(name='invoice_type', path=f'$.invoice_type', type='string', state='carry', ui_kind='select', required=True, description='发票类型 1:增值税普通发票 2:增值税专用发票', enum=['1', '2']),  # zh_ambiguous, needs_capture:enum_required
            DeclarationEntry(name='invoice_amount', path=f'$.invoice_amount', type='number', state='carry', ui_kind='number', required=True, default='0.00', description='发票金额'),  # zh_ambiguous, needs_capture:value_source
            DeclarationEntry(name='invoice_tax_amount', path=f'$.invoice_tax_amount', type='number', state='carry', ui_kind='number', required=True, default='0.00', description='发票税额'),  # needs_capture:value_source
            DeclarationEntry(name='invoice_date', path=f'$.invoice_date', type='string', state='carry', ui_kind='text', required=True, description='发票日期'),  # zh_ambiguous, needs_capture:value_source
            DeclarationEntry(name='currency', path=f'$.currency', type='string', state='carry', ui_kind='select', required=True, description='发票币种', enum=['CNY', 'USD']),  # zh_ambiguous, needs_capture:enum_required
            DeclarationEntry(name='usd_amount', path=f'$.usd_amount', type='number', state='carry', ui_kind='number', default='0.00', description='美元金额'),
            DeclarationEntry(name='invoice_exchange_rate', path=f'$.invoice_exchange_rate', type='string', state='carry', ui_kind='text', description='发票汇率'),  # zh_ambiguous
            DeclarationEntry(name='invoice_original', path=f'$.invoice_original', type='string', state='carry', ui_kind='text', required=True, description='发票原件'),  # needs_capture:value_source
            DeclarationEntry(name='buyer_chinese_header', path=f'$.buyer_chinese_header', type='string', state='carry', ui_kind='text', required=True, description='购买方中文抬头'),  # needs_capture:value_source
            DeclarationEntry(name='buyer_identifier_no', path=f'$.buyer_identifier_no', type='string', state='carry', ui_kind='text', required=True, description='购买方纳税人识别号'),  # needs_capture:value_source
            DeclarationEntry(name='buyer_identity', path=f'$.buyer_identity', type='string', state='carry', ui_kind='text', required=True),  # needs_capture:value_source
            DeclarationEntry(name='seller_chinese_header', path=f'$.seller_chinese_header', type='string', state='carry', ui_kind='text', required=True, description='销售方中文抬头'),  # needs_capture:value_source
            DeclarationEntry(name='seller_identifier_no', path=f'$.seller_identifier_no', type='string', state='carry', ui_kind='text', required=True, description='销售方纳税人识别号'),  # needs_capture:value_source
            DeclarationEntry(name='seller_identity', path=f'$.seller_identity', type='string', state='carry', ui_kind='text', required=True),  # needs_capture:value_source
            DeclarationEntry(name='pay_invoice_id', path=f'$.pay_invoice_id', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='invoice_no', path=f'$.invoice_no', type='string', state='carry', ui_kind='text', description='发票ID即编号'),
            DeclarationEntry(name='invoice_style', path=f'$.invoice_style', type='integer', state='carry', ui_kind='number', description='发票样式 1正式发票 2Debit Note'),
            DeclarationEntry(name='invoice_status', path=f'$.invoice_status', type='integer', state='carry', ui_kind='number', description='发票状态 2生效中 3已作废'),
            DeclarationEntry(name='fee_main_id', path=f'$.fee_main_id', type='integer', state='carry', ui_kind='number', description='费用主体ID'),
            DeclarationEntry(name='fee_main_name', path=f'$.fee_main_name', type='string', state='carry', ui_kind='text', description='费用主体名称'),  # needs_capture:value_source
            DeclarationEntry(name='pay_settle_object_id', path=f'$.pay_settle_object_id', type='integer', state='carry', ui_kind='number', description='应付结算对象ID'),
            DeclarationEntry(name='pay_settle_object', path=f'$.pay_settle_object', type='string', state='carry', ui_kind='text', description='应付结算对象'),
            DeclarationEntry(name='sorce', path=f'$.sorce', type='string', state='carry', ui_kind='text', description='对象来源  main 主体  supplier 供应商  customer 客户'),  # needs_capture:value_source
            DeclarationEntry(name='tax_voucher', path=f'$.tax_voucher', type='string', state='carry', ui_kind='text', description='税额凭证是否推送'),
            DeclarationEntry(name='file_id', path=f'$.file_id', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='bl_no', path=f'$.bl_no', type='string', state='carry', ui_kind='textarea', description='关联提单号'),
            DeclarationEntry(name='un_amount', path=f'$.un_amount', type='number', state='carry', ui_kind='number', description='未使用金额'),
            DeclarationEntry(name='use_amount', path=f'$.use_amount', type='number', state='carry', ui_kind='number', description='已使用金额'),
            DeclarationEntry(name='is_replace', path=f'$.is_replace', type='integer', state='carry', ui_kind='number', description='是否被替换 1是'),
            DeclarationEntry(name='replace_invoice_original', path=f'$.replace_invoice_original', type='string', state='carry', ui_kind='text', description='替换前发票原件'),  # needs_capture:value_source
            DeclarationEntry(name='replace_file_id', path=f'$.replace_file_id', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='writeoff_id', path=f'$.writeoff_id', type='string', state='carry', ui_kind='text', description='核销ID'),
            DeclarationEntry(name='writeoff_status', path=f'$.writeoff_status', type='integer', state='carry', ui_kind='number', description='核销状态 1未核销 2已核销 3部分核销'),
            DeclarationEntry(name='un_writeoff_amount_cny', path=f'$.un_writeoff_amount_cny', type='number', state='carry', ui_kind='number', description='未核销金额 CNY'),
            DeclarationEntry(name='use_writeoff_amount_cny', path=f'$.use_writeoff_amount_cny', type='number', state='carry', ui_kind='number', description='已核销金额 CNY'),
            DeclarationEntry(name='un_writeoff_amount_usd', path=f'$.un_writeoff_amount_usd', type='number', state='carry', ui_kind='number', description='未核销金额 USD'),
            DeclarationEntry(name='use_writeoff_amount_usd', path=f'$.use_writeoff_amount_usd', type='number', state='carry', ui_kind='number', description='已核销金额 USD'),
            DeclarationEntry(name='writeoff_force_audit_status', path=f'$.writeoff_force_audit_status', type='integer', state='carry', ui_kind='number', description='强制核销审批状态 0无状态 1审核中 2审核通过 3审核驳回 4审核撤销'),
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='carry', ui_kind='number', description='创建人ID'),
            DeclarationEntry(name='create_by', path=f'$.create_by', type='string', state='carry', ui_kind='text', description='创建人'),
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='number', description='创建时间'),
            DeclarationEntry(name='cancel_time', path=f'$.cancel_time', type='integer', state='carry', ui_kind='number', description='作废时间'),
            DeclarationEntry(name='cancel_id', path=f'$.cancel_id', type='integer', state='carry', ui_kind='number', description='作废人ID'),
            DeclarationEntry(name='cancel_by', path=f'$.cancel_by', type='string', state='carry', ui_kind='text', description='作废人'),  # needs_capture:value_source
            DeclarationEntry(name='update_time', path=f'$.update_time', type='integer', state='carry', ui_kind='number', description='更新时间'),
            DeclarationEntry(name='update_id', path=f'$.update_id', type='integer', state='carry', ui_kind='number', description='更新人ID'),
            DeclarationEntry(name='update_by', path=f'$.update_by', type='string', state='carry', ui_kind='text', description='更新人'),
            DeclarationEntry(name='sys_upttime', path=f'$.sys_upttime', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='invoice_image_name', path=f'$.invoice_image_name', type='string', state='carry', ui_kind='text', description='发票图片'),  # needs_capture:value_source
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
