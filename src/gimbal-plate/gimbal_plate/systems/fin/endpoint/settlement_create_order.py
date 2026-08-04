"""fin.settlement.create_order —— fin 系统结算服务创建结算单接口契约。"""""
from gimbal_plate.schema.endpoint import (
    ApiSpec,
    EndpointSpec,
    RequestSpec,
    ResponseSpec,
)
from gimbal_plate.systems.fin.models import (
    CreateOrderRequest,
    CreateOrderResponse,
)

SETTLEMENT_CREATE_ORDER = EndpointSpec(
    id="fin.settlement.create_order",
    system="fin",
    service="settlement",
    name="创建结算单",
    description="fin 结算服务创建结算订单的核心接口",
    api=ApiSpec(
        service="settlement",
        method="POST",
        path="/api/v1/fin/settlement/orders",
        auth="bearer",
        timeout_seconds=10.0,
    ),
    request=RequestSpec(body_type="json", model=CreateOrderRequest),
    responses={
        200: ResponseSpec(
            status=200,
            description="成功",
            model=CreateOrderResponse,
        ),
    },
    version="1.0.0",
)
