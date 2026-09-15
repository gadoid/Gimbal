"""fin.customer.check_base —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-15T11:13:18+00:00
needs_capture(首跑经 gimbal 执行回填): client_expand_id, customer_service
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

CUSTOMER_CHECK_BASE: Final[EndpointSpec] = EndpointSpec(
    id='fin.customer.check_base',
    system='fin',
    service='fin-service',
    name='Customer.checkBase',
    description='Customer.checkBase' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/customer/customer/checkBase',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='client_expand_id', path=f'$.client_expand_id', type='integer', state='carry', required=True, description='直客拓展'),  # needs_capture:value_source
            DeclarationEntry(name='customer_service', path=f'$.customer_service', type='integer', state='carry', required=True, description='客服'),  # needs_capture:value_source
            DeclarationEntry(name='operate', path=f'$.operate', type='string', state='carry', description='操作ID'),
            DeclarationEntry(name='sale', path=f'$.sale', type='integer', state='carry', description='销售'),
            DeclarationEntry(name='customer_team', path=f'$.customer_team', type='string', state='form'),
            DeclarationEntry(name='customer_contact', path=f'$.customer_contact', type='string', state='form'),
            DeclarationEntry(name='customer_bill_lading', path=f'$.customer_bill_lading', type='string', state='form'),
            DeclarationEntry(name='customer_finance', path=f'$.customer_finance', type='string', state='form'),
            DeclarationEntry(name='customer_association', path=f'$.customer_association', type='string', state='form'),
            DeclarationEntry(name='county_code', path=f'$.county_code', type='string', state='form'),
            DeclarationEntry(name='city_code', path=f'$.city_code', type='string', state='form'),
            DeclarationEntry(name='province_code', path=f'$.province_code', type='string', state='form'),
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
