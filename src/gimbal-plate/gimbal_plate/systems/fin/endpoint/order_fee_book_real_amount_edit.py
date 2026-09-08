"""fin.order_fee.book_real_amount_edit —— 订舱实收实付金额配置接口契约。在 scen_test_14 中出现2次。"""

from typing import Final

from gimbal_plate.systems.fin.system_info import (
    FIN_DEFAULT_AUTHOR,
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

# ----------------------------------------------------------------------
# 来源: Scenario_Test_14 提取(check 态)+ 2026-09-07 实抓 body
# (submit 态,order_id 355255812731438080)双证结构化。
# 人工已确认: 类型/必填/绑定面/响应语义/能力声明
# ----------------------------------------------------------------------
ORDER_FEE_BOOK_REAL_AMOUNT_EDIT: Final[EndpointSpec] = EndpointSpec(
    id="fin.order_fee.book_real_amount_edit",
    system=FIN_SYSTEM,
    service="fin-service",
    name="订舱实收实付金额配置",
    description="由 Scenario_Test_14 提取: 订舱实收实付金额配置",
    api=ApiSpec(service="fin-service", method="POST", path="/api/order/orderFee/bookRealAmountEdit", auth="bearer", timeout_seconds=30.0),
    request=RequestSpec(
        body_type="json",
        declarations=[
            DeclarationEntry(name='action', path='$.action', state='form', type='string', example='check', ui_kind='text', enum=['check', 'submit']),
            DeclarationEntry(name='order_id', path='$.order_id', state='form', type='string', example='355255812731438080', ui_kind='text'),
            DeclarationEntry(name='discount_ratio', path='$.discount_ratio', state='form', type='string', example='', ui_kind='text'),
            DeclarationEntry(name='service_project', path='$.service_project', state='form', type='string', example='booking_space', ui_kind='text'),
            DeclarationEntry(name='import_status', path='$.import_status', state='form', type='integer', example=0, ui_kind='number'),
            # 2026-09-07 结构化:example 单例承载弃,to_customer/to_supplier
            # 深传容器模板 children(put_amount/pay_amount.standard_list 行
            # 形状 22 键;Test_14 旧例 to_supplier 行曾多 related_unique_id,
            # 按本日实抓双行 22 键对齐,差异留痕)。全树 form —— 本端点
            # 业务面即费用行编辑;深层不带 default/example → platform
            # 导出 D7 深层无值不落 None 骨架,body 零漂移
            DeclarationEntry(name='to_customer', path='$.to_customer', state='form', type='object',
                children=[
                    DeclarationEntry(name='put_amount', path='$.to_customer.put_amount', state='form', type='object',
                        children=[
                            DeclarationEntry(name='standard_list', path='$.to_customer.put_amount.standard_list', state='form', type='array',
                                children=[
                                    DeclarationEntry(name='order_fee_real_id', path='$.to_customer.put_amount.standard_list.order_fee_real_id', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='fee_type', path='$.to_customer.put_amount.standard_list.fee_type', state='form', type='integer', ui_kind='number'),
                                    DeclarationEntry(name='policy_sub_id', path='$.to_customer.put_amount.standard_list.policy_sub_id', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='service_project', path='$.to_customer.put_amount.standard_list.service_project', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='cost_id', path='$.to_customer.put_amount.standard_list.cost_id', state='form', type='string', ui_kind='text',
                                        value_source=ValueSource(view='cost_list', column='cost_id', group='cost_list#to_customer')),
                                    DeclarationEntry(name='settle_object_id', path='$.to_customer.put_amount.standard_list.settle_object_id', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='subsidy_category', path='$.to_customer.put_amount.standard_list.subsidy_category', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='currency', path='$.to_customer.put_amount.standard_list.currency', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='unit_price', path='$.to_customer.put_amount.standard_list.unit_price', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='unit', path='$.to_customer.put_amount.standard_list.unit', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='specs', path='$.to_customer.put_amount.standard_list.specs', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='num', path='$.to_customer.put_amount.standard_list.num', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='remark', path='$.to_customer.put_amount.standard_list.remark', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='discount_ratio', path='$.to_customer.put_amount.standard_list.discount_ratio', state='form', type='integer', ui_kind='number'),
                                    DeclarationEntry(name='discount_amount', path='$.to_customer.put_amount.standard_list.discount_amount', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='discount_status', path='$.to_customer.put_amount.standard_list.discount_status', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='policy_sub_status_name', path='$.to_customer.put_amount.standard_list.policy_sub_status_name', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='pay_sync_status', path='$.to_customer.put_amount.standard_list.pay_sync_status', state='form', type='integer', ui_kind='number'),
                                    DeclarationEntry(name='unique_id', path='$.to_customer.put_amount.standard_list.unique_id', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='init_main_name', path='$.to_customer.put_amount.standard_list.init_main_name', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='main_name', path='$.to_customer.put_amount.standard_list.main_name', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='rowIndex', path='$.to_customer.put_amount.standard_list.rowIndex', state='form', type='integer', ui_kind='number'),
                                ]),
                        ]),
                ]),
            DeclarationEntry(name='to_supplier', path='$.to_supplier', state='form', type='object',
                children=[
                    DeclarationEntry(name='pay_amount', path='$.to_supplier.pay_amount', state='form', type='object',
                        children=[
                            DeclarationEntry(name='standard_list', path='$.to_supplier.pay_amount.standard_list', state='form', type='array',
                                children=[
                                    DeclarationEntry(name='order_fee_real_id', path='$.to_supplier.pay_amount.standard_list.order_fee_real_id', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='fee_type', path='$.to_supplier.pay_amount.standard_list.fee_type', state='form', type='integer', ui_kind='number'),
                                    DeclarationEntry(name='policy_sub_id', path='$.to_supplier.pay_amount.standard_list.policy_sub_id', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='service_project', path='$.to_supplier.pay_amount.standard_list.service_project', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='cost_id', path='$.to_supplier.pay_amount.standard_list.cost_id', state='form', type='string', ui_kind='text',
                                        value_source=ValueSource(view='cost_list', column='cost_id', group='cost_list#to_supplier')),
                                    DeclarationEntry(name='settle_object_id', path='$.to_supplier.pay_amount.standard_list.settle_object_id', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='subsidy_category', path='$.to_supplier.pay_amount.standard_list.subsidy_category', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='currency', path='$.to_supplier.pay_amount.standard_list.currency', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='unit_price', path='$.to_supplier.pay_amount.standard_list.unit_price', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='unit', path='$.to_supplier.pay_amount.standard_list.unit', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='specs', path='$.to_supplier.pay_amount.standard_list.specs', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='num', path='$.to_supplier.pay_amount.standard_list.num', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='remark', path='$.to_supplier.pay_amount.standard_list.remark', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='discount_ratio', path='$.to_supplier.pay_amount.standard_list.discount_ratio', state='form', type='integer', ui_kind='number'),
                                    DeclarationEntry(name='discount_amount', path='$.to_supplier.pay_amount.standard_list.discount_amount', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='discount_status', path='$.to_supplier.pay_amount.standard_list.discount_status', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='policy_sub_status_name', path='$.to_supplier.pay_amount.standard_list.policy_sub_status_name', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='pay_sync_status', path='$.to_supplier.pay_amount.standard_list.pay_sync_status', state='form', type='integer', ui_kind='number'),
                                    DeclarationEntry(name='unique_id', path='$.to_supplier.pay_amount.standard_list.unique_id', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='init_main_name', path='$.to_supplier.pay_amount.standard_list.init_main_name', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='main_name', path='$.to_supplier.pay_amount.standard_list.main_name', state='form', type='string', ui_kind='text'),
                                    DeclarationEntry(name='rowIndex', path='$.to_supplier.pay_amount.standard_list.rowIndex', state='form', type='integer', ui_kind='number'),
                                ]),
                        ]),
                ]),
        ],

    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="成功",
        ),
    },
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module=FIN_DEFAULT_MODULE,
        owner=FIN_DEFAULT_OWNER,
        tags=list(FIN_DEFAULT_TAGS),
    ),
)
