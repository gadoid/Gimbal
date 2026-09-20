"""fin.index.order_fee —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): order_fee_real_ids, order_no
溯源统计: rule=1, column=1 | fe_high=0, enum=0
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

INDEX_ORDER_FEE: Final[EndpointSpec] = EndpointSpec(
    id='fin.index.order_fee',
    system='fin',
    service='fin-service',
    name='Index.orderFee',
    description='Index.orderFee' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/api/index/orderFee',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='order_fee_real_ids', path=f'$.order_fee_real_ids', type='string', state='carry', ui_kind='text', required=True, description='费用ID'),  # needs_capture:value_source
            DeclarationEntry(name='order_no', path=f'$.order_no', type='string', state='form', ui_kind='text', description='业务订单ID'),  # zh_ambiguous
        ],
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description='成功(信封统一;data 行形状归场景用例)',
            declarations=[
            DeclarationEntry(name='retCode', path='$.retCode', type='number',
                             required=False, ui_kind='number',
                             description='回调状态码(0=成功)', assertable=True),
            DeclarationEntry(name='retMsg', path='$.retMsg', type='string',
                             required=False, ui_kind='text',
                             description='回调提示信息', assertable=True),
            DeclarationEntry(name='data', path='$.data', type='object',
                             required=False, ui_kind='json',
                             description='业务数据(行形状归场景用例)', assertable=True),

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
