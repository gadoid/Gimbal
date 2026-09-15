"""fin.payment_fee.get_payment_info —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-15T11:13:18+00:00
needs_capture(首跑经 gimbal 执行回填): id, payment_subtype
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

PAYMENT_FEE_GET_PAYMENT_INFO: Final[EndpointSpec] = EndpointSpec(
    id='fin.payment_fee.get_payment_info',
    system='fin',
    service='fin-service',
    name='PaymentFee.getPaymentInfo',
    description='PaymentFee.getPaymentInfo' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/operation/paymentFee/getPaymentInfo',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='id', path=f'$.id', type='string', state='carry', required=True),  # needs_capture:value_source
            DeclarationEntry(name='payment_subtype', path=f'$.payment_subtype', type='integer', state='carry', required=True, description='1调价回款 2调价折扣回款', enum=['1', '2']),  # needs_capture:enum_required
            DeclarationEntry(name='payment_method', path=f'$.payment_method', type='integer', state='form', default='0', description='1 提前回款 2确定回款'),
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
