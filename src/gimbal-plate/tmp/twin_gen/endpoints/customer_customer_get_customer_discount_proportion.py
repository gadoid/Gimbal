"""fin.customer.get_customer_discount_proportion —— 孪生生成器产物(请求面;行为面归场景用例)。

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

CUSTOMER_GET_CUSTOMER_DISCOUNT_PROPORTION: Final[EndpointSpec] = EndpointSpec(
    id='fin.customer.get_customer_discount_proportion',
    system='fin',
    service='fin-service',
    name='Customer.getCustomerDiscountProportion',
    description='Customer.getCustomerDiscountProportion' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/customer/customer/getCustomerDiscountProportion',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', default='0', description='客户ID'),
            DeclarationEntry(name='trade_term', path=f'$.trade_term', type='string', state='form', description='成交方式,多个逗号隔开'),
            DeclarationEntry(name='airline', path=f'$.airline', type='string', state='form', description='航线,多个逗号隔开  空则是全量'),
            DeclarationEntry(name='volume', path=f'$.volume', type='string', state='form', description='箱型箱量'),
            DeclarationEntry(name='atd', path=f'$.atd', type='integer', state='form', default='0', description='实际开航日'),
            DeclarationEntry(name='order_id', path=f'$.order_id', type='integer', state='form', default='0', description='业务订单ID'),
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
