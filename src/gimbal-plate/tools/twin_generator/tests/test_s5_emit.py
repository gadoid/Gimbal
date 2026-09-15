import importlib.util
import sys
from pathlib import Path

from twin_generator.ir import ActionIR, FieldIR
from twin_generator.s5_emit import render_endpoint, emit_all

# generated 文件 import gimbal_plate —— conftest 已插路径?本测试自己插:
REPO = Path(__file__).resolve().parents[5]   # tools/twin_generator/tests → repo
sys.path.insert(0, str(REPO / "src" / "gimbal-plate"))


def _act():
    return ActionIR(module="Order", controller="OrderEntrust", action="orderAdd")


def _fields():
    return [
        FieldIR(key="action", read=True, zh="动作", default="submit"),
        FieldIR(key="customer_id", required=True, zh="客户ID",
                value_source=("customer_list", "customer_id")),
        FieldIR(key="carrier", zh="船公司/承运人",
                flags=["needs_capture:value_source"]),
    ]


def test_render_and_import(tmp_path):
    src_text = render_endpoint(_act(), _fields(), baseline="fin-test@2026-09-15")
    assert "ORDER_ENTRUST_ORDER_ADD" in src_text
    assert "needs_capture:value_source" in src_text
    f = tmp_path / "order_entrust_order_add.py"
    f.write_text(src_text, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("gen_mod", f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)            # pydantic 构造期校验即验收
    ep = mod.ORDER_ENTRUST_ORDER_ADD
    assert ep.id == "fin.order_entrust.order_add"
    assert ep.api.path == "/api/order/orderEntrust/orderAdd"
    by_name = {d.name: d for d in ep.request.declarations}
    assert by_name["action"].state == "form"
    assert by_name["customer_id"].state == "carry"
    assert by_name["customer_id"].value_source.view == "customer_list"
    assert by_name["customer_id"].required is True


def test_emit_all_collision_skip(tmp_path):
    acts = [_act()]
    fields = {"fin.order_entrust.order_add": _fields()}
    summary = emit_all(acts, fields, tmp_path, existing_ids={"fin.order_entrust.order_add"},
                       baseline="b")
    assert summary["skipped"] == 1 and summary["emitted"] == 0
    assert not list(tmp_path.glob("*.py"))
