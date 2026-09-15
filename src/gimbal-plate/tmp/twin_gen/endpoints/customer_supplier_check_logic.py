"""fin.supplier.check_logic —— 孪生生成器产物(请求面;行为面归场景用例)。

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

SUPPLIER_CHECK_LOGIC: Final[EndpointSpec] = EndpointSpec(
    id='fin.supplier.check_logic',
    system='fin',
    service='fin-service',
    name='Supplier.checkLogic',
    description='Supplier.checkLogic' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/customer/supplier/checkLogic',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='supplier_name', path=f'$.supplier_name', type='string', state='form', description='变更账期供应商'),
            DeclarationEntry(name='tax_number', path=f'$.tax_number', type='string', state='form', description='税号'),
            DeclarationEntry(name='self_support', path=f'$.self_support', type='string', state='form', default='0', description='是否为自营供应商 0否 1是'),
            DeclarationEntry(name='service_items', path=f'$.service_items', type='string', state='form', description='服务项目'),
            DeclarationEntry(name='service_term', path=f'$.service_term', type='integer', state='form', description='自营服务项目账期'),
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
