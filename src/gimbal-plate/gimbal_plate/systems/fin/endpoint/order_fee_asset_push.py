"""fin.order_fee.asset_push —— 费用资产推送接口契约。在 scen_test_14 中出现3次。"""

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


ORDER_FEE_ASSET_PUSH: Final[EndpointSpec] = EndpointSpec(
    id="fin.order_fee.asset_push",
    system=FIN_SYSTEM,
    service="order_fee",
    name="费用资产推送",
    description="由 Scenario_Test_14 提取: 费用资产推送",
    api=ApiSpec(service="order_fee", method="POST", path="/api/order/orderFee/assetPush", auth="bearer", timeout_seconds=30.0),
    request=RequestSpec(
        body_type="json",
        fields=[
        IOFieldBinding(name='action', path='action', required=True, example='check', ui_kind='text'),
        IOFieldBinding(name='order_id', path='order_id', required=True, example='', ui_kind='text'),
        IOFieldBinding(name='audit_msg', path='audit_msg', required=True, example={'title': '资产推送申请', 'code': '', 'msgs': ['资产推送申请']}, ui_kind='json'),
        IOFieldBinding(name='select_node_user', path='select_node_user', required=True, example=[{'node_sort': '0', 'user_id': '828'}], ui_kind='json'),
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
