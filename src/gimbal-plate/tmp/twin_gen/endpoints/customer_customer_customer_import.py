"""fin.customer.customer_import —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): policy_types, customer_id, settle_type
溯源统计: lang=8, column=3, derived=1, 无zh=1 | fe_high=0, enum=0
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

CUSTOMER_CUSTOMER_IMPORT: Final[EndpointSpec] = EndpointSpec(
    id='fin.customer.customer_import',
    system='fin',
    service='fin-service',
    name='Customer.customerImport',
    description='Customer.customerImport' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/customer/customer/customerImport',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='enterprise_type', path=f'$.enterprise_type', type='integer', state='form', ui_kind='number', default='1', description='企业身份'),
            DeclarationEntry(name='policy_types', path=f'$.policy_types', type='string', state='form', ui_kind='text', description='可用政策类型'),  # zh_ambiguous
            DeclarationEntry(name='product_ids', path=f'$.product_ids', type='string', state='form', ui_kind='text', description='产品名称列表'),
            DeclarationEntry(name='service_team', path=f'$.service_team', type='string', state='form', ui_kind='text', description='服务团队'),
            DeclarationEntry(name='creation_method', path=f'$.creation_method', type='string', state='form', ui_kind='text', description='创建方式'),
            DeclarationEntry(name='customer_contact', path=f'$.customer_contact', type='string', state='form', ui_kind='text', description='联系人信息'),
            DeclarationEntry(name='customer_bill_lading', path=f'$.customer_bill_lading', type='string', state='form', ui_kind='text', description='收发通'),
            DeclarationEntry(name='customer_finance', path=f'$.customer_finance', type='string', state='form', ui_kind='text', description='财务信息'),
            DeclarationEntry(name='customer_association', path=f'$.customer_association', type='string', state='form', ui_kind='text', description='关联客户名称'),
            DeclarationEntry(name='customer_file', path=f'$.customer_file', type='string', state='form', ui_kind='file', description='附件'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='string', state='form', ui_kind='text', description='id 主键'),  # zh_ambiguous
            DeclarationEntry(name='settle_type', path=f'$.settle_type', type='integer', state='form', ui_kind='number', default='0', description='1月结 2票结'),  # zh_ambiguous
            DeclarationEntry(name='deposit_refund_day_error', path=f'$.deposit_refund_day_error', type='string', state='form', ui_kind='text'),
        ],
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description='成功(信封统一;data 行形状归场景用例)',
            declarations=[
            DeclarationEntry(name='code', path='$.code', type='number',
                             required=False, ui_kind='number',
                             description='业务状态码(200=成功)', assertable=True),
            DeclarationEntry(name='msg', path='$.msg', type='string',
                             required=False, ui_kind='text',
                             description='业务提示信息', assertable=True),
            DeclarationEntry(name='data', path='$.data', type='object',
                             required=False, ui_kind='json',
                             description='业务数据(行形状归场景用例)', assertable=True),
            DeclarationEntry(name='request_id', path='$.request_id', type='string',
                             required=False, ui_kind='text',
                             description='请求追踪ID', assertable=True),

            ],
        ),
    },
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module=FIN_DEFAULT_MODULE,
        owner=FIN_DEFAULT_OWNER,
        tags=list(FIN_DEFAULT_TAGS),
    ),
)
