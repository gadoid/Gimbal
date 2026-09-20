"""fin.order_self.order_detail —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): order_self_id, order_id, service_project
溯源统计: lang=18, 无zh=11, column=9, derived=8 | fe_high=0, enum=0
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

ORDER_SELF_ORDER_DETAIL: Final[EndpointSpec] = EndpointSpec(
    id='fin.order_self.order_detail',
    system='fin',
    service='fin-service',
    name='OrderSelf.orderDetail',
    description='OrderSelf.orderDetail' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/order/orderSelf/orderDetail',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='order_self_id', path=f'$.order_self_id', type='integer', state='form', ui_kind='number', required=True, default='0', description='订单id'),  # zh_ambiguous
            DeclarationEntry(name='order_id', path=f'$.order_id', type='integer', state='form', ui_kind='number', default='0', description='订单ID'),  # zh_ambiguous
            DeclarationEntry(name='etd', path=f'$.etd', type='integer', state='form', ui_kind='number', default='0', description='预计开航日'),
            DeclarationEntry(name='atd', path=f'$.atd', type='integer', state='form', ui_kind='number', default='0', description='实际开航日'),
            DeclarationEntry(name='service_project', path=f'$.service_project', type='string', state='form', ui_kind='text', description='服务项目'),  # zh_ambiguous
            DeclarationEntry(name='service_project_amount', path=f'$.service_project_amount', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='finance_status', path=f'$.finance_status', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='main_ids_name', path=f'$.main_ids_name', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='main_sort', path=f'$.main_sort', type='string', state='form', ui_kind='text', description='主体顺序'),
            DeclarationEntry(name='policy_type_name', path=f'$.policy_type_name', type='string', state='form', ui_kind='text', description='政策类型名称'),
            DeclarationEntry(name='policy_type', path=f'$.policy_type', type='string', state='form', ui_kind='text', description='政策类型'),
            DeclarationEntry(name='business_type_name', path=f'$.business_type_name', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='business_type', path=f'$.business_type', type='string', state='form', ui_kind='text', description='业务类型'),
            DeclarationEntry(name='cargo_type_name', path=f'$.cargo_type_name', type='string', state='form', ui_kind='text', description='货物类型名称'),
            DeclarationEntry(name='cargo_type', path=f'$.cargo_type', type='string', state='form', ui_kind='text', description='货物类型'),
            DeclarationEntry(name='period_rule_name', path=f'$.period_rule_name', type='string', state='form', ui_kind='text', description='截转规则名称'),
            DeclarationEntry(name='period_rule', path=f'$.period_rule', type='integer', state='form', ui_kind='number', default='0', description='截转规则'),
            DeclarationEntry(name='is_delayed_recovery', path=f'$.is_delayed_recovery', type='integer', state='form', ui_kind='number', default='0', description='是否超期回款 1是'),
            DeclarationEntry(name='trade_term_name', path=f'$.trade_term_name', type='string', state='form', ui_kind='text', description='成交方式名称'),
            DeclarationEntry(name='trade_term', path=f'$.trade_term', type='string', state='form', ui_kind='text', description='成交方式'),
            DeclarationEntry(name='carrier_name', path=f'$.carrier_name', type='string', state='form', ui_kind='text', description='承运人名称'),
            DeclarationEntry(name='carrier', path=f'$.carrier', type='string', state='form', ui_kind='text', description='承运人'),
            DeclarationEntry(name='terms_transport_name', path=f'$.terms_transport_name', type='string', state='form', ui_kind='text', description='运输条款名称'),
            DeclarationEntry(name='terms_transport', path=f'$.terms_transport', type='string', state='form', ui_kind='text', description='运输条款'),
            DeclarationEntry(name='terms_payment_name', path=f'$.terms_payment_name', type='string', state='form', ui_kind='text', description='结汇方式名称'),
            DeclarationEntry(name='terms_payment', path=f'$.terms_payment', type='string', state='form', ui_kind='text', description='结汇方式'),
            DeclarationEntry(name='pay_type_name', path=f'$.pay_type_name', type='string', state='form', ui_kind='text', description='付款方式名称'),
            DeclarationEntry(name='pay_type', path=f'$.pay_type', type='string', state='form', ui_kind='text', description='付款方式'),
            DeclarationEntry(name='customer_put_writeoff_date', path=f'$.customer_put_writeoff_date', type='integer', state='form', ui_kind='number', default='0', description='对客应收核销时间'),
            DeclarationEntry(name='m_delivery_type_name', path=f'$.m_delivery_type_name', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='m_delivery_type', path=f'$.m_delivery_type', type='string', state='form', ui_kind='text', description='M放货方式'),
            DeclarationEntry(name='service_items', path=f'$.service_items', type='string', state='form', ui_kind='text', description='服务项目'),
            DeclarationEntry(name='fee_service_items', path=f'$.fee_service_items', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='supplier', path=f'$.supplier', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='container', path=f'$.container', type='string', state='form', ui_kind='text', description='集装箱'),
            DeclarationEntry(name='policy_id', path=f'$.policy_id', type='integer', state='form', ui_kind='number', description='服务策略'),
            DeclarationEntry(name='policy_match', path=f'$.policy_match', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='policy_match_name', path=f'$.policy_match_name', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='period_delay_type_name', path=f'$.period_delay_type_name', type='string', state='form', ui_kind='text', description='客户账期类型名称'),
            DeclarationEntry(name='period_delay_type', path=f'$.period_delay_type', type='integer', state='form', ui_kind='number', default='0', description='客户账期类型'),
            DeclarationEntry(name='settle_type_name', path=f'$.settle_type_name', type='string', state='form', ui_kind='text', description='结算方式名称'),
            DeclarationEntry(name='settle_type', path=f'$.settle_type', type='integer', state='form', ui_kind='number', default='0', description='结算方式'),
            DeclarationEntry(name='deposit_type_name', path=f'$.deposit_type_name', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='deposit_type', path=f'$.deposit_type', type='integer', state='form', ui_kind='number', default='0', description='保证金类型  1有 2无'),
            DeclarationEntry(name='payment_type_name', path=f'$.payment_type_name', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='payment_type', path=f'$.payment_type', type='integer', state='form', ui_kind='number', default='0', description='付款类型 1确定性付款 2非确定性付款'),
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
