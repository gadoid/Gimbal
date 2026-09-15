"""fin.pay_invoice_batch.apply_edit —— 孪生生成器产物(请求面;行为面归场景用例)。

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

PAY_INVOICE_BATCH_APPLY_EDIT: Final[EndpointSpec] = EndpointSpec(
    id='fin.pay_invoice_batch.apply_edit',
    system='fin',
    service='fin-service',
    name='PayInvoiceBatch.applyEdit',
    description='PayInvoiceBatch.applyEdit' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/payInvoiceBatch/applyEdit',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='pay_invoice_apply_id', path=f'$.pay_invoice_apply_id', type='integer', state='form', required=True, default='0', description='应付开票申请ID'),
            DeclarationEntry(name='rate', path=f'$.rate', type='number', state='form', description='汇率'),
            DeclarationEntry(name='invoice_apply_simple', path=f'$.invoice_apply_simple', type='string', state='form', description='开票申请简称'),
            DeclarationEntry(name='invoice_form', path=f'$.invoice_form', type='string', state='form', required=True, description='开票形式 1合并开票 2按提单开票'),
            DeclarationEntry(name='invoice_type', path=f'$.invoice_type', type='integer', state='form', required=True, default='0', description='发票类型 1增值税数电普通发票 2增值税数电专用发票'),
            DeclarationEntry(name='seller_id', path=f'$.seller_id', type='integer', state='form', required=True, description='销售方ID'),
            DeclarationEntry(name='seller_name', path=f'$.seller_name', type='string', state='form', required=True, description='销售方名称'),
            DeclarationEntry(name='rate_list', path=f'$.rate_list', type='string', state='form', required=True),
            DeclarationEntry(name='truck_remark', path=f'$.truck_remark', type='string', state='form', description='拖车费/运费其他备注内容'),
            DeclarationEntry(name='require_other', path=f'$.require_other', type='string', state='form', description='其他开票要求'),
            DeclarationEntry(name='file_list', path=f'$.file_list', type='string', state='form'),
            DeclarationEntry(name='seller_info', path=f'$.seller_info', type='string', state='form', description='销售方信息'),
            DeclarationEntry(name='fast_remark', path=f'$.fast_remark', type='string', state='form', description='快速备注'),
            DeclarationEntry(name='invoice_rate_type', path=f'$.invoice_rate_type', type='string', state='form', description='发票税率类型 1统一税率 2设置费用税率'),
            DeclarationEntry(name='invoice_rate', path=f'$.invoice_rate', type='integer', state='form', description='发票税率'),
            DeclarationEntry(name='rate_type', path=f'$.rate_type', type='integer', state='form', description='汇率类型 1折币汇率 2系统汇率 3指定汇率'),
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
