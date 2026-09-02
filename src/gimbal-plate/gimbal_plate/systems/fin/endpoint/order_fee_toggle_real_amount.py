"""fin.order_fee.toggle_real_amount —— 切换订单实收实付金额模式接口契约。在 scen_test_14 中出现4次。"""

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
)


ORDER_FEE_TOGGLE_REAL_AMOUNT: Final[EndpointSpec] = EndpointSpec(
    id="fin.order_fee.toggle_real_amount",
    system=FIN_SYSTEM,
    service="fin-service",
    name="切换订单实收实付金额模式",
    description="由 Scenario_Test_14 提取: 切换订单实收实付金额模式",
    api=ApiSpec(service="fin-service", method="POST", path="/api/order/orderFee/toggleRealAmount", auth="bearer", timeout_seconds=30.0),
    request=RequestSpec(
        body_type="json",
        declarations=[
        DeclarationEntry(name='order_id', path='order_id', channel='binding', required=True, example='', ui_kind='text'),
        ],
        schema_={},
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="成功",
            declarations=[
        DeclarationEntry(name='order_id', path='$.data.amount_summary.order_id', channel='view_only', required=False, ui_kind="unknown", assertable=True),
        DeclarationEntry(name='order_fee_real_id', path='$.data.to_customer[0].put_amount.standard_list[0].order_fee_real_id', channel='view_only', required=False, ui_kind="unknown", assertable=True),
        DeclarationEntry(name='order_sub_no', path='$.data.to_customer[0].order_sub_no', channel='view_only', required=False, ui_kind="unknown", assertable=True),
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
