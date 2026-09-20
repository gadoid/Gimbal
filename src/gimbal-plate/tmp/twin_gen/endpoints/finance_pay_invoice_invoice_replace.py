"""fin.pay_invoice.invoice_replace —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): pay_invoice_id, invoice_number, invoice_type, invoice_amount, invoice_tax_amount, invoice_date, currency, invoice_exchange_rate, buyer_chinese_header, buyer_identifier_no, seller_chinese_header, seller_identifier_no
溯源统计: rule=14 | fe_high=0, enum=2
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

PAY_INVOICE_INVOICE_REPLACE: Final[EndpointSpec] = EndpointSpec(
    id='fin.pay_invoice.invoice_replace',
    system='fin',
    service='fin-service',
    name='PayInvoice.invoiceReplace',
    description='PayInvoice.invoiceReplace' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/payInvoice/invoiceReplace',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='pay_invoice_id', path=f'$.pay_invoice_id', type='string', state='form', ui_kind='text', required=True, default='0', description='发票id'),  # zh_ambiguous
            DeclarationEntry(name='invoice_number', path=f'$.invoice_number', type='string', state='form', ui_kind='text', required=True, description='发票号码'),  # zh_ambiguous
            DeclarationEntry(name='invoice_type', path=f'$.invoice_type', type='string', state='carry', ui_kind='select', required=True, description='发票类型 1:增值税普通发票 2:增值税专用发票', enum=['1', '2']),  # zh_ambiguous, needs_capture:enum_required
            DeclarationEntry(name='invoice_amount', path=f'$.invoice_amount', type='number', state='carry', ui_kind='number', required=True, default='0.00', description='发票金额'),  # zh_ambiguous, needs_capture:value_source
            DeclarationEntry(name='invoice_tax_amount', path=f'$.invoice_tax_amount', type='number', state='carry', ui_kind='number', required=True, default='0.00', description='发票税额'),  # needs_capture:value_source
            DeclarationEntry(name='invoice_date', path=f'$.invoice_date', type='string', state='carry', ui_kind='text', required=True, description='发票日期'),  # zh_ambiguous, needs_capture:value_source
            DeclarationEntry(name='currency', path=f'$.currency', type='string', state='carry', ui_kind='select', required=True, description='发票币种', enum=['CNY', 'USD']),  # zh_ambiguous, needs_capture:enum_required
            DeclarationEntry(name='usd_amount', path=f'$.usd_amount', type='number', state='form', ui_kind='number', default='0.00', description='美元金额'),
            DeclarationEntry(name='invoice_exchange_rate', path=f'$.invoice_exchange_rate', type='string', state='carry', ui_kind='text', description='发票汇率'),  # zh_ambiguous
            DeclarationEntry(name='invoice_original', path=f'$.invoice_original', type='string', state='form', ui_kind='text', required=True, description='发票原件'),
            DeclarationEntry(name='buyer_chinese_header', path=f'$.buyer_chinese_header', type='string', state='carry', ui_kind='text', required=True, description='购买方中文抬头'),  # needs_capture:value_source
            DeclarationEntry(name='buyer_identifier_no', path=f'$.buyer_identifier_no', type='string', state='carry', ui_kind='text', required=True, description='购买方纳税人识别号'),  # needs_capture:value_source
            DeclarationEntry(name='seller_chinese_header', path=f'$.seller_chinese_header', type='string', state='carry', ui_kind='text', required=True, description='销售方中文抬头'),  # needs_capture:value_source
            DeclarationEntry(name='seller_identifier_no', path=f'$.seller_identifier_no', type='string', state='carry', ui_kind='text', required=True, description='销售方纳税人识别号'),  # needs_capture:value_source
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
