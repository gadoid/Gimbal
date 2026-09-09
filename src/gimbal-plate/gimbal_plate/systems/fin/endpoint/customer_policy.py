"""fin.customer.policy — 客户策略列表(组合期取数源,级联链 ③)。

POST /api/Customer/Policy/getCustomerPolicy(body customer_id + status):
策略列表($.data[*]:policy_id/policy_name/customer_policy_id)。
customer_policy 视图:status="2" 静态预设(params)+ customer_id 点击期
(query_params)—— 静态/动态分离的实证样本(§13.1)。
行集结构待首连测核对,响应声明只登记信封。
"""
from typing import Final

from gimbal_plate.systems.fin.system_info import (
    FIN_DEFAULT_MODULE, FIN_DEFAULT_OWNER, FIN_DEFAULT_TAGS,
    FIN_DEFAULT_VERSION, FIN_SYSTEM,
)
from gimbal_plate.schema.endpoint import (
    ApiSpec, DeclarationEntry, EndpointMetadata, EndpointSpec,
    RequestSpec, ResponseSpec,
)
from gimbal_plate.schema.endpoint import QueryView

_RESPONSE_DECLS: Final[list[DeclarationEntry]] = [
    DeclarationEntry(name="code", path="$.code", type="number", required=False,
                     ui_kind="number", description="业务状态码(200=成功)", assertable=True),
    DeclarationEntry(name="msg", path="$.msg", type="string", required=False,
                     ui_kind="text", description="业务提示信息", assertable=True),
]

CUSTOMER_POLICY: Final[EndpointSpec] = EndpointSpec(
    id="fin.customer.policy",
    system=FIN_SYSTEM,
    service="fin-service",
    name="客户策略列表(getCustomerPolicy)",
    description="客户策略列表;组合期取数源 customer_policy 视图挂此(级联链 ③,§13.1)",
    api=ApiSpec(service="fin-service", method="POST",
                path="/api/Customer/Policy/getCustomerPolicy",
                auth="bearer", timeout_seconds=30.0),
    request=RequestSpec(body_type="json", declarations=[
        DeclarationEntry(name="customer_id", path="$.customer_id", type="string",
                         required=True, ui_kind="text",
                         description="客户ID(点击期参数面供给,§13.2)"),
        DeclarationEntry(name="status", path="$.status", type="string",
                         required=True, ui_kind="text",
                         description="策略状态(视图静态预设 status=2,§13.1)"),
    ]),
    responses={200: ResponseSpec(status=200, description="成功",
                                 declarations=_RESPONSE_DECLS)},
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(module=FIN_DEFAULT_MODULE, owner=FIN_DEFAULT_OWNER,
                              tags=list(FIN_DEFAULT_TAGS), query_safe=True),
    query_views=[QueryView(
        name="customer_policy",
        params={"status": "2"},
        query_params=["customer_id"],
        items="$.data[*]",
        label="policy_name",
    )],
)
