"""fin.receive_invoice_batch.get_supplier_pr_invoice —— 孪生生成器产物(请求面;行为面归场景用例)。

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

RECEIVE_INVOICE_BATCH_GET_SUPPLIER_PR_INVOICE: Final[EndpointSpec] = EndpointSpec(
    id='fin.receive_invoice_batch.get_supplier_pr_invoice',
    system='fin',
    service='fin-service',
    name='ReceiveInvoiceBatch.getSupplierPrInvoice',
    description='ReceiveInvoiceBatch.getSupplierPrInvoice' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/receiveInvoiceBatch/getSupplierPrInvoice',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='id', path=f'$.id', type='string', state='form', required=True),
            DeclarationEntry(name='batch_type', path=f'$.batch_type', type='integer', state='form', required=True, description='选中费用  1 按费用  2按提单', enum=['0', '1']),
            DeclarationEntry(name='invoice_style', path=f'$.invoice_style', type='integer', state='form', required=True, default='1', description='发票样式 1正式发票 2Debit Note', enum=['1', '2']),
            DeclarationEntry(name='page_no', path=f'$.page_no', type='string', state='form'),
            DeclarationEntry(name='page_size', path=f'$.page_size', type='string', state='form'),
            DeclarationEntry(name='merge_with_cny', path=f'$.merge_with_cny', type='string', state='form', description='是否与人民币合并 1是 2否'),
            DeclarationEntry(name='currency', path=f'$.currency', type='string', state='form', description='币值'),
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
