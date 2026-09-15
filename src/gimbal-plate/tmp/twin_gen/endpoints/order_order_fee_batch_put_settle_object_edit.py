"""fin.order_fee.batch_put_settle_object_edit —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-15T11:13:18+00:00
needs_capture(首跑经 gimbal 执行回填): order_fee_real_id, order_id
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

ORDER_FEE_BATCH_PUT_SETTLE_OBJECT_EDIT: Final[EndpointSpec] = EndpointSpec(
    id='fin.order_fee.batch_put_settle_object_edit',
    system='fin',
    service='fin-service',
    name='OrderFee.batchPutSettleObjectEdit',
    description='OrderFee.batchPutSettleObjectEdit' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/order/orderFee/batchPutSettleObjectEdit',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='order_fee_real_id', path=f'$.order_fee_real_id', type='integer', state='carry', required=True, default='0', description='费用id'),  # needs_capture:value_source
            DeclarationEntry(name='order_id', path=f'$.order_id', type='integer', state='carry', required=True, default='0', description='订单id'),  # needs_capture:value_source
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
