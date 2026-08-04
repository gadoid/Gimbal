"""fin.order_fee.toggle_real_amount —— 切换订单实收实付金额模式接口契约。在 scen_test_14 中出现4次。"""
from gimbal_plate.schema.endpoint import (
    ApiSpec,
    EndpointSpec,
    IOFieldBinding,
    RequestSpec,
    ResponseSpec,
)


ORDER_FEE_TOGGLE_REAL_AMOUNT = EndpointSpec(
    id="fin.order_fee.toggle_real_amount",
    system="fin",
    service="order_fee",
    name="切换订单实收实付金额模式",
    description="由 Scenario_Test_14 提取: 切换订单实收实付金额模式",
    api=ApiSpec(service="order_fee", method="POST", path="/api/order/orderFee/toggleRealAmount", auth="bearer", timeout_seconds=30.0),
    request=RequestSpec(
        body_type="json",
        fields=[
        IOFieldBinding(name='order_id', path='order_id', required=True, example='', ui_kind='text'),
        ],
        schema_={},
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="成功",
            fields=[
        IOFieldBinding(name='order_id', path='$.data.amount_summary.order_id', required=False, ui_kind="unknown"),
        IOFieldBinding(name='order_fee_real_id', path='$.data.to_customer[0].put_amount.standard_list[0].order_fee_real_id', required=False, ui_kind="unknown"),
        IOFieldBinding(name='order_sub_no', path='$.data.to_customer[0].order_sub_no', required=False, ui_kind="unknown"),
            ],
            assertable_fields=['$.data.amount_summary.order_id', '$.data.to_customer[0].put_amount.standard_list[0].order_fee_real_id', '$.data.to_customer[0].order_sub_no'],
        ),
    },
    version="1.0.0",
)
