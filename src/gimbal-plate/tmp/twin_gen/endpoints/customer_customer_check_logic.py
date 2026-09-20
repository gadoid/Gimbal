"""fin.customer.check_logic —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): settle_type, customer_id
溯源统计: lang=7, column=5, 无zh=1 | fe_high=0, enum=1
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

CUSTOMER_CHECK_LOGIC: Final[EndpointSpec] = EndpointSpec(
    id='fin.customer.check_logic',
    system='fin',
    service='fin-service',
    name='操作目的',
    description='操作目的' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/customer/customer/checkLogic',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='customer_discount', path=f'$.customer_discount', type='string', state='form', ui_kind='text', description='折扣补贴'),
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', ui_kind='select', default='submit', description='操作目的', enum=['check', 'submit']),
            DeclarationEntry(name='tax_number', path=f'$.tax_number', type='string', state='form', ui_kind='text', description='统一社会信用代码'),
            DeclarationEntry(name='service_team', path=f'$.service_team', type='string', state='form', ui_kind='text', description='服务团队'),
            DeclarationEntry(name='settle_type', path=f'$.settle_type', type='integer', state='form', ui_kind='number', default='0', description='1月结 2票结'),  # zh_ambiguous
            DeclarationEntry(name='customer_product_rel', path=f'$.customer_product_rel', type='string', state='form', ui_kind='text', description='产品信息'),
            DeclarationEntry(name='deposit_refund_day', path=f'$.deposit_refund_day', type='integer', state='form', ui_kind='number', description='保证金退还周期（天）'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='string', state='form', ui_kind='text', description='id 主键'),  # zh_ambiguous
            DeclarationEntry(name='deposit_refund_day_error', path=f'$.deposit_refund_day_error', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='receive_time_limit', path=f'$.receive_time_limit', type='integer', state='form', ui_kind='number', description='回款时效（天）'),
            DeclarationEntry(name='customer_association', path=f'$.customer_association', type='string', state='form', ui_kind='text', description='关联客户名称'),
            DeclarationEntry(name='client_expand_id', path=f'$.client_expand_id', type='integer', state='form', ui_kind='number', description='直客拓展ID'),
            DeclarationEntry(name='customer_service', path=f'$.customer_service', type='integer', state='form', ui_kind='number', description='客服'),
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
