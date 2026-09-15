"""fin.receive_invoice_batch.check_step2 —— 孪生生成器产物(请求面;行为面归场景用例)。

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

RECEIVE_INVOICE_BATCH_CHECK_STEP2: Final[EndpointSpec] = EndpointSpec(
    id='fin.receive_invoice_batch.check_step2',
    system='fin',
    service='fin-service',
    name='ReceiveInvoiceBatch.checkStep2',
    description='ReceiveInvoiceBatch.checkStep2' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/receiveInvoiceBatch/checkStep2',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='style', path=f'$.style', type='integer', state='form', description='开票申请样式 1正式发票 2Debit Note'),
            DeclarationEntry(name='cost_usd', path=f'$.cost_usd', type='number', state='form', description='费用金额（USD）'),
            DeclarationEntry(name='usd_is_turn', path=f'$.usd_is_turn', type='string', state='form', description='美金是否折币 1是 2否'),
            DeclarationEntry(name='rate_type', path=f'$.rate_type', type='integer', state='form', description='汇率类型 1折币汇率 2系统汇率 3指定汇率'),
            DeclarationEntry(name='sys_rate', path=f'$.sys_rate', type='number', state='form', description='系统汇率'),
            DeclarationEntry(name='merge_with_cny', path=f'$.merge_with_cny', type='string', state='form', description='是否与人民币合并 1是 2否'),
            DeclarationEntry(name='usd_require', path=f'$.usd_require', type='string', state='form'),
            DeclarationEntry(name='cost_cny', path=f'$.cost_cny', type='number', state='form', description='费用金额（CNY）'),
            DeclarationEntry(name='cny_require', path=f'$.cny_require', type='string', state='form'),
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
