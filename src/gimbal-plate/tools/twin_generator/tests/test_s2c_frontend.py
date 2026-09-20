"""S2c 前端面提取回归钉:mini chunk 实录三类字面量。

覆盖:URL 注册表(url+method)、payload 字面量、表单配置组 {type,name,key}
+ {label,width,name}、表单初始态模型(Vue data() KV 连缀)、组级归属
(键倒排 + REL_SCORE 近并列)、巨型 bundle 分段、method 回写。
"""
import json
from pathlib import Path

from twin_generator.ir import ActionIR, RuleEntry
from twin_generator.s2c_frontend import (
    _fe_path, _scan_chunk, scan_frontend, fe_to_json,
    FE_ASSIGN_MIN, _REL_SCORE,
)

# 实录风格压缩 mini chunk:url 注册 + 查询表单 + add 表单配置 + data() 模型
# 注意:必须显式 + 拼接 —— 括号内隐式字面量拼接会把 ' '*900 变成
# "前段整体重复 900 次"(组爆炸),这是本夹具踩过的真实陷阱。
MINI_CHUNK = (
    # 共享 API 函数块(每个 chunk 都有 → 不能作归属依据)
    'url:"/order/orderEntrust/orderPage",method:"post"'
    'url:"/order/orderEntrust/orderAdd",method:"post"'
    # orderPage 调用点 + payload 字面量(GET/查询类才有)
    't.post("/order/orderEntrust/orderPage",{params:{page_no:1,bl_no:"",customer_id:""}})'
    # orderAdd 的表单配置组({type,name,key} 高置信)
    '{type:"input",name:"提单号",key:"bl_no",placeholder:""}'
    '{type:"select",name:"客户",key:"customer_id",options:[]}'
    '{type:"digit",name:"件数",key:"num"}'
) + ' ' * 900 + (
    # 800+ 字符间隙 → 切段,归 orderEdit 组(近并列都收)
    '{type:"input",name:"提单号",key:"bl_no"}'
    '{type:"textarea",name:"备注",key:"remark"}'
    '{type:"upload",name:"附件",key:"order_file"}'
    # 表格列 label(name 变体 prop)
    '{label:"提单号",width:120,name:"bl_no"},{label:"件数",width:80,prop:"num"}'
    # Vue data() 表单初始态模型(≥15 键且 ≥60% 空值)
    'form:{id:"",bl_no:"",customer_id:null,num:null,gross_weight:null,bulk:null,'
    'packer:"",cargo_type:null,trade_term:"",pol_cn:"",pod_cn:"",carrier:"",'
    'remark:"",order_file:[],copy_order_id:"",is_delayed:0}'
)

# 无关端点的键:防跨页污染(交集不足不归属)
DISTRACT = (
    '{type:"input",name:"发票号",key:"invoice_no"}}'
    '{type:"select",name:"币种",key:"currency_id"}}'
)


def _actions():
    def act(ctrl, action, keys):
        a = ActionIR(module="Order", controller=ctrl, action=action)
        a.rules = [RuleEntry(key=k, rules="require") for k in keys]
        return a
    return [
        act("OrderEntrust", "orderPage", ["page_no", "bl_no", "customer_id"]),
        act("OrderEntrust", "orderAdd",
            ["bl_no", "customer_id", "num", "gross_weight", "cargo_type",
             "trade_term", "packer", "pol_cn"]),
        act("OrderEntrust", "orderEdit", ["bl_no", "remark", "order_file"]),
    ]


def test_fe_path_strips_api_prefix():
    assert _fe_path("/api/order/orderEntrust/orderAdd") == "/order/orderEntrust/orderAdd"
    assert _fe_path("/order/x") == "/order/x"


def test_scan_chunk_extracts_registry_and_literals(tmp_path):
    f = tmp_path / "chunk-mini.js"
    f.write_text(MINI_CHUNK, encoding="utf-8")
    c = _scan_chunk(f)
    assert "/order/orderEntrust/orderPage" in c["urls"]
    assert "/order/orderEntrust/orderAdd" in c["urls"]
    assert c["methods"]["/order/orderEntrust/orderAdd"] == "post"
    # payload:orderPage 调用点 params 顶层键
    assert set(c["payload"]["/order/orderEntrust/orderPage"]) == \
        {"page_no", "bl_no", "customer_id"}
    # 表单配置:两组(间隙切段)
    keys_all = {k for g in c["groups"] for *_t, _z, k in g}
    assert {"bl_no", "customer_id", "num", "order_file"} <= keys_all
    # label:两种列字面量都收
    assert c["labels"]["bl_no"] == "提单号" and c["labels"]["num"] == "件数"
    # data() 模型:16 键、≥60% 空 → 收
    model_keys = {k for m in c["models"] for *_t, _z, k in m}
    assert {"cargo_type", "trade_term", "copy_order_id"} <= model_keys


