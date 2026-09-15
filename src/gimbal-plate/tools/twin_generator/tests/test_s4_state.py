from twin_generator.ir import ActionIR, FieldIR
from twin_generator.schema_source import load_columns
from twin_generator.s4_state import assign
from conftest import FIXTURES

VIEW_ROWS = [
    {"name": "customer_list", "columns": ["customer_id", "customer_name", "bl_no"]},
    {"name": "customer_part", "columns": ["customer_id", "handover_form.client_expand_name"]},
]


def _fields():
    return [
        FieldIR(key="action", read=True, required=False),               # 读 → form
        FieldIR(key="customer_id", read=False, required=True),          # 必填未读 → carry+vs
        FieldIR(key="bl_no", read=False, must_include=True),            # exist → carry+vs
        FieldIR(key="carrier", read=False, required=False),             # 纯携带
        FieldIR(key="etd", read=False, required=False),
        FieldIR(key="settle_type", read=False, required=True,
                enum_values=["1", "2"]),                                # enum×vs 互斥
    ]


def test_assign():
    acts = [ActionIR(module="Order", controller="OrderEntrust", action="orderAdd")]
    fields = {"fin.order_entrust.order_add": _fields()}
    cat = load_columns(FIXTURES / "schema" / "fin_test_search.csv")
    report = assign(fields, acts, cat, VIEW_ROWS)
    by = {f.key: f for f in fields["fin.order_entrust.order_add"]}
    assert by["action"].state == "form"
    # customer_id 两视图同名 → 消歧,不自动挂
    assert by["customer_id"].value_source is None
    assert "needs_capture:value_source" in by["customer_id"].flags
    assert ("fin.order_entrust.order_add", "customer_id",
            {"customer_list", "customer_part"}) in report.ambiguous
    # bl_no 恰一视图 → 挂上
    assert by["bl_no"].value_source == ("customer_list", "bl_no")
    # carrier/etd 纯 carry(etd 的 NOT NULL 有默认 '0',不触发)
    assert by["carrier"].state == "carry" and by["carrier"].flags == []
    assert by["etd"].state == "carry" and by["etd"].flags == []
    # enum 与 vs 互斥:必填但有 enum → 不挂 vs,标 needs_capture
    assert by["settle_type"].value_source is None
    assert "needs_capture:enum_required" in by["settle_type"].flags
