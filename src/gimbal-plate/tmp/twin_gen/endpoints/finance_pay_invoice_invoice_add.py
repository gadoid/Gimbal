"""fin.pay_invoice.invoice_add —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-15T11:13:18+00:00
needs_capture(首跑经 gimbal 执行回填): invoice_number, invoice_type, invoice_amount, invoice_tax_amount, invoice_date, currency, invoice_original, buyer_chinese_header, buyer_identifier_no, buyer_identity, seller_chinese_header, seller_identifier_no, seller_identity
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
            DeclarationEntry(name='invoice_number', path=f'$.invoice_number', type='string', state='carry', required=True, description='发票号码'),  # needs_capture:value_source
            DeclarationEntry(name='invoice_type', path=f'$.invoice_type', type='integer', state='carry', required=True, description='发票类型 1:增值税普通发票 2:增值税专用发票', enum=['1', '2']),  # needs_capture:enum_required
            DeclarationEntry(name='invoice_amount', path=f'$.invoice_amount', type='number', state='carry', required=True, default='0.00', description='发票金额'),  # needs_capture:value_source
            DeclarationEntry(name='invoice_tax_amount', path=f'$.invoice_tax_amount', type='number', state='carry', required=True, default='0.00', description='发票税额'),  # needs_capture:value_source
            DeclarationEntry(name='invoice_date', path=f'$.invoice_date', type='string', state='carry', required=True, description='发票日期'),  # needs_capture:value_source
            DeclarationEntry(name='currency', path=f'$.currency', type='string', state='carry', required=True, description='发票币种', enum=['CNY', 'USD']),  # needs_capture:enum_required
            DeclarationEntry(name='usd_amount', path=f'$.usd_amount', type='number', state='carry', default='0.00', description='美元金额'),
            DeclarationEntry(name='invoice_exchange_rate', path=f'$.invoice_exchange_rate', type='string', state='carry', description='发票汇率'),
            DeclarationEntry(name='invoice_original', path=f'$.invoice_original', type='string', state='carry', required=True, description='发票原件'),  # needs_capture:value_source
            DeclarationEntry(name='buyer_chinese_header', path=f'$.buyer_chinese_header', type='string', state='carry', required=True, description='购买方中文抬头'),  # needs_capture:value_source
            DeclarationEntry(name='buyer_identifier_no', path=f'$.buyer_identifier_no', type='string', state='carry', required=True, description='购买方纳税人识别号'),  # needs_capture:value_source
            DeclarationEntry(name='buyer_identity', path=f'$.buyer_identity', type='string', state='carry', required=True),  # needs_capture:value_source
            DeclarationEntry(name='seller_chinese_header', path=f'$.seller_chinese_header', type='string', state='carry', required=True, description='销售方中文抬头'),  # needs_capture:value_source
            DeclarationEntry(name='seller_identifier_no', path=f'$.seller_identifier_no', type='string', state='carry', required=True, description='销售方纳税人识别号'),  # needs_capture:value_source
            DeclarationEntry(name='seller_identity', path=f'$.seller_identity', type='string', state='carry', required=True),  # needs_capture:value_source
        ],
    ),
    responses={
        200: ResponseSpec(
            status=200,
        ),
    },
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module=FIN_DEFAULT_MODULE,
        owner=FIN_DEFAULT_OWNER,
        tags=list(FIN_DEFAULT_TAGS),
    ),
)
