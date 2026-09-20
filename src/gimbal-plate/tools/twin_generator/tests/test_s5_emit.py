import importlib.util
import sys
from pathlib import Path

from twin_generator.ir import ActionIR, FieldIR
from twin_generator.s4_state import assign
from twin_generator.s5_emit import render_endpoint, emit_all
from twin_generator.schema_source import ColumnCatalog, ColumnInfo

# generated 文件 import gimbal_plate —— conftest 已插路径?本测试自己插:
REPO = Path(__file__).resolve().parents[5]   # tools/twin_generator/tests → repo
sys.path.insert(0, str(REPO / "src" / "gimbal-plate"))


def _act():
    return ActionIR(module="Order", controller="OrderEntrust", action="orderAdd")


def _catalog():
    return ColumnCatalog([ColumnInfo(
        table="sys_x", column="zzz", col_type="varchar(32)",
        nullable=True, default=None, comment="")])


def _fields():
    """管线序:构造 → S4 赋值(S5 不再对裸 FieldIR 兜底,state 真源在 S4)。"""
    fs = [
        FieldIR(key="action", read=True, zh="动作", default="submit",
                enum_values=["check", "submit"]),
        FieldIR(key="customer_id", required=True, zh="客户ID"),
        FieldIR(key="carrier", zh="船公司/承运人", col_type="text"),
        FieldIR(key="bl_no", zh="提单号", fe_confidence="high",
                fe_type="select", example="BL20260901"),
    ]
    assign({_act().id: fs}, [_act()], _catalog(), [])
    fs[1].value_source = ("customer_list", "customer_id")
    fs[2].flags.append("needs_capture:value_source")
    return fs


def test_render_and_import(tmp_path):
    src_text = render_endpoint(_act(), _fields(), baseline="fin-test@2026-09-15")
    assert "ORDER_ENTRUST_ORDER_ADD" in src_text
    assert "needs_capture:value_source" in src_text
    assert "溯源统计:" in src_text            # T5.5 头部溯源行
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
    # T5.1 ui_kind:enum→select;fe high 采信;text 列→textarea
    assert by_name["action"].ui_kind == "select"
    assert by_name["bl_no"].ui_kind == "select"
    assert by_name["carrier"].ui_kind == "textarea"
    # T5.2 example 仅 high 置信;T5.5 value_source → lookup
    assert by_name["bl_no"].example == "BL20260901"
    assert by_name["customer_id"].source_kind == "lookup"
    # T5.4 信封:四键全 assertable,data 行形状不碰
    resp = ep.responses[200]
    env = {d.name: d for d in resp.declarations}
    assert set(env) == {"code", "msg", "data", "request_id"}
    assert all(d.assertable for d in env.values())
    assert env["data"].type == "object" and env["data"].ui_kind == "json"
    assert env["data"].children is None


def test_envelope_api_module(tmp_path):
    """Api 回调模块:retCode/retMsg/data 三键信封(无 code/request_id)。"""
    act = ActionIR(module="Api", controller="Finance", action="payNotify")
    fs = [FieldIR(key="order_no", zh="订单号")]
    src_text = render_endpoint(act, fs, baseline="b")
    f = tmp_path / "api_finance_pay_notify.py"
    f.write_text(src_text, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("gen_mod2", f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    env = {d.name: d for d in mod.FINANCE_PAY_NOTIFY.responses[200].declarations}
    assert set(env) == {"retCode", "retMsg", "data"}
    assert all(d.assertable for d in env.values())


def test_emit_all_collision_skip(tmp_path):
    acts = [_act()]
    fields = {"fin.order_entrust.order_add": _fields()}
    summary = emit_all(acts, fields, tmp_path, existing_ids={"fin.order_entrust.order_add"},
                       baseline="b")
    assert summary["skipped"] == 1 and summary["emitted"] == 0
    assert not list(tmp_path.glob("*.py"))
