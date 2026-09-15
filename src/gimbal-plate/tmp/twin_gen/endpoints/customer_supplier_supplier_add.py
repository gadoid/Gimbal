"""fin.supplier.supplier_add —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-15T11:13:18+00:00
needs_capture(首跑经 gimbal 执行回填): supplier_name, tax_number, enterprise_type
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

SUPPLIER_SUPPLIER_ADD: Final[EndpointSpec] = EndpointSpec(
    id='fin.supplier.supplier_add',
    system='fin',
    service='fin-service',
    name='操作目的',
    description='操作目的' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/customer/supplier/supplierAdd',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='supplier_number', path=f'$.supplier_number', type='string', state='carry', description='供应商编号'),
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='form', required=True, description='状态 1未通知 2已通知', enum=['1', '2']),
            DeclarationEntry(name='supplier_name', path=f'$.supplier_name', type='string', state='carry', required=True, description='供应商名称'),  # needs_capture:value_source
            DeclarationEntry(name='tax_number', path=f'$.tax_number', type='string', state='carry', required=True, description='供应商名称'),  # needs_capture:value_source
            DeclarationEntry(name='supplier_name_en', path=f'$.supplier_name_en', type='string', state='carry', description='英文名称'),
            DeclarationEntry(name='self_support', path=f'$.self_support', type='string', state='form', required=True, default='0', description='是否为自营供应商 0否 1是'),
            DeclarationEntry(name='service_term', path=f'$.service_term', type='integer', state='form', description='自营服务项目账期'),
            DeclarationEntry(name='enterprise_type', path=f'$.enterprise_type', type='integer', state='carry', required=True, default='1', description='企业身份'),  # needs_capture:value_source
            DeclarationEntry(name='address_en', path=f'$.address_en', type='string', state='carry', description='英文详细地址'),
            DeclarationEntry(name='remark', path=f'$.remark', type='string', state='carry', description='备注'),
            DeclarationEntry(name='supplier_simple', path=f'$.supplier_simple', type='string', state='carry', description='公司简称'),
            DeclarationEntry(name='supplier_id', path=f'$.supplier_id', type='integer', state='form', default='0', description='变更账期供应商ID'),
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', default='submit', description='操作目的'),
            DeclarationEntry(name='service_items', path=f'$.service_items', type='string', state='form', description='服务项目'),
            DeclarationEntry(name='supplier_contact', path=f'$.supplier_contact', type='string', state='form'),
            DeclarationEntry(name='supplier_finance', path=f'$.supplier_finance', type='string', state='form'),
            DeclarationEntry(name='supplier_file', path=f'$.supplier_file', type='string', state='form'),
            DeclarationEntry(name='order_id', path=f'$.order_id', type='integer', state='form', default='0', description='业务订单ID'),
            DeclarationEntry(name='policy_id', path=f'$.policy_id', type='integer', state='form', default='0', description='服务策略ID'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', default='0', description='客户ID'),
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
