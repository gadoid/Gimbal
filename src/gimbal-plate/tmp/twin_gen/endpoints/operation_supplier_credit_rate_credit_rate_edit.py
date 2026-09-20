"""fin.supplier_credit_rate.credit_rate_edit —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): id, advance_payment_rate, adjustment_payment_rate, month_advance_payment_amount, month_sure_payment_amount, month_adjustment_payment_amount, usd_rate, effective_time_start, effective_time_end, ap_rate_discount_status
溯源统计: lang=8, column=2 | fe_high=0, enum=1
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

SUPPLIER_CREDIT_RATE_CREDIT_RATE_EDIT: Final[EndpointSpec] = EndpointSpec(
    id='fin.supplier_credit_rate.credit_rate_edit',
    system='fin',
    service='fin-service',
    name='SupplierCreditRate.creditRateEdit',
    description='SupplierCreditRate.creditRateEdit' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/operation/supplierCreditRate/creditRateEdit',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='id', path=f'$.id', type='integer', state='carry', ui_kind='number', required=True, description='关联ID'),  # zh_ambiguous, needs_capture:value_source
            DeclarationEntry(name='advance_payment_rate', path=f'$.advance_payment_rate', type='number', state='carry', ui_kind='number', required=True, default='0.0000', description='提前回款费率'),  # zh_ambiguous, needs_capture:value_source
            DeclarationEntry(name='adjustment_payment_rate', path=f'$.adjustment_payment_rate', type='number', state='carry', ui_kind='number', required=True, default='0.0000', description='调价回款费率'),  # needs_capture:value_source
            DeclarationEntry(name='month_advance_payment_amount', path=f'$.month_advance_payment_amount', type='number', state='carry', ui_kind='number', required=True, default='0.00', description='月提前回款额度'),  # needs_capture:value_source
            DeclarationEntry(name='month_sure_payment_amount', path=f'$.month_sure_payment_amount', type='number', state='carry', ui_kind='number', required=True, default='0.00', description='月到期回款额度'),  # needs_capture:value_source
            DeclarationEntry(name='month_adjustment_payment_amount', path=f'$.month_adjustment_payment_amount', type='number', state='carry', ui_kind='number', required=True, default='0.00', description='月调价回款额度'),  # needs_capture:value_source
            DeclarationEntry(name='usd_rate', path=f'$.usd_rate', type='number', state='carry', ui_kind='number', required=True, default='0.0000', description='约定美元汇率'),  # needs_capture:value_source
            DeclarationEntry(name='effective_time_start', path=f'$.effective_time_start', type='integer', state='carry', ui_kind='number', required=True, default='0', description='有效期起'),  # needs_capture:value_source
            DeclarationEntry(name='effective_time_end', path=f'$.effective_time_end', type='integer', state='carry', ui_kind='number', required=True, default='0', description='有效期止'),  # needs_capture:value_source
            DeclarationEntry(name='ap_rate_discount_status', path=f'$.ap_rate_discount_status', type='integer', state='carry', ui_kind='select', required=True, default='0', description='提前回款费率折扣状态  0否 1是', enum=['0', '1']),  # needs_capture:enum_required
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
