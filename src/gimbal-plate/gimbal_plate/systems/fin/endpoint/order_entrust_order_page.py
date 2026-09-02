"""fin.order_entrust.order_page —— 分页查询委托订单接口契约。在 scen_test_14 中出现1次。"""

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

_ROW_BASE = "$.data.data[0]."

# (字段名, ui_kind, 说明) —— 顺序与实测响应出现顺序一致,按业务域分段注释。
_ROW_FIELDS: Final[list[tuple[str, str, str]]] = [
    # ── 订单标识 ──
    ("order_id", "text", "订单ID"),
    ("order_no", "text", "业务订单号(如 YWDD20260901110701)"),
    ("order_sub_no", "text", "子订单号"),
    ("business_no", "text", "业务编号"),
    ("copy_order_id", "text", "复制来源订单ID(0=非复制)"),
    ("change_type", "text", "变更类型(0=无)"),
    ("business_main_id", "text", "业务主体ID"),
    ("business_main_name", "text", "业务主体名称"),
    ("main_ids", "text", "主体ID列表(逗号分隔)"),
    ("main_sort", "text", "主体简称拼接(如 易航道,易汇联)"),
    ("customer_order_sn", "text", "客户单号"),
    ("etd", "text", "预计离港时间(秒级时间戳字符串)"),
    ("atd", "text", "实际离港时间(秒级时间戳字符串)"),
    ("bl_no", "text", "提单号"),
    ("track_bl_no", "text", "跟踪提单号"),
    ("service_items", "text", "服务项"),
    ("track_atd", "text", ""),
    ("track_eta", "text", ""),
    ("track_ata", "text", ""),
]


def _build_response_face() -> tuple[list[IOFieldBinding], list[str]]:
    """信封字段 + 行字段 → (fields, assertable_fields);全部声明即可断言。"""
    fields = [
        IOFieldBinding(name="code", path="$.code", required=False, ui_kind="number",
                       description="业务状态码(200=成功)"),
        IOFieldBinding(name="msg", path="$.msg", required=False, ui_kind="text",
                       description="业务提示信息"),
        IOFieldBinding(name="request_id", path="$.request_id", required=False, ui_kind="text",
                       description="请求追踪ID"),
        IOFieldBinding(name="total", path="$.data.total", required=False, ui_kind="number",
                       description="命中总条数(分页)"),
    ]
    fields += [
        IOFieldBinding(name=name, path=f"{_ROW_BASE}{name}", required=False,
                       ui_kind=kind, description=desc)
        for name, kind, desc in _ROW_FIELDS
    ]
    return fields, [f.path for f in fields]


_RESPONSE_FIELDS, _ASSERTABLE_FIELDS = _build_response_face()



ORDER_ENTRUST_ORDER_PAGE: Final[EndpointSpec] = EndpointSpec(
    id="fin.order_entrust.order_page",
    system=FIN_SYSTEM,
    service="fin-service",
    name="委托订单的分页查询",
    description="由 Scenario_Test_14 提取: 分页查询委托订单",
    api=ApiSpec(service="fin-service", method="POST", path="/api/order/orderEntrust/orderPage", auth="bearer", timeout_seconds=30.0),
    request=RequestSpec(
        body_type="json",
        fields=[
        IOFieldBinding(name='bl_no', path='bl_no', required=True, example='', ui_kind='text'),
        IOFieldBinding(name='order_no', path='order_no', required=True, example='', ui_kind='text'),
        IOFieldBinding(name='page_no', path='page_no', required=True, example=1, ui_kind='number'),
        IOFieldBinding(name='page_size', path='page_size', required=True, example=20, ui_kind='number'),
        IOFieldBinding(name='sort_field', path='sort_field', required=True, example='update_time', ui_kind='text'),
        IOFieldBinding(name='sort_order', path='sort_order', required=True, example='desc', ui_kind='text'),
        IOFieldBinding(name='params', path='params', required=True, example={}, ui_kind='json'),
        ],
        schema_={},
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="成功",
            fields=_RESPONSE_FIELDS,
            assertable_fields=_ASSERTABLE_FIELDS,
        ),
    },
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module=FIN_DEFAULT_MODULE,
        owner=FIN_DEFAULT_OWNER,
        tags=list(FIN_DEFAULT_TAGS),
    ),
)
