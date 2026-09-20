"""fin.pay_account.remove_account_order —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): (无)
溯源统计: 无zh=5, column=2 | fe_high=0, enum=0
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

PAY_ACCOUNT_REMOVE_ACCOUNT_ORDER: Final[EndpointSpec] = EndpointSpec(
    id='fin.pay_account.remove_account_order',
    system='fin',
    service='fin-service',
    name='PayAccount.removeAccountOrder',
    description='PayAccount.removeAccountOrder' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/payAccount/removeAccountOrder',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='account_type', path=f'$.account_type', type='integer', state='form', ui_kind='number', default='0', description='0物流对账单  1对账单补件类型一， 对账单补件类型二'),
            DeclarationEntry(name='pay_account_id', path=f'$.pay_account_id', type='integer', state='form', ui_kind='number', default='0', description='应付对账'),
            DeclarationEntry(name='pay_account_order_ids', path=f'$.pay_account_order_ids', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='original_removable_usd', path=f'$.original_removable_usd', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='original_removable_cny', path=f'$.original_removable_cny', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='original_removable_fee_ids', path=f'$.original_removable_fee_ids', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='receive_account_id', path=f'$.receive_account_id', type='integer', state='form', ui_kind='number'),
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
