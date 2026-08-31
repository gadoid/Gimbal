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
    IOFieldBinding,
    RequestSpec,
    ResponseSpec,
    EndpointMetadata,
)
from gimbal_plate.schema.endpoint.io_spec import CarryEntry
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
    request=RequestSpec(
        body_type="json",
        schema_=CreateOrderRequest.model_json_schema(),
        fields=[
            IOFieldBinding(name="order_id", path="$.order_id", required=True,
                           description="业务订单号"),
            IOFieldBinding(name="amount", path="$.amount", required=True,
                           description="结算金额,单位分", ui_kind="number"),
            IOFieldBinding(name="currency", path="$.currency", required=False,
                           default="CNY", description="币种"),
        ],
        # 传递面(spec §2):备注是典型 carry 字段 —— 值随 platform 配置走
        carry={"$.remark": CarryEntry(description="备注(随请求传递,不进表单)")},
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="成功",
            schema_=CreateOrderResponse.model_json_schema(),
        ),
    },
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module=FIN_DEFAULT_MODULE,
        owner=FIN_DEFAULT_OWNER,
        tags=list(FIN_DEFAULT_TAGS),
    ),
)
