"""fin.logistics_user.customer_account_detail —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-15T11:13:18+00:00
needs_capture(首跑经 gimbal 执行回填): user_id
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

LOGISTICS_USER_CUSTOMER_ACCOUNT_DETAIL: Final[EndpointSpec] = EndpointSpec(
    id='fin.logistics_user.customer_account_detail',
    system='fin',
    service='fin-service',
    name='LogisticsUser.customerAccountDetail',
    description='LogisticsUser.customerAccountDetail' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/operation/logisticsUser/customerAccountDetail',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='user_id', path=f'$.user_id', type='integer', state='carry', required=True, default='0', description='用户ID'),  # needs_capture:value_source
            DeclarationEntry(name='customer_source', path=f'$.customer_source', type='string', state='form', description='客商类型 01 外贸客户 02供应商'),
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
