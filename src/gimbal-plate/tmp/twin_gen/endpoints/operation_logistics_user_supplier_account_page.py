"""fin.logistics_user.supplier_account_page —— 孪生生成器产物(请求面;行为面归场景用例)。

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

LOGISTICS_USER_SUPPLIER_ACCOUNT_PAGE: Final[EndpointSpec] = EndpointSpec(
    id='fin.logistics_user.supplier_account_page',
    system='fin',
    service='fin-service',
    name='LogisticsUser.supplierAccountPage',
    description='LogisticsUser.supplierAccountPage' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/operation/logisticsUser/supplierAccountPage',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='page_no', path=f'$.page_no', type='string', state='form'),
            DeclarationEntry(name='page_size', path=f'$.page_size', type='string', state='form'),
            DeclarationEntry(name='customer_source', path=f'$.customer_source', type='string', state='form', description='客商类型 01 外贸客户 02供应商'),
            DeclarationEntry(name='register_source', path=f'$.register_source', type='integer', state='form', default='0', description='注册来源  0产融同步  1轻注册 3轻注册转产融'),
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
