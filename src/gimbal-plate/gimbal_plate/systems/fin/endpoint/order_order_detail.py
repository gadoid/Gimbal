"""fin.order.order_detail —— 查询订单详情接口契约。在 scen_test_14 中出现4次。"""

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
    IOFieldBinding,
    RequestSpec,
    ResponseSpec,
    EndpointMetadata,
)


ORDER_ORDER_DETAIL: Final[EndpointSpec] = EndpointSpec(
    id="fin.order.order_detail",
    system=FIN_SYSTEM,
    service="fin-service",
    name="查询订单详情",
    description="由 Scenario_Test_14 提取: 查询订单详情",
    api=ApiSpec(service="fin-service", method="POST", path="/api/order/order/orderDetail", auth="bearer", timeout_seconds=30.0),
    request=RequestSpec(
        body_type="json",
        fields=[
        IOFieldBinding(name='order_id', path='order_id', required=True, example='', ui_kind='text', description='订单主键 ID,可取上一步 extract 的 ${var.order_id}'),
        ],
        schema_={},
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="成功",
            fields=[
        IOFieldBinding(name='order_supplier_id', path='$.data.supplier[0].order_supplier_id', required=False, ui_kind="unknown"),
        IOFieldBinding(name='order_id', path='$.data.order_id', required=False, ui_kind="unknown"),
        IOFieldBinding(name='order_no', path='$.data.order_no', required=False, ui_kind="unknown"),
        IOFieldBinding(name='order_container_id', path='$.data.container[0].order_container_id', required=False, ui_kind="unknown"),
        IOFieldBinding(name='$', path='$', required=False, ui_kind="unknown"),
            ],
            assertable_fields=['$.data.supplier[0].order_supplier_id', '$.data.order_id', '$.data.order_no', '$.data.container[0].order_container_id', '$'],
        ),
    },
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module=FIN_DEFAULT_MODULE,
        owner=FIN_DEFAULT_OWNER,
        tags=list(FIN_DEFAULT_TAGS),
    ),
)
