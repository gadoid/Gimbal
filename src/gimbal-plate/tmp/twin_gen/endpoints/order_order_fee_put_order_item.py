"""fin.order_fee.put_order_item —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): main_id, settle_object_id, symbol
溯源统计: lang=2, builtin=2, column=1 | fe_high=0, enum=1
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

ORDER_FEE_PUT_ORDER_ITEM: Final[EndpointSpec] = EndpointSpec(
    id='fin.order_fee.put_order_item',
    system='fin',
    service='fin-service',
    name='OrderFee.putOrderItem',
    description='OrderFee.putOrderItem' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/order/orderFee/putOrderItem',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='carry', ui_kind='number', required=True, default='0', description='费用主体'),  # zh_ambiguous, needs_capture:value_source
            DeclarationEntry(name='settle_object_id', path=f'$.settle_object_id', type='integer', state='carry', ui_kind='number', required=True, default='0', description='结算对象'),  # zh_ambiguous, needs_capture:value_source
            DeclarationEntry(name='symbol', path=f'$.symbol', type='integer', state='form', ui_kind='number', default='0', description='应收应付 0 应付  1应收'),  # zh_ambiguous
            DeclarationEntry(name='sort_field', path=f'$.sort_field', type='string', state='form', ui_kind='text', description='排序字段'),
            DeclarationEntry(name='sort_order', path=f'$.sort_order', type='string', state='form', ui_kind='select', description='排序方向', enum=['asc', 'desc']),
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
