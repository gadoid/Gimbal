"""fin.order.order_page —— 分页查询委托订单接口契约。在 scen_test_14 中出现3次。

响应字段面依据 2026-09-01 实测响应(单条订单 YWDD20260901110701)逐字段核对重建:
行字段挂 $.data.data[0].<name>(首页首行,断言/提取按行取值,分页查询通常配
page_size=1 + 精确条件定位);类型按实测 JSON 类型映射(str→text / 数值→number /
bool→boolean / 数组→json);说明仅标注可确信语义(枚举值对照同响应的 *_name
字段),不确定的留空 —— 宁缺毋滥,避免误导断言编写。
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
    EndpointSpec,
    DeclarationEntry,
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


def _build_response_decls() -> list[DeclarationEntry]:
    """信封字段 + 行字段 → view_only 声明;全部声明即可断言(B3 assertable)。"""
    entries = [
        DeclarationEntry(name="code", path="$.code", type='number', 
                         required=False, ui_kind="number",
                         description="业务状态码(200=成功)", assertable=True),
        DeclarationEntry(name="msg", path="$.msg", type='string', 
                         required=False, ui_kind="text",
                         description="业务提示信息", assertable=True),
        DeclarationEntry(name="request_id", path="$.request_id", type='string', 
                         required=False, ui_kind="text",
                         description="请求追踪ID", assertable=True),
        DeclarationEntry(name="total", path="$.data.total", type='number', 
                         required=False, ui_kind="number",
                         description="命中总条数(分页)", assertable=True),
    ]
    entries += [
        DeclarationEntry(name=name, path=f"{_ROW_BASE}{name}", type='string', 
                         required=False, ui_kind=kind, description=desc,
                         assertable=True)
        for name, kind, desc in _ROW_FIELDS
    ]
    return entries


_RESPONSE_DECLS = _build_response_decls()

ORDER_ORDER_PAGE: Final[EndpointSpec] = EndpointSpec(
    id="fin.order.order_page",
    system=FIN_SYSTEM,
    service="fin-service",
    name="分页查询委托订单",
    description="由 Scenario_test_14 提取: 分页查询委托订单",
    api=ApiSpec(service="fin-service", method="POST", path="/api/order/order/orderPage", auth="bearer", timeout_seconds=30.0),
    request=RequestSpec(
        body_type="json",
        declarations=[
        DeclarationEntry(name='bl_no', path='bl_no', type='string', required=True, example='', ui_kind='text'),
        DeclarationEntry(name='order_no', path='order_no', type='string', required=True, example='', ui_kind='text'),
        DeclarationEntry(name='page_no', path='page_no', type='integer', required=True, example=1, ui_kind='number'),
        DeclarationEntry(name='page_size', path='page_size', type='integer', required=True, example=20, ui_kind='number'),
        DeclarationEntry(name='sort_field', path='sort_field', type='string', required=True, example='update_time', ui_kind='text'),
        DeclarationEntry(name='sort_order', path='sort_order', type='string', required=True, example='desc', ui_kind='text'),
        DeclarationEntry(name='params', path='params', type='object', required=True, example={}, ui_kind='json'),
        ],
        
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="成功",
            declarations=_RESPONSE_DECLS,
        ),
    },
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module=FIN_DEFAULT_MODULE,
        owner=FIN_DEFAULT_OWNER,
        tags=list(FIN_DEFAULT_TAGS),
    ),
)
