"""fin.receive_writeoff.writeoff_invoice_page —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-15T11:13:18+00:00
needs_capture(首跑经 gimbal 执行回填): (无)
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

RECEIVE_WRITEOFF_WRITEOFF_INVOICE_PAGE: Final[EndpointSpec] = EndpointSpec(
    id='fin.receive_writeoff.writeoff_invoice_page',
    system='fin',
    service='fin-service',
    name='ReceiveWriteoff.writeoffInvoicePage',
    description='ReceiveWriteoff.writeoffInvoicePage' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/receiveWriteoff/writeoffInvoicePage',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='receive_invoice_ids', path=f'$.receive_invoice_ids', type='string', state='form', required=True),
            DeclarationEntry(name='relation_id', path=f'$.relation_id', type='integer', state='form', default='0', description='业务ID'),
            DeclarationEntry(name='check_ids', path=f'$.check_ids', type='string', state='form'),
            DeclarationEntry(name='invoice_no', path=f'$.invoice_no', type='string', state='form', description='发票ID即编号'),
            DeclarationEntry(name='invoice_style', path=f'$.invoice_style', type='integer', state='form', default='1', description='发票样式 1正式发票 2Debit Note'),
            DeclarationEntry(name='invoice_status', path=f'$.invoice_status', type='integer', state='form', default='0', description='登记状态  0 未开票  1已开票'),
            DeclarationEntry(name='fee_main_id', path=f'$.fee_main_id', type='integer', state='form', default='0', description='费用主体ID'),
            DeclarationEntry(name='receive_settle_object_id', path=f'$.receive_settle_object_id', type='integer', state='form', default='0', description='应收结算对象ID'),
            DeclarationEntry(name='invoice_number', path=f'$.invoice_number', type='string', state='form', description='发票号码'),
            DeclarationEntry(name='invoice_type', path=f'$.invoice_type', type='integer', state='form', default='0', description='发票类型 1增值税数电普通发票 2增值税数电专用发票'),
            DeclarationEntry(name='invoice_amount_start', path=f'$.invoice_amount_start', type='string', state='form'),
            DeclarationEntry(name='invoice_amount_end', path=f'$.invoice_amount_end', type='string', state='form'),
            DeclarationEntry(name='invoice_date_start', path=f'$.invoice_date_start', type='string', state='form'),
            DeclarationEntry(name='invoice_date_end', path=f'$.invoice_date_end', type='string', state='form'),
            DeclarationEntry(name='currency', path=f'$.currency', type='string', state='form', description='币值'),
            DeclarationEntry(name='usd_amount_start', path=f'$.usd_amount_start', type='string', state='form'),
            DeclarationEntry(name='usd_amount_end', path=f'$.usd_amount_end', type='string', state='form'),
            DeclarationEntry(name='bl_no', path=f'$.bl_no', type='string', state='form', description='提单号'),
            DeclarationEntry(name='is_replace', path=f'$.is_replace', type='integer', state='form', default='0', description='是否被替换 1是'),
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='form', default='0', description='发起人ID'),
            DeclarationEntry(name='create_time_start', path=f'$.create_time_start', type='string', state='form'),
            DeclarationEntry(name='create_time_end', path=f'$.create_time_end', type='string', state='form'),
            DeclarationEntry(name='cancel_time_start', path=f'$.cancel_time_start', type='string', state='form'),
            DeclarationEntry(name='cancel_time_end', path=f'$.cancel_time_end', type='string', state='form'),
            DeclarationEntry(name='cancel_id', path=f'$.cancel_id', type='integer', state='form', default='0', description='作废人ID'),
            DeclarationEntry(name='un_amount', path=f'$.un_amount', type='number', state='form', default='0.00', description='未使用金额'),
            DeclarationEntry(name='is_no_tax_amount', path=f'$.is_no_tax_amount', type='string', state='form'),
            DeclarationEntry(name='writeoff_status', path=f'$.writeoff_status', type='integer', state='form', default='1', description='核销状态 1未核销 2已核销 3部分核销'),
            DeclarationEntry(name='invoice_use_status', path=f'$.invoice_use_status', type='string', state='form'),
            DeclarationEntry(name='receive_invoice_apply_no', path=f'$.receive_invoice_apply_no', type='string', state='form', description='开票申请ID编号'),
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
