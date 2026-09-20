"""fin.relate.check_base —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): business_type, trade_term, customer_period, supplier_period
溯源统计: column=5, 无zh=3 | fe_high=0, enum=0
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

RELATE_CHECK_BASE: Final[EndpointSpec] = EndpointSpec(
    id='fin.relate.check_base',
    system='fin',
    service='fin-service',
    name='Relate.checkBase',
    description='Relate.checkBase' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/customer/relate/checkBase',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='business_type', path=f'$.business_type', type='string', state='carry', ui_kind='text', description='业务类型'),  # needs_capture:value_source
            DeclarationEntry(name='trade_term', path=f'$.trade_term', type='string', state='carry', ui_kind='text', description='成交方式'),  # zh_ambiguous, needs_capture:value_source
            DeclarationEntry(name='customer_period', path=f'$.customer_period', type='integer', state='carry', ui_kind='number', default='0', description='客户账期'),  # needs_capture:value_source
            DeclarationEntry(name='supplier_period', path=f'$.supplier_period', type='integer', state='carry', ui_kind='number', default='0', description='供应商账期'),  # needs_capture:value_source
            DeclarationEntry(name='is_independent_email', path=f'$.is_independent_email', type='integer', state='form', ui_kind='number', default='0', description='是否独立对接供应商邮箱：0否 1是'),
            DeclarationEntry(name='receive_contact_ids', path=f'$.receive_contact_ids', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='relate_id', path=f'$.relate_id', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='relate_account', path=f'$.relate_account', type='array', state='form', ui_kind='unknown',
                children=[
                DeclarationEntry(name='business_type', path=f'$.relate_account.business_type', type='string', state='form', ui_kind='text', description='业务类型'),
                DeclarationEntry(name='trade_term', path=f'$.relate_account.trade_term', type='string', state='form', ui_kind='text', description='成交方式'),  # zh_ambiguous
                DeclarationEntry(name='customer_period', path=f'$.relate_account.customer_period', type='integer', state='form', ui_kind='number', description='客户账期'),
                DeclarationEntry(name='supplier_period', path=f'$.relate_account.supplier_period', type='integer', state='form', ui_kind='number', description='供应商账期'),
                ]),
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
