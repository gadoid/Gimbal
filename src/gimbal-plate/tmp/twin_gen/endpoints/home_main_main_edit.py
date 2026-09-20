"""fin.main.main_edit —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): main_name, status, king_dee_account_number, main_id, main_no, create_id, create_time, update_id, update_time, fund_code, country_cn_id, country_cn
溯源统计: column=16, lang=13, frontend=7, rule=4, 无zh=3 | fe_high=32, enum=1
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

MAIN_MAIN_EDIT: Final[EndpointSpec] = EndpointSpec(
    id='fin.main.main_edit',
    system='fin',
    service='fin-service',
    name='操作目的',
    description='操作目的' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/home/main/mainEdit',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='main_name_cn', path=f'$.main_name_cn', type='string', state='form', ui_kind='text', description='主体名称'),
            DeclarationEntry(name='main_name_en', path=f'$.main_name_en', type='string', state='form', ui_kind='text', description='英文名称'),
            DeclarationEntry(name='main_name', path=f'$.main_name', type='string', state='form', ui_kind='text', description='公司简称'),  # zh_ambiguous
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='form', ui_kind='select', default='0', description='状态'),  # zh_ambiguous
            DeclarationEntry(name='curator_user_id', path=f'$.curator_user_id', type='string', state='form', ui_kind='text', description='财务负责人'),
            DeclarationEntry(name='is_generate', path=f'$.is_generate', type='string', state='form', ui_kind='select', description='是否产生凭证'),
            DeclarationEntry(name='identity', path=f'$.identity', type='string', state='form', ui_kind='select', description='主体身份'),
            DeclarationEntry(name='enterprise_type', path=f'$.enterprise_type', type='integer', state='form', ui_kind='number', default='1', description='企业身份'),
            DeclarationEntry(name='is_sync', path=f'$.is_sync', type='string', state='form', ui_kind='select', description='是否同步凭证'),
            DeclarationEntry(name='simplified_code', path=f'$.simplified_code', type='string', state='form', ui_kind='text', description='简码'),
            DeclarationEntry(name='tax_number', path=f'$.tax_number', type='string', state='form', ui_kind='text', description='统一社会信用代码'),
            DeclarationEntry(name='address_cn', path=f'$.address_cn', type='string', state='form', ui_kind='text', description='中文详细地址'),
            DeclarationEntry(name='address_en', path=f'$.address_en', type='string', state='form', ui_kind='text', description='英文详细地址'),
            DeclarationEntry(name='remark', path=f'$.remark', type='string', state='form', ui_kind='text', description='备注'),
            DeclarationEntry(name='king_dee_account_number', path=f'$.king_dee_account_number', type='string', state='carry', ui_kind='text', description='金蝶账簿编号'),  # needs_capture:value_source
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='form', ui_kind='number', default='0', description='费用主体ID'),  # zh_ambiguous
            DeclarationEntry(name='main_no', path=f'$.main_no', type='string', state='carry', ui_kind='text', description='主体ID'),  # needs_capture:value_source
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='carry', ui_kind='select', default='0', description='创建人'),  # zh_ambiguous
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='text', default='0', description='创建时间'),  # zh_ambiguous
            DeclarationEntry(name='update_id', path=f'$.update_id', type='integer', state='carry', ui_kind='select', description='更新人'),  # zh_ambiguous
            DeclarationEntry(name='update_time', path=f'$.update_time', type='integer', state='carry', ui_kind='text', default='0', description='更新时间'),  # zh_ambiguous
            DeclarationEntry(name='fund_code', path=f'$.fund_code', type='string', state='carry', ui_kind='text', description='资方编码'),  # zh_ambiguous
            DeclarationEntry(name='country_en_id', path=f'$.country_en_id', type='string', state='form', ui_kind='text', description='英文国家ID'),
            DeclarationEntry(name='country_en', path=f'$.country_en', type='string', state='form', ui_kind='text', description='英文国家'),
            DeclarationEntry(name='province_code', path=f'$.province_code', type='string', state='form', ui_kind='text', description='省code'),
            DeclarationEntry(name='province_name', path=f'$.province_name', type='string', state='form', ui_kind='text', description='省名称'),
            DeclarationEntry(name='city_code', path=f'$.city_code', type='string', state='form', ui_kind='text', description='市code'),
            DeclarationEntry(name='city_name', path=f'$.city_name', type='string', state='form', ui_kind='text', description='市名称'),
            DeclarationEntry(name='county_code', path=f'$.county_code', type='string', state='form', ui_kind='text', description='区code'),
            DeclarationEntry(name='county_name', path=f'$.county_name', type='string', state='form', ui_kind='text', description='区名称'),
            DeclarationEntry(name='king_dee_number', path=f'$.king_dee_number', type='string', state='carry', ui_kind='text', description='金蝶编号'),
            DeclarationEntry(name='king_dee_id', path=f'$.king_dee_id', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='address_cnObj', path=f'$.address_cnObj', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', ui_kind='select', default='submit', description='操作目的', enum=['check', 'submit']),
            DeclarationEntry(name='contact_data', path=f'$.contact_data', type='string', state='form', ui_kind='text', description='联系人信息'),
            DeclarationEntry(name='finance_data', path=f'$.finance_data', type='string', state='form', ui_kind='text', description='开票信息'),
            DeclarationEntry(name='bank_data', path=f'$.bank_data', type='string', state='form', ui_kind='text', description='财务信息'),
            DeclarationEntry(name='country_cn_id', path=f'$.country_cn_id', type='string', state='carry', ui_kind='text', description='中文国家ID'),  # needs_capture:value_source
            DeclarationEntry(name='country_cn', path=f'$.country_cn', type='string', state='carry', ui_kind='text', description='中文国家'),  # needs_capture:value_source
            DeclarationEntry(name='create_by', path=f'$.create_by', type='string', state='carry', ui_kind='text', description='创建人'),
            DeclarationEntry(name='update_by', path=f'$.update_by', type='string', state='carry', ui_kind='text', description='更更新人'),
            DeclarationEntry(name='delete_time', path=f'$.delete_time', type='integer', state='carry', ui_kind='number', description='删除时间'),
            DeclarationEntry(name='sys_upttime', path=f'$.sys_upttime', type='string', state='carry', ui_kind='text'),
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
