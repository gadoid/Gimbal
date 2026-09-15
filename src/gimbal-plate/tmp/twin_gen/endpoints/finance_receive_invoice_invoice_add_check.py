"""fin.receive_invoice.invoice_add_check —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-15T11:13:18+00:00
needs_capture(首跑经 gimbal 执行回填): invoice_original, seller_identity
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

RECEIVE_INVOICE_INVOICE_ADD_CHECK: Final[EndpointSpec] = EndpointSpec(
    id='fin.receive_invoice.invoice_add_check',
    system='fin',
    service='fin-service',
    name='ReceiveInvoice.invoiceAddCheck',
    description='ReceiveInvoice.invoiceAddCheck' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/receiveInvoice/invoiceAddCheck',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='invoice_number', path=f'$.invoice_number', type='string', state='form', required=True, description='发票号码'),
            DeclarationEntry(name='invoice_type', path=f'$.invoice_type', type='integer', state='form', required=True, description='发票类型 1:增值税普通发票 2:增值税专用发票', enum=['1', '2']),
            DeclarationEntry(name='invoice_amount', path=f'$.invoice_amount', type='number', state='form', required=True, default='0.00', description='发票金额'),
            DeclarationEntry(name='invoice_tax_amount', path=f'$.invoice_tax_amount', type='number', state='form', required=True, default='0.00', description='发票税额'),
            DeclarationEntry(name='invoice_date', path=f'$.invoice_date', type='string', state='form', required=True, description='发票日期'),
            DeclarationEntry(name='currency', path=f'$.currency', type='string', state='form', required=True, description='发票币种', enum=['CNY', 'USD']),
            DeclarationEntry(name='usd_amount', path=f'$.usd_amount', type='number', state='form', default='0.00', description='美元金额'),
            DeclarationEntry(name='invoice_exchange_rate', path=f'$.invoice_exchange_rate', type='string', state='form', description='发票汇率'),
            DeclarationEntry(name='invoice_original', path=f'$.invoice_original', type='string', state='carry', required=True, description='发票原件'),  # needs_capture:value_source
            DeclarationEntry(name='buyer_chinese_header', path=f'$.buyer_chinese_header', type='string', state='form', required=True, description='购买方中文抬头'),
            DeclarationEntry(name='buyer_identifier_no', path=f'$.buyer_identifier_no', type='string', state='form', required=True, description='购买方纳税人识别号'),
            DeclarationEntry(name='buyer_identity', path=f'$.buyer_identity', type='string', state='form', required=True),
            DeclarationEntry(name='seller_chinese_header', path=f'$.seller_chinese_header', type='string', state='form', required=True, description='销售方中文抬头'),
            DeclarationEntry(name='seller_identifier_no', path=f'$.seller_identifier_no', type='string', state='form', required=True, description='销售方纳税人识别号'),
            DeclarationEntry(name='seller_identity', path=f'$.seller_identity', type='string', state='carry', required=True),  # needs_capture:value_source
            DeclarationEntry(name='put_settle_object', path=f'$.put_settle_object', type='string', state='form', description='应收结算对象'),
            DeclarationEntry(name='main_name', path=f'$.main_name', type='string', state='form', description='费用主体名称'),
            DeclarationEntry(name='invoice_apply_type', path=f'$.invoice_apply_type', type='string', state='form'),
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
