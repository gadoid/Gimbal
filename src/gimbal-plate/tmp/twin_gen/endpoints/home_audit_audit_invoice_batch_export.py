"""fin.audit.audit_invoice_batch_export —— 孪生生成器产物(请求面;行为面归场景用例)。

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

AUDIT_AUDIT_INVOICE_BATCH_EXPORT: Final[EndpointSpec] = EndpointSpec(
    id='fin.audit.audit_invoice_batch_export',
    system='fin',
    service='fin-service',
    name='Audit.auditInvoiceBatchExport',
    description='Audit.auditInvoiceBatchExport' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/home/audit/auditInvoiceBatchExport',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='active_tab', path=f'$.active_tab', type='string', state='form'),
            DeclarationEntry(name='is_all', path=f'$.is_all', type='string', state='form'),
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='form', default='0', description='发起人ID'),
            DeclarationEntry(name='create_time_start', path=f'$.create_time_start', type='string', state='form'),
            DeclarationEntry(name='create_time_end', path=f'$.create_time_end', type='string', state='form'),
            DeclarationEntry(name='audit_type', path=f'$.audit_type', type='string', state='form', description='审批类型'),
            DeclarationEntry(name='audit_no', path=f'$.audit_no', type='string', state='form', description='审批编号'),
            DeclarationEntry(name='audit_status', path=f'$.audit_status', type='integer', state='form', default='1', description='审批状态 1待处理 2通过 3驳回 4撤销'),
            DeclarationEntry(name='check_ids', path=f'$.check_ids', type='string', state='form'),
            DeclarationEntry(name='audit_note', path=f'$.audit_note', type='string', state='form', description='审批人备注'),
            DeclarationEntry(name='expedite_status', path=f'$.expedite_status', type='integer', state='form', default='0', description='催办状态 1已催办'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', default='0', description='客户ID'),
            DeclarationEntry(name='supplier_id', path=f'$.supplier_id', type='integer', state='form', default='0', description='变更账期供应商ID'),
            DeclarationEntry(name='bl_no', path=f'$.bl_no', type='string', state='form', description='提单号'),
            DeclarationEntry(name='bl_nos', path=f'$.bl_nos', type='string', state='form', description='关联提单号'),
            DeclarationEntry(name='cancel_remark', path=f'$.cancel_remark', type='string', state='form', description='撤销描述'),
            DeclarationEntry(name='invoice_batch_no', path=f'$.invoice_batch_no', type='string', state='form', description='开票批次编号'),
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='form', default='0', description='费用主体ID'),
            DeclarationEntry(name='put_settle_object_id', path=f'$.put_settle_object_id', type='integer', state='form', default='0', description='应收结算对象ID'),
            DeclarationEntry(name='pay_settle_object_id', path=f'$.pay_settle_object_id', type='integer', state='form', default='0', description='应收结算对象ID'),
            DeclarationEntry(name='invoice_apply_currency', path=f'$.invoice_apply_currency', type='string', state='form', description='开票申请币制'),
            DeclarationEntry(name='writeoff_no', path=f'$.writeoff_no', type='string', state='form', description='应收核销记录编号'),
            DeclarationEntry(name='pay_demand_no', path=f'$.pay_demand_no', type='string', state='form', description='付款需求编号'),
            DeclarationEntry(name='account_no', path=f'$.account_no', type='string', state='form', description='对账批次编号'),
            DeclarationEntry(name='source_type', path=f'$.source_type', type='integer', state='form', default='1', description='来源类型(应收批次)1自主创建 2应付联动发起(0910)'),
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
