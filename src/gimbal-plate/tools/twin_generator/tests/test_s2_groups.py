"""T5.3 行容器分组:检测 → 富化 → S4 → 渲染全链。"""
import importlib.util
import sys
from pathlib import Path

from twin_generator.s1_routes import scan_actions
from twin_generator.s2_validator import attach_rules
from twin_generator.s2_reads import collect_reads
from twin_generator.s2_groups import detect_groups, detect_containers
from twin_generator.s3_semantics import enrich
from twin_generator.s4_state import assign
from twin_generator.s5_emit import render_endpoint
from twin_generator.schema_source import load_columns
from conftest import FIXTURES

APP2 = FIXTURES / "php" / "app2" / "Application"
REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / "src" / "gimbal-plate"))


def _pipeline():
    acts = [a for a in scan_actions(APP2)
            if a.controller == "Customer" and a.action == "checkBase"]
    attach_rules(acts, APP2)
    collect_reads(acts, APP2)
    groups = detect_groups(acts, APP2)
    catalog = load_columns(FIXTURES / "schema" / "fin_test_search.csv")
    all_fields = enrich(acts, catalog, groups=groups)
    assign(all_fields, acts, catalog, [])
    return acts, all_fields, groups


def _pipeline_order():
    acts = [a for a in scan_actions(APP2)
            if a.controller == "Order" and a.action == "orderAdd"]
    attach_rules(acts, APP2)
    collect_reads(acts, APP2)
    groups = detect_groups(acts, APP2)
    sigs = detect_containers(acts, APP2)
    catalog = load_columns(FIXTURES / "schema" / "fin_test_search.csv")
    all_fields = enrich(acts, catalog, groups=groups, container_sigs=sigs)
    assign(all_fields, acts, catalog, [])
    return acts, all_fields, sigs


def test_detect_groups():
    acts, all_fields, groups = _pipeline()
    assert "fin.customer.check_base" in groups
    containers = {c for c, _rules in groups["fin.customer.check_base"]}
    assert containers == {"customer_team"}


def test_container_field_and_children():
    acts, all_fields, _g = _pipeline()
    fields = all_fields["fin.customer.check_base"]
    top = {f.key: f for f in fields}
    # 容器键本身是 foreach 下标读取 → 已在字段集,标 array
    assert top["customer_team"].container is True
    assert top["customer_team"].type_ == "array"
    kids = {c.key: c for c in top["customer_team"].children}
    assert set(kids) == {"team_role", "team_user_id"}
    # require 直译:checkBase 非表单动作 → team_role 必填
    assert kids["team_role"].required is True
    assert kids["team_role"].zh == "团队角色"
    assert kids["team_user_id"].required is False


def test_render_children(tmp_path):
    acts, all_fields, _g = _pipeline()
    fields = all_fields["fin.customer.check_base"]
    src = render_endpoint(acts[0], fields, baseline="b")
    assert "children=[" in src and "$.customer_team.team_role" in src
    f = tmp_path / "customer_check_base.py"
    f.write_text(src, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("gen_grp", f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)             # pydantic 树校验即验收
    ep = mod.CUSTOMER_CHECK_BASE
    top = {d.name: d for d in ep.request.declarations}
    ct = top["customer_team"]
    assert ct.type == "array" and ct.children is not None
    kids = {d.name: d for d in ct.children}
    assert kids["team_role"].path == "$.customer_team.team_role"
    assert kids["team_role"].required is True
    # 容器 form(被读)⇒ 子孙 form;路径模板态(无 [i])
    assert ct.state == "form" and kids["team_role"].state == "form"


def test_detect_containers_getdataarray():
    acts, all_fields, sigs = _pipeline_order()
    # checkContainer 内 getDataArray($requestData, "container") → 容器键
    assert sigs == {"fin.order.order_add": ["container"]}
    fields = all_fields["fin.order.order_add"]
    top = {f.key: f for f in fields}
    assert top["container"].container is True
    assert top["container"].type_ == "array"
    # children 按容器表 sys_order_container 解析,zh 直取列注释
    kids = {c.key: c for c in top["container"].children}
    assert set(kids) == {"container_id", "container_type", "quantity"}
    assert kids["container_type"].zh == "箱型"
    assert kids["quantity"].type_ == "integer"
    assert kids["container_id"].zh == ""          # 无注释列留空(不造词)
    # 容器被读(getDataArray)→ form;子孙随容器
    assert top["container"].state == "form"
    assert kids["container_type"].state == "form"
    # 渲染:children 模板路径 $.container.<child>
    src = render_endpoint(acts[0], fields, baseline="b")
    assert "$.container.container_type" in src and "children=[" in src


def test_form_action_main_table_merge():
    acts, all_fields, _s = _pipeline_order()
    fields = all_fields["fin.order.order_add"]
    top = {f.key: f for f in fields}
    # 主表解析:sys_order_entrust 不在 CSV → 退 sys_order;
    # 已入集键(order_id/customer_id/num…)不重复,缺列补齐
    assert top["gross_weight"].zh == "毛重" and top["gross_weight"].zh_source == "column"
    assert top["create_time"].zh == "创建时间"
    # 列并入未读 → carry(save-all 实证:手建 order_add 13 form/227 carry 同构)
    assert top["gross_weight"].state == "carry"
    # 表列类型映射:decimal → number
    assert top["gross_weight"].type_ == "number"
    # 规则键优先不并入重复:order_id 仍只有一条
    assert len([f for f in fields if f.key == "order_id"]) == 1
