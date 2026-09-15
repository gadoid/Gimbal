"""fin.order.batch_edit_settle_object —— 孪生生成器产物(请求面;行为面归场景用例)。

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

ORDER_BATCH_EDIT_SETTLE_OBJECT: Final[EndpointSpec] = EndpointSpec(
    id='fin.order.batch_edit_settle_object',
    system='fin',
    service='fin-service',
    name='操作目的',
    description='操作目的' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/order/order/batchEditSettleObject',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', description='操作目的'),
            DeclarationEntry(name='modify_type', path=f'$.modify_type', type='string', state='form'),
            DeclarationEntry(name='symbol', path=f'$.symbol', type='integer', state='form', default='0', description='应收应付 0 应付  1应收'),
            DeclarationEntry(name='order_id', path=f'$.order_id', type='integer', state='form', default='0', description='业务订单ID'),
            DeclarationEntry(name='checkData', path=f'$.checkData', type='string', state='form'),
            DeclarationEntry(name='settle_object', path=f'$.settle_object', type='string', state='form'),
            DeclarationEntry(name='currency', path=f'$.currency', type='string', state='form', description='币值'),
            DeclarationEntry(name='service_project', path=f'$.service_project', type='string', state='form', description='服务项目'),
            DeclarationEntry(name='old_put_settle_object_id', path=f'$.old_put_settle_object_id', type='string', state='form'),
            DeclarationEntry(name='old_pay_settle_object_id', path=f'$.old_pay_settle_object_id', type='string', state='form'),
            DeclarationEntry(name='put_settle_object_id', path=f'$.put_settle_object_id', type='integer', state='form', default='0', description='应收结算对象ID'),
            DeclarationEntry(name='pay_settle_object_id', path=f'$.pay_settle_object_id', type='integer', state='form', default='0', description='应收结算对象ID'),
            DeclarationEntry(name='settle_object_id', path=f'$.settle_object_id', type='integer', state='form', default='0', description='超期应收结算对象'),
            DeclarationEntry(name='voucher_fee_real_ids', path=f'$.voucher_fee_real_ids', type='string', state='form'),
            DeclarationEntry(name='sorce', path=f'$.sorce', type='string', state='form', description='对象来源  main 主体  supplier 供应商  customer 客户'),
            DeclarationEntry(name='relation_id', path=f'$.relation_id', type='integer', state='form', default='0', description='业务ID'),
            DeclarationEntry(name='unique_id', path=f'$.unique_id', type='string', state='form', description='唯一标记  同源费用标记一致'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', default='0', description='客户ID'),
            DeclarationEntry(name='self_support', path=f'$.self_support', type='string', state='form', default='0', description='是否为自营供应商 0否 1是'),
            DeclarationEntry(name='service_item', path=f'$.service_item', type='string', state='form', description='服务项目'),
            DeclarationEntry(name='unique', path=f'$.unique', type='string', state='form'),
            DeclarationEntry(name='settle_object_type', path=f'$.settle_object_type', type='string', state='form', description='结算对象类型 customer客户/supplier供应商'),
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
