"""fin.settlement.create_order —— fin 系统结算服务创建结算单接口契约。"""""

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
    RequestSpec,
    ResponseSpec,
    EndpointMetadata,
)
from gimbal_plate.systems.fin.models import (
    CreateOrderRequest,
    CreateOrderResponse,
)

SETTLEMENT_CREATE_ORDER: Final[EndpointSpec] = EndpointSpec(
    id="fin.settlement.create_order",
    system=FIN_SYSTEM,
    service="fin-service",
    name="创建结算单",
    description="fin 结算服务创建结算订单的核心接口",
    api=ApiSpec(
        service="fin-service",
        method="POST",
        path="/api/v1/fin/settlement/orders",
        auth="bearer",
        timeout_seconds=10.0,
    ),
    request=RequestSpec.declare(
        # 2026-09-05 目录化:bindings/carry 通道参数退役,states 盖戳共识默认
        # (order_id/amount/currency = form 默认;remark = carry 值表传递;
        #  amount 的 number 控件由 type 基线推断承接)
        CreateOrderRequest,
        states={"remark": "carry"},
    ),
    responses={
        200: ResponseSpec.declare(CreateOrderResponse, status=200, description='成功'),
    },
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module=FIN_DEFAULT_MODULE,
        owner=FIN_DEFAULT_OWNER,
        tags=list(FIN_DEFAULT_TAGS),
    ),
)
