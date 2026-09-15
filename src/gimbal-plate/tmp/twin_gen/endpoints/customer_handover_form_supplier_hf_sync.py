"""fin.handover_form.supplier_hf_sync —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-15T11:13:18+00:00
needs_capture(首跑经 gimbal 执行回填): tax_number, crm_forwarder_id, sale_support, sale_name, service_name
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

HANDOVER_FORM_SUPPLIER_HF_SYNC: Final[EndpointSpec] = EndpointSpec(
    id='fin.handover_form.supplier_hf_sync',
    system='fin',
    service='fin-service',
    name='HandoverForm.supplierHfSync',
    description='HandoverForm.supplierHfSync' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/customer/handoverForm/supplierHfSync',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='customer_name', path=f'$.customer_name', type='string', state='carry', required=True, description='客户名称,', value_source=ValueSource(view='customer_list', column='customer_name')),
            DeclarationEntry(name='tax_number', path=f'$.tax_number', type='string', state='carry', required=True, description='社会统一信用证代码'),  # needs_capture:value_source
            DeclarationEntry(name='crm_forwarder_id', path=f'$.crm_forwarder_id', type='string', state='carry', required=True, description='交接单id'),  # needs_capture:value_source
            DeclarationEntry(name='sale_support', path=f'$.sale_support', type='string', state='carry', required=True, description='销售支持姓名'),  # needs_capture:value_source
            DeclarationEntry(name='sale_name', path=f'$.sale_name', type='string', state='carry', required=True, description='销售姓名'),  # needs_capture:value_source
            DeclarationEntry(name='service_name', path=f'$.service_name', type='string', state='carry', required=True, description='客服姓名'),  # needs_capture:value_source
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
