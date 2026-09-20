"""fin.customer.check_base —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): client_expand_id, customer_service
溯源统计: rule=4, 无zh=4, lang=4 | fe_high=0, enum=0
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
            DeclarationEntry(name='client_expand_id', path=f'$.client_expand_id', type='integer', state='carry', ui_kind='number', description='直客拓展'),  # needs_capture:value_source
            DeclarationEntry(name='customer_service', path=f'$.customer_service', type='integer', state='carry', ui_kind='number', description='客服'),  # needs_capture:value_source
            DeclarationEntry(name='operate', path=f'$.operate', type='string', state='carry', ui_kind='text', description='操作ID'),
            DeclarationEntry(name='sale', path=f'$.sale', type='integer', state='carry', ui_kind='number', description='销售'),
            DeclarationEntry(name='customer_team', path=f'$.customer_team', type='array', state='form', ui_kind='unknown',
                children=[
                DeclarationEntry(name='client_expand_id', path=f'$.customer_team.client_expand_id', type='integer', state='form', ui_kind='number', description='直客拓展'),
                DeclarationEntry(name='customer_service', path=f'$.customer_team.customer_service', type='integer', state='form', ui_kind='number', description='客服'),
                DeclarationEntry(name='operate', path=f'$.customer_team.operate', type='string', state='form', ui_kind='text', description='操作ID'),
                DeclarationEntry(name='sale', path=f'$.customer_team.sale', type='integer', state='form', ui_kind='number', description='销售'),
                ]),
            DeclarationEntry(name='customer_contact', path=f'$.customer_contact', type='array', state='form', ui_kind='unknown', description='联系人信息',
                children=[
                DeclarationEntry(name='contacts_name', path=f'$.customer_contact.contacts_name', type='string', state='form', ui_kind='text', description='姓名'),
                DeclarationEntry(name='duties', path=f'$.customer_contact.duties', type='string', state='form', ui_kind='text', description='职务'),
                DeclarationEntry(name='phone', path=f'$.customer_contact.phone', type='string', state='form', ui_kind='text', description='电话'),
                DeclarationEntry(name='fax', path=f'$.customer_contact.fax', type='string', state='form', ui_kind='text', description='传真'),
                DeclarationEntry(name='email', path=f'$.customer_contact.email', type='string', state='form', ui_kind='text', description='邮箱'),
                DeclarationEntry(name='skype', path=f'$.customer_contact.skype', type='string', state='form', ui_kind='text', description='skype'),
                DeclarationEntry(name='remark', path=f'$.customer_contact.remark', type='string', state='form', ui_kind='text', description='备注'),
                ]),
            DeclarationEntry(name='customer_bill_lading', path=f'$.customer_bill_lading', type='array', state='form', ui_kind='unknown', description='收发通',
                children=[
                DeclarationEntry(name='header', path=f'$.customer_bill_lading.header', type='string', state='form', ui_kind='text', description='抬头'),
                ]),
            DeclarationEntry(name='customer_finance', path=f'$.customer_finance', type='array', state='form', ui_kind='unknown', description='财务信息',
                children=[
                DeclarationEntry(name='english_header', path=f'$.customer_finance.english_header', type='string', state='form', ui_kind='text', description='英文抬头'),
                DeclarationEntry(name='phone', path=f'$.customer_finance.phone', type='string', state='form', ui_kind='text', description='电话'),
                DeclarationEntry(name='bank_account', path=f'$.customer_finance.bank_account', type='string', state='form', ui_kind='text', description='银行账号'),
                DeclarationEntry(name='currency', path=f'$.customer_finance.currency', type='string', state='form', ui_kind='text', description='银行账号'),  # zh_ambiguous
                DeclarationEntry(name='swift_code', path=f'$.customer_finance.swift_code', type='string', state='form', ui_kind='text', description='swift code'),
                DeclarationEntry(name='register_address', path=f'$.customer_finance.register_address', type='string', state='form', ui_kind='text', description='注册地址'),
                DeclarationEntry(name='open_bank_cn', path=f'$.customer_finance.open_bank_cn', type='string', state='form', ui_kind='text', description='开户行'),
                DeclarationEntry(name='bank_status', path=f'$.customer_finance.bank_status', type='integer', state='form', ui_kind='number', required=True, description='账户状态'),
                DeclarationEntry(name='remark', path=f'$.customer_finance.remark', type='string', state='form', ui_kind='text', description='备注'),
                ]),
            DeclarationEntry(name='customer_association', path=f'$.customer_association', type='array', state='form', ui_kind='unknown', description='关联客户名称',
                children=[
                DeclarationEntry(name='belong_id', path=f'$.customer_association.belong_id', type='string', state='form', ui_kind='text', description='客户ID'),
                DeclarationEntry(name='belong_style', path=f'$.customer_association.belong_style', type='string', state='form', ui_kind='text', description='客户类型'),
                ]),
            DeclarationEntry(name='county_code', path=f'$.county_code', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='city_code', path=f'$.city_code', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='province_code', path=f'$.province_code', type='string', state='form', ui_kind='text'),
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
