"""fin.order_entrust.batch_change_related —— 孪生生成器产物(请求面;行为面归场景用例)。

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

ORDER_ENTRUST_BATCH_CHANGE_RELATED: Final[EndpointSpec] = EndpointSpec(
    id='fin.order_entrust.batch_change_related',
    system='fin',
    service='fin-service',
    name='OrderEntrust.batchChangeRelated',
    description='OrderEntrust.batchChangeRelated' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/order/orderEntrust/batchChangeRelated',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='order_ids', path=f'$.order_ids', type='string', state='form', required=True, description='客户ID'),
            DeclarationEntry(name='sale', path=f'$.sale', type='integer', state='form', description='销售ID'),
            DeclarationEntry(name='customer_service', path=f'$.customer_service', type='integer', state='form', description='客服ID'),
            DeclarationEntry(name='operate', path=f'$.operate', type='string', state='form', description='操作'),
            DeclarationEntry(name='book', path=f'$.book', type='string', state='form', description='订舱ID'),
            DeclarationEntry(name='bill', path=f'$.bill', type='string', state='form', description='报关ID'),
            DeclarationEntry(name='trailer', path=f'$.trailer', type='string', state='form', description='拖车ID'),
            DeclarationEntry(name='manifest', path=f'$.manifest', type='string', state='form', description='舱单ID'),
            DeclarationEntry(name='insurance', path=f'$.insurance', type='string', state='form', description='保险ID'),
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
