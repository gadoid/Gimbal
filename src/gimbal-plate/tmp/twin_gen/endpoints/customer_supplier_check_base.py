"""fin.supplier.check_base —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): contacts_name
溯源统计: rule=9, lang=3, column=2 | fe_high=0, enum=2
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
            DeclarationEntry(name='contacts_name', path=f'$.contacts_name', type='string', state='carry', ui_kind='text', description='姓名'),  # needs_capture:value_source
            DeclarationEntry(name='duties', path=f'$.duties', type='string', state='carry', ui_kind='text', description='职务'),
            DeclarationEntry(name='phone', path=f'$.phone', type='string', state='carry', ui_kind='text', description='电话'),
            DeclarationEntry(name='fax', path=f'$.fax', type='string', state='carry', ui_kind='text', description='传真'),
            DeclarationEntry(name='email', path=f'$.email', type='string', state='carry', ui_kind='text', description='邮箱'),
            DeclarationEntry(name='is_default_receive_email', path=f'$.is_default_receive_email', type='integer', state='carry', ui_kind='select', default='0', description='默认收件邮箱', enum=['0', '1']),
            DeclarationEntry(name='is_default_cc_email', path=f'$.is_default_cc_email', type='integer', state='carry', ui_kind='select', default='0', description='默认抄送邮箱', enum=['0', '1']),
            DeclarationEntry(name='skype', path=f'$.skype', type='string', state='carry', ui_kind='text', description='skype'),
            DeclarationEntry(name='remark', path=f'$.remark', type='string', state='carry', ui_kind='text', description='备注'),
            DeclarationEntry(name='self_support', path=f'$.self_support', type='string', state='form', ui_kind='text', default='0', description='是否为自营供应商'),
            DeclarationEntry(name='service_items', path=f'$.service_items', type='string', state='form', ui_kind='text', description='自营服务项目 1报关 2舱单 3保险 4拖车'),
            DeclarationEntry(name='service_term', path=f'$.service_term', type='integer', state='form', ui_kind='number', description='自营服务项目账期'),
            DeclarationEntry(name='supplier_contact', path=f'$.supplier_contact', type='array', state='form', ui_kind='unknown', description='联系人信息',
                children=[
                DeclarationEntry(name='contacts_name', path=f'$.supplier_contact.contacts_name', type='string', state='form', ui_kind='text', description='姓名'),
                DeclarationEntry(name='duties', path=f'$.supplier_contact.duties', type='string', state='form', ui_kind='text', description='职务'),
                DeclarationEntry(name='phone', path=f'$.supplier_contact.phone', type='string', state='form', ui_kind='text', description='电话'),
                DeclarationEntry(name='fax', path=f'$.supplier_contact.fax', type='string', state='form', ui_kind='text', description='传真'),
                DeclarationEntry(name='email', path=f'$.supplier_contact.email', type='string', state='form', ui_kind='text', description='邮箱'),
                DeclarationEntry(name='is_default_receive_email', path=f'$.supplier_contact.is_default_receive_email', type='integer', state='form', ui_kind='select', description='默认收件邮箱', enum=['0', '1']),
                DeclarationEntry(name='is_default_cc_email', path=f'$.supplier_contact.is_default_cc_email', type='integer', state='form', ui_kind='select', description='默认抄送邮箱', enum=['0', '1']),
                DeclarationEntry(name='skype', path=f'$.supplier_contact.skype', type='string', state='form', ui_kind='text', description='skype'),
                DeclarationEntry(name='remark', path=f'$.supplier_contact.remark', type='string', state='form', ui_kind='text', description='备注'),
                ]),
            DeclarationEntry(name='supplier_finance', path=f'$.supplier_finance', type='array', state='form', ui_kind='unknown', description='财务信息',
                children=[
                DeclarationEntry(name='chinese_header', path=f'$.supplier_finance.chinese_header', type='string', state='form', ui_kind='text', description='中文抬头'),
                DeclarationEntry(name='english_header', path=f'$.supplier_finance.english_header', type='string', state='form', ui_kind='text', description='英文抬头'),
                DeclarationEntry(name='identifier_no', path=f'$.supplier_finance.identifier_no', type='string', state='form', ui_kind='text', description='纳税人识别号'),
                DeclarationEntry(name='phone', path=f'$.supplier_finance.phone', type='string', state='form', ui_kind='text', description='电话'),
                DeclarationEntry(name='currency', path=f'$.supplier_finance.currency', type='string', state='form', ui_kind='select', description='账户类型', enum=['CNY', 'USD']),  # zh_ambiguous
                DeclarationEntry(name='bank_account', path=f'$.supplier_finance.bank_account', type='string', state='form', ui_kind='text', description='银行账号'),
                DeclarationEntry(name='swift_code', path=f'$.supplier_finance.swift_code', type='string', state='form', ui_kind='text', description='swift code'),
                DeclarationEntry(name='register_address', path=f'$.supplier_finance.register_address', type='string', state='form', ui_kind='text', description='注册地址'),
                DeclarationEntry(name='open_bank_cn', path=f'$.supplier_finance.open_bank_cn', type='string', state='form', ui_kind='text', description='开户行'),
                DeclarationEntry(name='bank_status', path=f'$.supplier_finance.bank_status', type='integer', state='form', ui_kind='number', required=True, description='账户状态'),
                DeclarationEntry(name='remark', path=f'$.supplier_finance.remark', type='string', state='form', ui_kind='text', description='备注'),
                ]),
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
