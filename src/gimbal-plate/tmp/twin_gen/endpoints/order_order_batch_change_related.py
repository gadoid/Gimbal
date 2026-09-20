"""fin.order_order.batch_change_related —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): (无)
溯源统计: rule=9, column=1 | fe_high=0, enum=0
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

ORDER_BATCH_CHANGE_RELATED: Final[EndpointSpec] = EndpointSpec(
    id='fin.order_order.batch_change_related',
    system='fin',
    service='fin-service',
    name='Order.batchChangeRelated',
    description='Order.batchChangeRelated' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/order/order/batchChangeRelated',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='order_ids', path=f'$.order_ids', type='string', state='form', ui_kind='text', required=True, description='客户ID'),
            DeclarationEntry(name='sale', path=f'$.sale', type='integer', state='form', ui_kind='number', description='销售ID'),
            DeclarationEntry(name='customer_service', path=f'$.customer_service', type='integer', state='form', ui_kind='number', description='客服ID'),
            DeclarationEntry(name='operate', path=f'$.operate', type='string', state='form', ui_kind='text', description='操作'),
            DeclarationEntry(name='book', path=f'$.book', type='string', state='form', ui_kind='text', description='订舱ID'),
            DeclarationEntry(name='bill', path=f'$.bill', type='string', state='form', ui_kind='text', description='报关ID'),
            DeclarationEntry(name='trailer', path=f'$.trailer', type='string', state='form', ui_kind='text', description='拖车ID'),
            DeclarationEntry(name='manifest', path=f'$.manifest', type='string', state='form', ui_kind='text', description='舱单ID'),
            DeclarationEntry(name='insurance', path=f'$.insurance', type='string', state='form', ui_kind='text', description='保险ID'),
            DeclarationEntry(name='client_expand', path=f'$.client_expand', type='string', state='form', ui_kind='text', description='服务团队—直客拓展'),
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
