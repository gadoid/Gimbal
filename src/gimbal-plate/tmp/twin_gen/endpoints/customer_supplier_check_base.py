"""fin.supplier.check_base —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-15T11:13:18+00:00
needs_capture(首跑经 gimbal 执行回填): contacts_name
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

SUPPLIER_CHECK_BASE: Final[EndpointSpec] = EndpointSpec(
    id='fin.supplier.check_base',
    system='fin',
    service='fin-service',
    name='Supplier.checkBase',
    description='Supplier.checkBase' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/customer/supplier/checkBase',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='contacts_name', path=f'$.contacts_name', type='string', state='carry', required=True, description='姓名'),  # needs_capture:value_source
            DeclarationEntry(name='duties', path=f'$.duties', type='string', state='carry', description='职务'),
            DeclarationEntry(name='phone', path=f'$.phone', type='string', state='carry', description='电话'),
            DeclarationEntry(name='fax', path=f'$.fax', type='string', state='carry', description='传真'),
            DeclarationEntry(name='email', path=f'$.email', type='string', state='carry', description='邮箱'),
            DeclarationEntry(name='is_default_receive_email', path=f'$.is_default_receive_email', type='integer', state='carry', default='0', description='默认收件邮箱', enum=['0', '1']),
            DeclarationEntry(name='is_default_cc_email', path=f'$.is_default_cc_email', type='integer', state='carry', default='0', description='默认抄送邮箱', enum=['0', '1']),
            DeclarationEntry(name='skype', path=f'$.skype', type='string', state='carry', description='skype'),
            DeclarationEntry(name='remark', path=f'$.remark', type='string', state='carry', description='备注'),
            DeclarationEntry(name='self_support', path=f'$.self_support', type='string', state='form', default='0', description='是否为自营供应商 0否 1是'),
            DeclarationEntry(name='service_items', path=f'$.service_items', type='string', state='form', description='服务项目'),
            DeclarationEntry(name='service_term', path=f'$.service_term', type='integer', state='form', description='自营服务项目账期'),
            DeclarationEntry(name='supplier_contact', path=f'$.supplier_contact', type='string', state='form'),
            DeclarationEntry(name='supplier_finance', path=f'$.supplier_finance', type='string', state='form'),
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
