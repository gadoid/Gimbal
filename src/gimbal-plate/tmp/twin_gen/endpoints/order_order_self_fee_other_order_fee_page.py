"""fin.order_self_fee.other_order_fee_page —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-15T11:13:18+00:00
needs_capture(首跑经 gimbal 执行回填): service_project
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

ORDER_SELF_FEE_OTHER_ORDER_FEE_PAGE: Final[EndpointSpec] = EndpointSpec(
    id='fin.order_self_fee.other_order_fee_page',
    system='fin',
    service='fin-service',
    name='OrderSelfFee.otherOrderFeePage',
    description='OrderSelfFee.otherOrderFeePage' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/order/orderSelfFee/otherOrderFeePage',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='service_project', path=f'$.service_project', type='string', state='carry', required=True, description='服务项目'),  # needs_capture:value_source
            DeclarationEntry(name='bl_no', path=f'$.bl_no', type='string', state='form', description='提单号'),
            DeclarationEntry(name='order_no', path=f'$.order_no', type='string', state='form', description='业务订单编号'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', default='0', description='客户ID'),
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='form', default='0', description='状态 1未通知 2已通知'),
            DeclarationEntry(name='order_self_id', path=f'$.order_self_id', type='integer', state='form', default='0', description='订单id'),
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
