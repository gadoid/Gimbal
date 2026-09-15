"""fin.pay_demand.payment_list —— 孪生生成器产物(请求面;行为面归场景用例)。

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

PAY_DEMAND_PAYMENT_LIST: Final[EndpointSpec] = EndpointSpec(
    id='fin.pay_demand.payment_list',
    system='fin',
    service='fin-service',
    name='PayDemand.paymentList',
    description='PayDemand.paymentList' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/payDemand/paymentList',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='split_dimension', path=f'$.split_dimension', type='string', state='form', description='拆分维度'),
            DeclarationEntry(name='operation_type', path=f'$.operation_type', type='integer', state='form', default='0', description='需求选择类型 0费用 1提单'),
            DeclarationEntry(name='select_list', path=f'$.select_list', type='string', state='form'),
            DeclarationEntry(name='pay_demand_name', path=f'$.pay_demand_name', type='string', state='form', description='付款需求名称'),
            DeclarationEntry(name='payment_list', path=f'$.payment_list', type='string', state='form'),
            DeclarationEntry(name='pay_settle_object_id', path=f'$.pay_settle_object_id', type='integer', state='form', default='0', description='应收结算对象ID'),
            DeclarationEntry(name='cost_ids', path=f'$.cost_ids', type='string', state='form'),
            DeclarationEntry(name='service_project', path=f'$.service_project', type='string', state='form', description='服务项目'),
            DeclarationEntry(name='payment_type', path=f'$.payment_type', type='integer', state='form', default='0', description='付款类型 1确定性付款 2非确定性付款'),
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
