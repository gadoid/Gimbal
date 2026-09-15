"""fin.receive_invoice_batch.apply_export —— 孪生生成器产物(请求面;行为面归场景用例)。

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

RECEIVE_INVOICE_BATCH_APPLY_EXPORT: Final[EndpointSpec] = EndpointSpec(
    id='fin.receive_invoice_batch.apply_export',
    system='fin',
    service='fin-service',
    name='ReceiveInvoiceBatch.applyExport',
    description='ReceiveInvoiceBatch.applyExport' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/receiveInvoiceBatch/applyExport',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='check_ids', path=f'$.check_ids', type='string', state='form'),
            DeclarationEntry(name='relation_id', path=f'$.relation_id', type='integer', state='form', default='0', description='业务ID'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', default='0', description='客户ID'),
            DeclarationEntry(name='invoice_apply_amount_min', path=f'$.invoice_apply_amount_min', type='string', state='form'),
            DeclarationEntry(name='invoice_apply_amount_max', path=f'$.invoice_apply_amount_max', type='string', state='form'),
            DeclarationEntry(name='bl_nos', path=f'$.bl_nos', type='string', state='form', description='关联提单号'),
            DeclarationEntry(name='page_no', path=f'$.page_no', type='string', state='form'),
            DeclarationEntry(name='page_size', path=f'$.page_size', type='string', state='form'),
            DeclarationEntry(name='link_role', path=f'$.link_role', type='integer', state='form', default='0', description='关联身份 0无 1发起方 2被关联方'),
            DeclarationEntry(name='link_audit_status', path=f'$.link_audit_status', type='integer', state='form', default='0', description='关联应收审核状态,应付申请用,同步对向应收批次审核状态 0无 1审核中 2审核通过 3审核驳回 4审核撤销'),
            DeclarationEntry(name='link_apply_id', path=f'$.link_apply_id', type='integer', state='form', description='关联对向申请ID'),
            DeclarationEntry(name='link_batch_id', path=f'$.link_batch_id', type='integer', state='form', description='关联对向批次ID,发起方记录'),
            DeclarationEntry(name='link_batch_no', path=f'$.link_batch_no', type='string', state='form', description='关联对向批次编号'),
            DeclarationEntry(name='link_apply_no', path=f'$.link_apply_no', type='string', state='form', description='关联对向申请编号'),
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
