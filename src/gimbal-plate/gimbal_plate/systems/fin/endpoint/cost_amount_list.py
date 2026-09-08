"""fin.cost.amount_list — 费用字典列表(组合期取数源)。

GET /api/home/cost/amountCostList:业务持续增补的费用字典(130+),
cost_list 视图供字段绑定组合期取数(spec 2026-09-07 §0.1/§3.1)。
字典接口成为目录公民 = 获得声明、golden 覆盖、自身可测。
行集结构待首次连测核对(cost_name/cost_id 键位),响应声明只登记信封。
"""
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
    DeclarationEntry,
    EndpointMetadata,
    EndpointSpec,
    RequestSpec,
    ResponseSpec,
)
from gimbal_plate.schema.endpoint import QueryView

_RESPONSE_DECLS: Final[list[DeclarationEntry]] = [
    DeclarationEntry(name="code", path="$.code", type="number", required=False,
                     ui_kind="number", description="业务状态码(200=成功)", assertable=True),
    DeclarationEntry(name="msg", path="$.msg", type="string", required=False,
                     ui_kind="text", description="业务提示信息", assertable=True),
]

COST_AMOUNT_LIST: Final[EndpointSpec] = EndpointSpec(
    id="fin.cost.amount_list",
    system=FIN_SYSTEM,
    service="fin-service",
    name="费用字典列表(amountCostList)",
    description="费用名称/费用ID 字典;组合期取数源 cost_list 视图挂此",
    api=ApiSpec(service="fin-service", method="GET",
                path="/api/home/cost/amountCostList",
                auth="bearer", timeout_seconds=30.0),
    request=RequestSpec(body_type="none"),
    responses={200: ResponseSpec(status=200, description="成功",
                                 declarations=_RESPONSE_DECLS)},
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(module=FIN_DEFAULT_MODULE, owner=FIN_DEFAULT_OWNER,
                              tags=list(FIN_DEFAULT_TAGS)),
    query_views=[QueryView(name="cost_list", items="$.data[*]", label="cost_name")],
)
