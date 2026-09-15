"""fin.order.export_customer_account_fee —— 孪生生成器产物(请求面;行为面归场景用例)。

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

ORDER_EXPORT_CUSTOMER_ACCOUNT_FEE: Final[EndpointSpec] = EndpointSpec(
    id='fin.order.export_customer_account_fee',
    system='fin',
    service='fin-service',
    name='Order.exportCustomerAccountFee',
    description='Order.exportCustomerAccountFee' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/order/order/exportCustomerAccountFee',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='split_type', path=f'$.split_type', type='string', state='form', required=True),
            DeclarationEntry(name='order_ids', path=f'$.order_ids', type='string', state='form'),
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
