"""fin.pay_invoice_batch.check_step2 —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): rate_type
溯源统计: lang=6, 无zh=2, column=1 | fe_high=0, enum=0
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

PAY_INVOICE_BATCH_CHECK_STEP2: Final[EndpointSpec] = EndpointSpec(
    id='fin.pay_invoice_batch.check_step2',
    system='fin',
    service='fin-service',
    name='PayInvoiceBatch.checkStep2',
    description='PayInvoiceBatch.checkStep2' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/payInvoiceBatch/checkStep2',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='style', path=f'$.style', type='integer', state='form', ui_kind='number', description='开票申请样式'),
            DeclarationEntry(name='cost_usd', path=f'$.cost_usd', type='number', state='form', ui_kind='number', description='费用金额（USD）'),
            DeclarationEntry(name='usd_is_turn', path=f'$.usd_is_turn', type='string', state='form', ui_kind='text', description='美金是否折币'),
            DeclarationEntry(name='rate_type', path=f'$.rate_type', type='integer', state='form', ui_kind='number', description='汇率类型'),  # zh_ambiguous
            DeclarationEntry(name='sys_rate', path=f'$.sys_rate', type='number', state='form', ui_kind='number', description='系统汇率'),
            DeclarationEntry(name='merge_with_cny', path=f'$.merge_with_cny', type='string', state='form', ui_kind='text', description='是否与人民币合并 1是 2否'),
            DeclarationEntry(name='usd_require', path=f'$.usd_require', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='cost_cny', path=f'$.cost_cny', type='number', state='form', ui_kind='number', description='费用金额（CNY）'),
            DeclarationEntry(name='cny_require', path=f'$.cny_require', type='string', state='form', ui_kind='text'),
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
