"""fin.receive_account.remove_account_order —— 孪生生成器产物(请求面;行为面归场景用例)。

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

RECEIVE_ACCOUNT_REMOVE_ACCOUNT_ORDER: Final[EndpointSpec] = EndpointSpec(
    id='fin.receive_account.remove_account_order',
    system='fin',
    service='fin-service',
    name='ReceiveAccount.removeAccountOrder',
    description='ReceiveAccount.removeAccountOrder' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/receiveAccount/removeAccountOrder',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='account_type', path=f'$.account_type', type='integer', state='form', default='0', description='0物流对账单  1对账单补件类型一， 对账单补件类型二'),
            DeclarationEntry(name='receive_account_id', path=f'$.receive_account_id', type='integer', state='form'),
            DeclarationEntry(name='receive_order_ids', path=f'$.receive_order_ids', type='string', state='form'),
            DeclarationEntry(name='original_removable_usd', path=f'$.original_removable_usd', type='string', state='form'),
            DeclarationEntry(name='original_removable_cny', path=f'$.original_removable_cny', type='string', state='form'),
            DeclarationEntry(name='original_removable_fee_ids', path=f'$.original_removable_fee_ids', type='string', state='form'),
            DeclarationEntry(name='pay_account_id', path=f'$.pay_account_id', type='integer', state='form', default='0', description='应付对账'),
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
