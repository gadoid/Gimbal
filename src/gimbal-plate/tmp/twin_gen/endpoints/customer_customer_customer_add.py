"""fin.customer.customer_add —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-15T11:13:18+00:00
needs_capture(首跑经 gimbal 执行回填): tax_number
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

CUSTOMER_CUSTOMER_ADD: Final[EndpointSpec] = EndpointSpec(
    id='fin.customer.customer_add',
    system='fin',
    service='fin-service',
    name='操作目的',
    description='操作目的' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/customer/customer/customerAdd',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='customer_name', path=f'$.customer_name', type='string', state='carry', required=True, description='客户名称', value_source=ValueSource(view='customer_list', column='customer_name')),
            DeclarationEntry(name='customer_name_en', path=f'$.customer_name_en', type='string', state='carry', description='英文名称'),
            DeclarationEntry(name='company_tel', path=f'$.company_tel', type='string', state='carry', description='企业注册电话'),
            DeclarationEntry(name='tax_number', path=f'$.tax_number', type='string', state='carry', required=True, description='税号'),  # needs_capture:value_source
            DeclarationEntry(name='customer_from', path=f'$.customer_from', type='string', state='carry', description='客户来源'),
            DeclarationEntry(name='customer_category', path=f'$.customer_category', type='string', state='carry', description='客户分类'),
            DeclarationEntry(name='business_type', path=f'$.business_type', type='string', state='carry', description='业务类型'),
            DeclarationEntry(name='policy_types', path=f'$.policy_types', type='string', state='form', required=True, description='可用政策类型'),
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='form', required=True, description='状态 1未通知 2已通知', enum=['1', '2']),
            DeclarationEntry(name='address_cn', path=f'$.address_cn', type='string', state='carry', description='中文详细地址'),
            DeclarationEntry(name='address_en', path=f'$.address_en', type='string', state='carry', description='英文详细地址'),
            DeclarationEntry(name='remark', path=f'$.remark', type='string', state='carry', description='备注'),
            DeclarationEntry(name='receive_time_limit', path=f'$.receive_time_limit', type='integer', state='carry', description='回款时效'),
            DeclarationEntry(name='deposit_refund_day', path=f'$.deposit_refund_day', type='integer', state='carry', description='保证金退还周期  单位天'),
            DeclarationEntry(name='enterprise_type', path=f'$.enterprise_type', type='integer', state='form', required=True, default='1', description='企业身份'),
            DeclarationEntry(name='customer_simple', path=f'$.customer_simple', type='string', state='carry', description='公司简称'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', default='0', description='客户ID'),
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', default='submit', description='操作目的'),
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
