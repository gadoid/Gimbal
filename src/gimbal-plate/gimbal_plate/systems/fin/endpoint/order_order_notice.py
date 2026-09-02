"""fin.order.order_notice —— 应收核销通知接口契约。在 scen_test_14 中出现2次。"""

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


ORDER_ORDER_NOTICE: Final[EndpointSpec] = EndpointSpec(
    id="fin.order.order_notice",
    system=FIN_SYSTEM,
    service="fin-service",
    name="应收核销通知",
    description="由 Scenario_Test_14 提取: 应收核销通知",
    api=ApiSpec(service="fin-service", method="POST", path="/api/order/order/orderNotice", auth="bearer", timeout_seconds=30.0),
    request=RequestSpec(
        body_type="json",
        declarations=[
        DeclarationEntry(name='order_id', path='order_id', channel='binding', required=True, example='', ui_kind='text'),
        DeclarationEntry(name='action', path='action', channel='binding', required=True, example='check', ui_kind='text'),
        DeclarationEntry(name='finance_ids', path='finance_ids', channel='binding', required=True, example=['${var.finance_id_0}', '${var.finance_id_1}'], ui_kind='json'),
        DeclarationEntry(name='bank_ids', path='bank_ids', channel='binding', required=True, example=['${var.bank_id_0}', '${var.bank_id_1}'], ui_kind='json'),
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
