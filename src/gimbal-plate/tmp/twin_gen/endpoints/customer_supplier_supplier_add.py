"""fin.supplier.supplier_add —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): status, supplier_name, tax_number, enterprise_type, create_id, create_time, update_time, settlement_date, supplier_id
溯源统计: column=13, 无zh=11, rule=7, lang=7, frontend=6 | fe_high=25, enum=2
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
            DeclarationEntry(name='supplier_number', path=f'$.supplier_number', type='string', state='carry', ui_kind='text', description='供应商编号'),
            DeclarationEntry(name='status', path=f'$.status', type='string', state='form', ui_kind='select', description='创建状态', enum=['1', '2']),  # zh_ambiguous
            DeclarationEntry(name='supplier_name', path=f'$.supplier_name', type='string', state='carry', ui_kind='text', description='供应商名称'),  # needs_capture:value_source
            DeclarationEntry(name='tax_number', path=f'$.tax_number', type='string', state='carry', ui_kind='text', description='供应商名称'),  # needs_capture:value_source
            DeclarationEntry(name='supplier_name_en', path=f'$.supplier_name_en', type='string', state='carry', ui_kind='text', description='英文名称'),
            DeclarationEntry(name='self_support', path=f'$.self_support', type='string', state='form', ui_kind='text', default='0', description='是否为自营供应商'),
            DeclarationEntry(name='service_term', path=f'$.service_term', type='integer', state='form', ui_kind='number', description='自营服务项目账期'),
            DeclarationEntry(name='enterprise_type', path=f'$.enterprise_type', type='integer', state='carry', ui_kind='number', default='1', description='企业身份'),  # needs_capture:value_source
            DeclarationEntry(name='address_en', path=f'$.address_en', type='string', state='carry', ui_kind='text', description='英文详细地址'),
            DeclarationEntry(name='remark', path=f'$.remark', type='string', state='carry', ui_kind='text', description='备注'),
            DeclarationEntry(name='supplier_simple', path=f'$.supplier_simple', type='string', state='carry', ui_kind='text', description='公司简称'),
            DeclarationEntry(name='service_items', path=f'$.service_items', type='string', state='form', ui_kind='text', description='自营服务项目 1报关 2舱单 3保险 4拖车'),
            DeclarationEntry(name='supplier_category', path=f'$.supplier_category', type='string', state='carry', ui_kind='text', description='供应商分类'),
            DeclarationEntry(name='business_type', path=f'$.business_type', type='string', state='carry', ui_kind='text', description='业务类型'),
            DeclarationEntry(name='country_id_cn', path=f'$.country_id_cn', type='string', state='carry', ui_kind='text', description='中文国家id'),
            DeclarationEntry(name='province_code', path=f'$.province_code', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='city_code', path=f'$.city_code', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='county_code', path=f'$.county_code', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='address_cn', path=f'$.address_cn', type='string', state='carry', ui_kind='text', description='中文地址'),
            DeclarationEntry(name='address_cnObj', path=f'$.address_cnObj', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='supplier_no', path=f'$.supplier_no', type='string', state='carry', ui_kind='text', description='供应商ID'),
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='carry', ui_kind='select', default='0', description='创建人'),  # zh_ambiguous
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='text', description='创建时间'),  # zh_ambiguous
            DeclarationEntry(name='update_id', path=f'$.update_id', type='integer', state='carry', ui_kind='select', default='0', description='更新人'),
            DeclarationEntry(name='update_time', path=f'$.update_time', type='integer', state='carry', ui_kind='text', description='更新时间'),  # zh_ambiguous
            DeclarationEntry(name='settlement_date', path=f'$.settlement_date', type='string', state='carry', ui_kind='text', default='10', description='供应商结算日'),  # zh_ambiguous
            DeclarationEntry(name='country_name_cn', path=f'$.country_name_cn', type='string', state='carry', ui_kind='text', description='中文'),
            DeclarationEntry(name='supplier_id', path=f'$.supplier_id', type='integer', state='form', ui_kind='number', default='0', description='供应商ID'),  # zh_ambiguous
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', ui_kind='select', default='submit', description='操作目的', enum=['check', 'submit']),
            DeclarationEntry(name='supplier_contact', path=f'$.supplier_contact', type='string', state='form', ui_kind='text', description='联系人信息'),
            DeclarationEntry(name='supplier_finance', path=f'$.supplier_finance', type='string', state='form', ui_kind='text', description='财务信息'),
            DeclarationEntry(name='supplier_file', path=f'$.supplier_file', type='string', state='form', ui_kind='file', description='附件'),
            DeclarationEntry(name='supplier_name_clean', path=f'$.supplier_name_clean', type='string', state='carry', ui_kind='text', description='供应商名称,没有括号'),
            DeclarationEntry(name='supplier_category2', path=f'$.supplier_category2', type='string', state='carry', ui_kind='text', description='供应商分类-二级'),
            DeclarationEntry(name='province_name', path=f'$.province_name', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='city_name', path=f'$.city_name', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='county_name', path=f'$.county_name', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='country_id_en', path=f'$.country_id_en', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='country_name_en', path=f'$.country_name_en', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='create_by', path=f'$.create_by', type='string', state='carry', ui_kind='text', description='创建者'),
            DeclarationEntry(name='update_by', path=f'$.update_by', type='string', state='carry', ui_kind='text', description='更新者'),
            DeclarationEntry(name='king_dee_number', path=f'$.king_dee_number', type='string', state='carry', ui_kind='text', description='金蝶系统编号'),
            DeclarationEntry(name='king_dee_id', path=f'$.king_dee_id', type='integer', state='carry', ui_kind='number'),
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
