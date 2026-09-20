"""fin.customer.customer_edit —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): status, customer_id, policy_types, settle_type
溯源统计: column=34, 无zh=18, lang=17, derived=1 | fe_high=16, enum=1
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

CUSTOMER_CUSTOMER_EDIT: Final[EndpointSpec] = EndpointSpec(
    id='fin.customer.customer_edit',
    system='fin',
    service='fin-service',
    name='操作目的',
    description='操作目的' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/customer/customer/customerEdit',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='sale', path=f'$.sale', type='integer', state='carry', ui_kind='number', description='销售'),
            DeclarationEntry(name='client_expand_id', path=f'$.client_expand_id', type='integer', state='carry', ui_kind='number', description='直客拓展ID'),
            DeclarationEntry(name='client_expand_name', path=f'$.client_expand_name', type='string', state='carry', ui_kind='text', description='直客拓展用户名称'),
            DeclarationEntry(name='customer_service', path=f'$.customer_service', type='integer', state='carry', ui_kind='number', description='客服'),
            DeclarationEntry(name='operate', path=f'$.operate', type='string', state='carry', ui_kind='text', description='操作'),
            DeclarationEntry(name='customer_discount', path=f'$.customer_discount', type='string', state='carry', ui_kind='text', description='折扣补贴'),
            DeclarationEntry(name='customer_contact', path=f'$.customer_contact', type='string', state='form', ui_kind='text', description='联系人信息'),
            DeclarationEntry(name='customer_bill_lading', path=f'$.customer_bill_lading', type='string', state='form', ui_kind='text', description='收发通'),
            DeclarationEntry(name='customer_finance', path=f'$.customer_finance', type='string', state='form', ui_kind='text', description='财务信息'),
            DeclarationEntry(name='customer_association', path=f'$.customer_association', type='string', state='form', ui_kind='text', description='关联客户名称'),
            DeclarationEntry(name='customer_file', path=f'$.customer_file', type='string', state='form', ui_kind='file', description='附件'),
            DeclarationEntry(name='payment_type', path=f'$.payment_type', type='integer', state='carry', ui_kind='number', default='0', description='付款类型'),
            DeclarationEntry(name='customer_product_rel', path=f'$.customer_product_rel', type='string', state='carry', ui_kind='text', description='产品信息'),
            DeclarationEntry(name='product_ids', path=f'$.product_ids', type='string', state='form', ui_kind='text', description='产品名称列表'),
            DeclarationEntry(name='deposit_refund_day', path=f'$.deposit_refund_day', type='integer', state='carry', ui_kind='number', description='保证金退还周期（天）'),
            DeclarationEntry(name='deposit_settlement_date', path=f'$.deposit_settlement_date', type='integer', state='carry', ui_kind='number', default='0', description='保证金结算日'),
            DeclarationEntry(name='status', path=f'$.status', type='string', state='form', ui_kind='text', default='0', description='状态'),  # zh_ambiguous
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='string', state='form', ui_kind='text', description='id 主键'),  # zh_ambiguous
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', ui_kind='select', default='submit', description='操作目的', enum=['check', 'submit']),
            DeclarationEntry(name='enterprise_type', path=f'$.enterprise_type', type='integer', state='form', ui_kind='number', default='1', description='企业身份'),
            DeclarationEntry(name='policy_types', path=f'$.policy_types', type='string', state='form', ui_kind='text', description='可用政策类型'),  # zh_ambiguous
            DeclarationEntry(name='service_team', path=f'$.service_team', type='string', state='form', ui_kind='text', description='服务团队'),
            DeclarationEntry(name='creation_method', path=f'$.creation_method', type='string', state='form', ui_kind='text', description='创建方式'),
            DeclarationEntry(name='settle_type', path=f'$.settle_type', type='integer', state='form', ui_kind='number', default='0', description='1月结 2票结'),  # zh_ambiguous
            DeclarationEntry(name='deposit_refund_day_error', path=f'$.deposit_refund_day_error', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='customer_no', path=f'$.customer_no', type='string', state='carry', ui_kind='text', description='客户编号'),
            DeclarationEntry(name='customer_name', path=f'$.customer_name', type='string', state='carry', ui_kind='text', description='客户名称'),
            DeclarationEntry(name='customer_name_clean', path=f'$.customer_name_clean', type='string', state='carry', ui_kind='text', description='客户名称，没有括号'),
            DeclarationEntry(name='customer_name_en', path=f'$.customer_name_en', type='string', state='carry', ui_kind='text', description='英文名称'),
            DeclarationEntry(name='customer_simple', path=f'$.customer_simple', type='string', state='carry', ui_kind='text', description='公司简称'),
            DeclarationEntry(name='tax_number', path=f'$.tax_number', type='string', state='carry', ui_kind='text', description='统一社会信用代码'),
            DeclarationEntry(name='company_tel', path=f'$.company_tel', type='string', state='carry', ui_kind='text', description='企业注册电话'),
            DeclarationEntry(name='customer_from', path=f'$.customer_from', type='string', state='carry', ui_kind='text', description='客户来源'),
            DeclarationEntry(name='delivery_receipt_id', path=f'$.delivery_receipt_id', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='customer_category', path=f'$.customer_category', type='string', state='carry', ui_kind='text', description='客户分类'),
            DeclarationEntry(name='business_type', path=f'$.business_type', type='string', state='carry', ui_kind='text', description='业务类型'),
            DeclarationEntry(name='funds', path=f'$.funds', type='string', state='carry', ui_kind='text', description='资方'),
            DeclarationEntry(name='settlement_date', path=f'$.settlement_date', type='string', state='carry', ui_kind='text', description='结算业务客户结算日'),
            DeclarationEntry(name='country_id_cn', path=f'$.country_id_cn', type='string', state='carry', ui_kind='text', description='中文国家id'),
            DeclarationEntry(name='country_name_cn', path=f'$.country_name_cn', type='string', state='carry', ui_kind='text', description='中文'),
            DeclarationEntry(name='province_code', path=f'$.province_code', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='province_name', path=f'$.province_name', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='city_code', path=f'$.city_code', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='city_name', path=f'$.city_name', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='county_code', path=f'$.county_code', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='county_name', path=f'$.county_name', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='address_cn', path=f'$.address_cn', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='country_id_en', path=f'$.country_id_en', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='country_name_en', path=f'$.country_name_en', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='address_en', path=f'$.address_en', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='first_etd', path=f'$.first_etd', type='integer', state='carry', ui_kind='number', description='首单ETD时间'),
            DeclarationEntry(name='last_etd', path=f'$.last_etd', type='integer', state='carry', ui_kind='number', description='末单ETD时间'),
            DeclarationEntry(name='remark', path=f'$.remark', type='string', state='carry', ui_kind='text', description='备注'),
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='create_by', path=f'$.create_by', type='string', state='carry', ui_kind='text', description='创建者'),
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='number', description='创建时间'),
            DeclarationEntry(name='update_id', path=f'$.update_id', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='update_by', path=f'$.update_by', type='string', state='carry', ui_kind='text', description='更新者'),
            DeclarationEntry(name='update_time', path=f'$.update_time', type='integer', state='carry', ui_kind='number', description='更新时间'),
            DeclarationEntry(name='person_in_charge', path=f'$.person_in_charge', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='overdue_payment', path=f'$.overdue_payment', type='integer', state='carry', ui_kind='number', description='是否超期汇款  1是  2否'),
            DeclarationEntry(name='overdue_amount_usd', path=f'$.overdue_amount_usd', type='number', state='carry', ui_kind='number', description='超期金额USD'),
            DeclarationEntry(name='overdue_amount_cny', path=f'$.overdue_amount_cny', type='number', state='carry', ui_kind='number', description='超期金额CNY'),
            DeclarationEntry(name='overdue_time', path=f'$.overdue_time', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='period_rule', path=f'$.period_rule', type='string', state='carry', ui_kind='text', description='废弃 125日后订单截转下月计算账期 2按ATD本月计算账期'),
            DeclarationEntry(name='king_dee_number', path=f'$.king_dee_number', type='string', state='carry', ui_kind='text', description='金蝶系统编号'),
            DeclarationEntry(name='king_dee_id', path=f'$.king_dee_id', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='sys_upttime', path=f'$.sys_upttime', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='period_delay_type', path=f'$.period_delay_type', type='integer', state='carry', ui_kind='number', description='客户账期类型 1延长 2不延长'),
            DeclarationEntry(name='receive_time_limit', path=f'$.receive_time_limit', type='integer', state='carry', ui_kind='number', description='回款时效'),
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
