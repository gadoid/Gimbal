"""fin.receive_invoice_batch.get_supplier_pr_invoice —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): currency
溯源统计: column=3, builtin=2, 无zh=1, lang=1 | fe_high=0, enum=2
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
            DeclarationEntry(name='id', path=f'$.id', type='string', state='form', ui_kind='text', required=True),
            DeclarationEntry(name='batch_type', path=f'$.batch_type', type='integer', state='form', ui_kind='select', required=True, description='选开票用按费用还是按提单', enum=['0', '1']),
            DeclarationEntry(name='invoice_style', path=f'$.invoice_style', type='integer', state='form', ui_kind='select', required=True, default='1', description='发票样式 1正式发票 2Debit Note', enum=['1', '2']),
            DeclarationEntry(name='page_no', path=f'$.page_no', type='string', state='form', ui_kind='text', description='页码'),
            DeclarationEntry(name='page_size', path=f'$.page_size', type='string', state='form', ui_kind='text', description='每页条数'),
            DeclarationEntry(name='merge_with_cny', path=f'$.merge_with_cny', type='string', state='form', ui_kind='text', description='是否与人民币合并 1是 2否'),
            DeclarationEntry(name='currency', path=f'$.currency', type='string', state='form', ui_kind='text', description='币值  '),  # zh_ambiguous
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
