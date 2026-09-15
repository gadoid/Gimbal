"""fin.order_self_fee.edit_create_status —— 孪生生成器产物(请求面;行为面归场景用例)。

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

ORDER_SELF_FEE_EDIT_CREATE_STATUS: Final[EndpointSpec] = EndpointSpec(
    id='fin.order_self_fee.edit_create_status',
    system='fin',
    service='fin-service',
    name='OrderSelfFee.editCreateStatus',
    description='OrderSelfFee.editCreateStatus' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/order/orderSelfFee/editCreateStatus',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='order_self_id', path=f'$.order_self_id', type='integer', state='form', required=True, default='0', description='订单id'),
            DeclarationEntry(name='service_project', path=f'$.service_project', type='string', state='form', required=True, description='服务项目'),
            DeclarationEntry(name='order_id', path=f'$.order_id', type='integer', state='form', default='0', description='业务订单ID'),
            DeclarationEntry(name='policy_id', path=f'$.policy_id', type='integer', state='form', default='0', description='服务策略ID'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', default='0', description='客户ID'),
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
