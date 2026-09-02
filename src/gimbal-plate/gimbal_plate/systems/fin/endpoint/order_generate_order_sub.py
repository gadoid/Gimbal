"""fin.order.generate_order_sub —— 生成应收应付子订单接口契约。在 scen_test_14 中出现1次。"""

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


ORDER_GENERATE_ORDER_SUB: Final[EndpointSpec] = EndpointSpec(
    id="fin.order.generate_order_sub",
    system=FIN_SYSTEM,
    service="fin-service",
    name="生成应收应付子订单",
    description="由 Scenario_Test_14 提取: 生成应收应付子订单",
    api=ApiSpec(service="fin-service", method="POST", path="/api/order/order/generateOrderSub", auth="bearer", timeout_seconds=30.0),
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
        ),
    },
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module=FIN_DEFAULT_MODULE,
        owner=FIN_DEFAULT_OWNER,
        tags=list(FIN_DEFAULT_TAGS),
    ),
)
