"""fin.customer.subsidy_edit —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): customer_id
溯源统计: column=41, 无zh=22, rule=1 | fe_high=0, enum=1
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

CUSTOMER_SUBSIDY_EDIT: Final[EndpointSpec] = EndpointSpec(
    id='fin.customer.subsidy_edit',
    system='fin',
    service='fin-service',
    name='操作目的',
    description='操作目的' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/customer/customer/subsidyEdit',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='string', state='form', ui_kind='text', description='客户ID'),  # zh_ambiguous
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', ui_kind='select', default='submit', description='操作目的', enum=['check', 'submit']),
            DeclarationEntry(name='list', path=f'$.list', type='array', state='form', ui_kind='unknown',
                children=[
                DeclarationEntry(name='subsidy_product_id', path=f'$.list.subsidy_product_id', type='integer', state='form', ui_kind='number', description='补贴id'),
                DeclarationEntry(name='subsidy_id', path=f'$.list.subsidy_id', type='integer', state='form', ui_kind='number', description='补贴id'),
                DeclarationEntry(name='subsidy_name', path=f'$.list.subsidy_name', type='string', state='form', ui_kind='text', description='补贴名称'),
                DeclarationEntry(name='product_name', path=f'$.list.product_name', type='string', state='form', ui_kind='text', description='产品名称'),
                DeclarationEntry(name='product_id', path=f'$.list.product_id', type='integer', state='form', ui_kind='number', description='产品id'),  # zh_ambiguous
                DeclarationEntry(name='deposit_type', path=f'$.list.deposit_type', type='integer', state='form', ui_kind='number', description='保证金类型'),  # zh_ambiguous
                DeclarationEntry(name='trade_term', path=f'$.list.trade_term', type='string', state='form', ui_kind='text', description='成交方式'),  # zh_ambiguous
                DeclarationEntry(name='airline', path=f'$.list.airline', type='string', state='form', ui_kind='text', description='航线'),  # zh_ambiguous
                DeclarationEntry(name='volume', path=f'$.list.volume', type='string', state='form', ui_kind='text', description='箱型'),  # zh_ambiguous
                DeclarationEntry(name='subsidy_category', path=f'$.list.subsidy_category', type='string', state='form', ui_kind='text', description='补贴分类'),  # zh_ambiguous
                DeclarationEntry(name='discount_start', path=f'$.list.discount_start', type='integer', state='form', ui_kind='number', description='有效期起'),
                DeclarationEntry(name='discount_end', path=f'$.list.discount_end', type='integer', state='form', ui_kind='number', description='有效期止'),
                DeclarationEntry(name='subsidy_proportion_arr', path=f'$.list.subsidy_proportion_arr', type='string', state='form', ui_kind='text', description='比例'),
                ]),
            DeclarationEntry(name='checkResult', path=f'$.checkResult', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='select_node_user', path=f'$.select_node_user', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='audit_note', path=f'$.audit_note', type='string', state='form', ui_kind='text', description='审批人备注'),
            DeclarationEntry(name='flow_type', path=f'$.flow_type', type='string', state='form', ui_kind='text', description='审批流配置类型'),
            DeclarationEntry(name='relation_id', path=f'$.relation_id', type='integer', state='form', ui_kind='number', default='0', description='业务ID'),
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
            DeclarationEntry(name='policy_types', path=f'$.policy_types', type='string', state='carry', ui_kind='text', description='可用政策类型'),
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
            DeclarationEntry(name='creation_method', path=f'$.creation_method', type='string', state='carry', ui_kind='text', description='创建方式'),
            DeclarationEntry(name='first_etd', path=f'$.first_etd', type='integer', state='carry', ui_kind='number', description='首单ETD时间'),
            DeclarationEntry(name='last_etd', path=f'$.last_etd', type='integer', state='carry', ui_kind='number', description='末单ETD时间'),
            DeclarationEntry(name='status', path=f'$.status', type='string', state='carry', ui_kind='text', description='状态（0停用  1草稿 2正常）\n'),
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
            DeclarationEntry(name='sale', path=f'$.sale', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='customer_service', path=f'$.customer_service', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='operate', path=f'$.operate', type='string', state='carry', ui_kind='text', description='操作'),
            DeclarationEntry(name='client_expand_id', path=f'$.client_expand_id', type='integer', state='carry', ui_kind='number', description='直客拓展ID'),
            DeclarationEntry(name='period_rule', path=f'$.period_rule', type='string', state='carry', ui_kind='text', description='废弃 125日后订单截转下月计算账期 2按ATD本月计算账期'),
            DeclarationEntry(name='king_dee_number', path=f'$.king_dee_number', type='string', state='carry', ui_kind='text', description='金蝶系统编号'),
            DeclarationEntry(name='king_dee_id', path=f'$.king_dee_id', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='sys_upttime', path=f'$.sys_upttime', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='payment_type', path=f'$.payment_type', type='integer', state='carry', ui_kind='number', description='付款类型 1确定性付款 2非确定性付款'),
            DeclarationEntry(name='deposit_settlement_date', path=f'$.deposit_settlement_date', type='integer', state='carry', ui_kind='number', description='保证金结算日'),
            DeclarationEntry(name='deposit_refund_day', path=f'$.deposit_refund_day', type='integer', state='carry', ui_kind='number', description='保证金退还周期  单位天'),
            DeclarationEntry(name='enterprise_type', path=f'$.enterprise_type', type='integer', state='carry', ui_kind='number', description='企业身份  1境内企业 2境外企业 3境外企业-港澳台企业 4境外企业-海外企业'),
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
