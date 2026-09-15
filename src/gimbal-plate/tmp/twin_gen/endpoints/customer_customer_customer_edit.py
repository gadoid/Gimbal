"""fin.customer.customer_edit —— 孪生生成器产物(请求面;行为面归场景用例)。

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

CUSTOMER_CUSTOMER_EDIT: Final[EndpointSpec] = EndpointSpec(
    id='fin.customer.customer_edit',
    system='fin',
    service='fin-service',
    name='操作目的',
    description='操作目的' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/customer/customer/customerEdit',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='form', default='0', description='状态 1未通知 2已通知'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', default='0', description='客户ID'),
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', default='submit', description='操作目的'),
            DeclarationEntry(name='enterprise_type', path=f'$.enterprise_type', type='integer', state='form', default='1', description='企业身份  1境内企业 2境外企业 3境外企业-港澳台企业 4境外企业-海外企业'),
            DeclarationEntry(name='policy_types', path=f'$.policy_types', type='string', state='form', description='可用政策类型'),
            DeclarationEntry(name='product_ids', path=f'$.product_ids', type='string', state='form'),
            DeclarationEntry(name='service_team', path=f'$.service_team', type='string', state='form'),
            DeclarationEntry(name='creation_method', path=f'$.creation_method', type='string', state='form', description='创建方式'),
            DeclarationEntry(name='customer_contact', path=f'$.customer_contact', type='string', state='form'),
            DeclarationEntry(name='customer_bill_lading', path=f'$.customer_bill_lading', type='string', state='form'),
            DeclarationEntry(name='customer_finance', path=f'$.customer_finance', type='string', state='form'),
            DeclarationEntry(name='customer_association', path=f'$.customer_association', type='string', state='form'),
            DeclarationEntry(name='customer_file', path=f'$.customer_file', type='string', state='form'),
            DeclarationEntry(name='settle_type', path=f'$.settle_type', type='integer', state='form', default='0', description='1月结 2票结'),
            DeclarationEntry(name='deposit_refund_day_error', path=f'$.deposit_refund_day_error', type='string', state='form'),
            DeclarationEntry(name='order_id', path=f'$.order_id', type='integer', state='form', default='0', description='业务订单ID'),
            DeclarationEntry(name='policy_id', path=f'$.policy_id', type='integer', state='form', default='0', description='服务策略ID'),
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
