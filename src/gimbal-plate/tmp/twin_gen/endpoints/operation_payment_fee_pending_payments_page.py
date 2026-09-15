"""fin.payment_fee.pending_payments_page —— 孪生生成器产物(请求面;行为面归场景用例)。

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

PAYMENT_FEE_PENDING_PAYMENTS_PAGE: Final[EndpointSpec] = EndpointSpec(
    id='fin.payment_fee.pending_payments_page',
    system='fin',
    service='fin-service',
    name='PaymentFee.pendingPaymentsPage',
    description='PaymentFee.pendingPaymentsPage' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/operation/paymentFee/pendingPaymentsPage',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='page_no', path=f'$.page_no', type='string', state='form'),
            DeclarationEntry(name='page_size', path=f'$.page_size', type='string', state='form'),
            DeclarationEntry(name='payment_status', path=f'$.payment_status', type='integer', state='form', default='0', description='结算状态 待确认 1已确认 2已退回  3已完成  4已拒绝'),
            DeclarationEntry(name='invoice_status', path=f'$.invoice_status', type='integer', state='form', default='0', description='登记状态  0 未开票  1已开票'),
            DeclarationEntry(name='enter_status', path=f'$.enter_status', type='integer', state='form', default='0', description='0待录入 1已录入'),
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
