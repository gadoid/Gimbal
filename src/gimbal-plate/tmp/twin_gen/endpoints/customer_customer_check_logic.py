"""fin.customer.check_logic —— 孪生生成器产物(请求面;行为面归场景用例)。

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
            DeclarationEntry(name='customer_discount', path=f'$.customer_discount', type='string', state='form'),
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', default='submit', description='操作目的'),
            DeclarationEntry(name='tax_number', path=f'$.tax_number', type='string', state='form', description='税号'),
            DeclarationEntry(name='service_team', path=f'$.service_team', type='string', state='form'),
            DeclarationEntry(name='settle_type', path=f'$.settle_type', type='integer', state='form', default='0', description='1月结 2票结'),
            DeclarationEntry(name='customer_product_rel', path=f'$.customer_product_rel', type='string', state='form'),
            DeclarationEntry(name='deposit_refund_day', path=f'$.deposit_refund_day', type='integer', state='form', description='保证金退还周期  单位天'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', default='0', description='客户ID'),
            DeclarationEntry(name='deposit_refund_day_error', path=f'$.deposit_refund_day_error', type='string', state='form'),
            DeclarationEntry(name='receive_time_limit', path=f'$.receive_time_limit', type='integer', state='form', description='回款时效'),
            DeclarationEntry(name='customer_association', path=f'$.customer_association', type='string', state='form'),
            DeclarationEntry(name='client_expand_id', path=f'$.client_expand_id', type='integer', state='form', description='直客拓展ID'),
            DeclarationEntry(name='customer_service', path=f'$.customer_service', type='integer', state='form'),
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
