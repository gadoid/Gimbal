"""fin.customer.list — 客户列表(组合期取数源,级联链 ①)。

POST /api/customer/customer/customerList:客户公司列表,无必填参。
customer_list 视图:选公司 → customer_id/customer_name 一查多填(§13.1 ①)。
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

CUSTOMER_LIST: Final[EndpointSpec] = EndpointSpec(
    id="fin.customer.list",
    system=FIN_SYSTEM,
    service="fin-service",
    name="客户列表(customerList)",
    description="客户公司列表;组合期取数源 customer_list 视图挂此(级联链 ①,§13.1)",
    api=ApiSpec(service="fin-service", method="POST",
                path="/api/customer/customer/customerList",
                auth="bearer", timeout_seconds=30.0),
    request=RequestSpec(body_type="json"),
    responses={200: ResponseSpec(status=200, description="成功",
                                 declarations=_RESPONSE_DECLS)},
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(module=FIN_DEFAULT_MODULE, owner=FIN_DEFAULT_OWNER,
                              tags=list(FIN_DEFAULT_TAGS), query_safe=True),
    query_views=[QueryView(name="customer_list", items="$.data[*]",
                           label="customer_name")],
)