def test_scan_chunk_rejects_non_form_kv_run(tmp_path):
    # 值非空(菜单/配置对象):不满 60% 空值 → 不收为模型
    s = "cfg:{a:1,b:2,c:'x',d:'y',e:1,f:2,g:3,h:4,i:5,j:6,k:7,l:8,m:9,n:10,o:11,p:12,q:13,r:14,s:15}"
    f = tmp_path / "chunk-cfg.js"
    f.write_text(s, encoding="utf-8")
    assert _scan_chunk(f)["models"] == []


def test_scan_frontend_attribution_and_method(tmp_path):
    (tmp_path / "chunk-mini.js").write_text(MINI_CHUNK, encoding="utf-8")
    (tmp_path / "chunk-other.js").write_text(DISTRACT, encoding="utf-8")
    actions = _actions()
    faces = scan_frontend(tmp_path, actions)

    add = faces["fin.order_entrust.order_add"]
    # 表单配置 + data() 模型都归 add;zh/fe_type 来自配置
    fk = add.form_keys
    assert {"bl_no", "customer_id", "num", "cargo_type", "trade_term"} <= set(fk)
    assert fk["bl_no"]["zh"] == "提单号"
    assert fk["customer_id"]["fe_type"] == "select"
    # 近并列:orderEdit 组(间隙切段后)键同源 → 也收
    edit = faces["fin.order_entrust.order_edit"]
    assert "order_file" in edit.form_keys
    # URL 命中 → method 回写为 FE 实证(非假设)
    by_id = {a.id: a for a in actions}
    assert by_id["fin.order_entrust.order_add"].method == "POST"
    assert by_id["fin.order_entrust.order_add"].method_assumed is False
    # payload 归 page
    assert set(faces["fin.order_entrust.order_page"].payload_keys) == \
        {"page_no", "bl_no", "customer_id"}
    # 干扰键不归属任何端点(发票/币种不在后端键集)
    for f in faces.values():
        assert "invoice_no" not in f.form_keys and "currency_id" not in f.form_keys
    # label:拥有组的端点才吃
    assert faces["fin.order_entrust.order_add"].label_keys.get("bl_no") == "提单号"


def test_scan_frontend_min_intersection_gate(tmp_path):
    # 单键交集(不足 FE_ASSIGN_MIN)→ 不归属
    s = 'url:"/order/orderEntrust/orderAdd",method:"post"'
    s += '{type:"input",name:"提单号",key:"bl_no"}'
    (tmp_path / "chunk-thin.js").write_text(s, encoding="utf-8")
    actions = _actions()
    faces = scan_frontend(tmp_path, actions)
    for f in faces.values():
        assert "bl_no" not in f.form_keys or len(f.form_keys) >= FE_ASSIGN_MIN


def test_rel_score_allows_near_ties(tmp_path):
    # 双集团:add 5 键全交,page 仅 3 键(< 80% 最高)→ page 不吃该组
    s = ('{type:"input",name:"a",key:"bl_no"}{type:"input",name:"b",key:"customer_id"}'
         '{type:"input",name:"c",key:"num"}{type:"input",name:"d",key:"cargo_type"}'
         '{type:"input",name:"e",key:"trade_term"}')
    (tmp_path / "chunk-tie.js").write_text(s, encoding="utf-8")

    def act(name, keys):
        a = ActionIR(module="Order", controller="OrderEntrust", action=name)
        a.rules = [RuleEntry(key=k, rules="require") for k in keys]
        return a
    actions = [
        act("orderAdd", ["bl_no", "customer_id", "num", "cargo_type", "trade_term"]),
        act("orderPage", ["bl_no", "customer_id", "num"]),
    ]
    faces = scan_frontend(tmp_path, actions)
    assert set(faces["fin.order_entrust.order_add"].form_keys) == \
        {"bl_no", "customer_id", "num", "cargo_type", "trade_term"}
    # 3/5 = 0.6 < _REL_SCORE → page 不归属
    assert "fin.order_entrust.order_page" not in faces


def test_fe_to_json_roundtrip():
    from twin_generator.s2c_frontend import FeFace
    f = FeFace(path="/api/x", method="post", form_keys={"a": {"zh": "甲", "fe_type": "select"}})
    j = fe_to_json({"fin.x.y": f})
    assert json.loads(json.dumps(j))["fin.x.y"]["form_keys"]["a"]["zh"] == "甲"
