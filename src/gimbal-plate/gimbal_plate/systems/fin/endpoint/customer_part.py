"""fin.customer.part — 客户详情(组合期取数源,级联链 ②)。

POST /api/customer/customer/customerPart(body customer_id):单对象详情
{bill, contact, customer_service, finance, handover_form, …}。
customer_part 视图:单对象型($.data 整对象即一行,§13.4),点路径列
handover_form.client_expand_id 等扇出;customer_id 走点击期参数面(§13.2)。
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

CUSTOMER_PART: Final[EndpointSpec] = EndpointSpec(
    id="fin.customer.part",
    system=FIN_SYSTEM,
    service="fin-service",
    name="客户详情(customerPart)",
    description="客户单对象详情;组合期取数源 customer_part 视图挂此(级联链 ②,§13.1/§13.4)",
    api=ApiSpec(service="fin-service", method="POST",
                path="/api/customer/customer/customerPart",
                auth="bearer", timeout_seconds=30.0),
    request=RequestSpec(body_type="json", declarations=[
        DeclarationEntry(name="customer_id", path="$.customer_id", type="string",
                         required=True, ui_kind="text",
                         description="客户ID(点击期参数面供给,§13.2)"),
    ]),
    responses={200: ResponseSpec(status=200, description="成功",
                                 declarations=_RESPONSE_DECLS)},
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(module=FIN_DEFAULT_MODULE, owner=FIN_DEFAULT_OWNER,
                              tags=list(FIN_DEFAULT_TAGS), query_safe=True),
    query_views=[QueryView(
        name="customer_part",
        query_params=["customer_id"],
        items="$.data",                       # 单对象型:整对象即一行(§13.4)
        label="customer_service.user_name",   # 单对象行标识列(点路径,2026-09-09 抓包实证)
    )],
)
