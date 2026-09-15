"""fin.order_entrust.change_account_rule —— 孪生生成器产物(请求面;行为面归场景用例)。

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

ORDER_ENTRUST_CHANGE_ACCOUNT_RULE: Final[EndpointSpec] = EndpointSpec(
    id='fin.order_entrust.change_account_rule',
    system='fin',
    service='fin-service',
    name='操作目的',
    description='操作目的' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/order/orderEntrust/changeAccountRule',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='order_id', path=f'$.order_id', type='integer', state='form', required=True, default='0', description='业务订单ID'),
            DeclarationEntry(name='customer_account', path=f'$.customer_account', type='string', state='form'),
            DeclarationEntry(name='supplier_account', path=f'$.supplier_account', type='string', state='form'),
            DeclarationEntry(name='order_supplier_id', path=f'$.order_supplier_id', type='integer', state='form'),
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', default='submit', description='操作目的'),
            DeclarationEntry(name='select_node_user', path=f'$.select_node_user', type='string', state='form'),
            DeclarationEntry(name='audit_msg', path=f'$.audit_msg', type='string', state='form', description='审批回显信息'),
            DeclarationEntry(name='flow_type', path=f'$.flow_type', type='string', state='form', description='审批流配置类型'),
            DeclarationEntry(name='relation_id', path=f'$.relation_id', type='integer', state='form', default='0', description='业务ID'),
            DeclarationEntry(name='policy_type', path=f'$.policy_type', type='string', state='form', description='政策类型'),
            DeclarationEntry(name='customer_period', path=f'$.customer_period', type='integer', state='form', default='0', description='客户账期'),
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
