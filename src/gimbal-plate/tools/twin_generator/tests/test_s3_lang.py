"""T3.1 Lang 语言包解析回归钉。

实录结构(D:\\fin-test Common/Lang/zh-cn.php):
- else if 链 + 多控制器条件(||);
- array() 与 [] 两种块体;
- 嵌套数组值(分段文案)与注释行不收;
- 模块级 Lang 直给、优先于 Common。
"""
from pathlib import Path

from twin_generator.s3_lang import load_langs, lang_zh

COMMON = """<?php
$controller = lcfirst(CONTROLLER_NAME);
$lang = [];
if ($controller == "customer") {
    $lang = array(
        'customer_name_en' => '英文名称',
        // 注释行不收 commented_out => '不该出现'
        'currency' => '账户类型',
    );
} else if ($controller == "audit") {
    $lang = [
        'supplier_name' => '供应商名称',
    ];
} else if ($controller == "order" || $controller == "orderEntrust") {
    $lang = [
        'service_id' => '客服',
        'fee_msg' => [
            1 => '分段文案一',
            2 => '分段文案二',
        ],
        'bl_no' => '提单号',
    );
}
"""

MODULE_LANG = """<?php
$lang = [
    'payment_status' => '回款状态',
    'LOGIN_PWD_ERROR' => '密码错误,请重新输入',
    'customer_name_en' => '模块级覆盖英文名',
];
"""


def _app(tmp_path: Path) -> Path:
    (tmp_path / "Common" / "Lang").mkdir(parents=True)
    (tmp_path / "Common" / "Lang" / "zh-cn.php").write_text(
        COMMON, encoding="utf-8")
    (tmp_path / "Operation" / "Lang").mkdir(parents=True)
    (tmp_path / "Operation" / "Lang" / "zh-cn.php").write_text(
        MODULE_LANG, encoding="utf-8")
    return tmp_path


def test_load_langs_blocks_and_multi_controller(tmp_path):
    cbc, ml = load_langs(_app(tmp_path))
    assert cbc["customer"]["customer_name_en"] == "英文名称"
    assert cbc["customer"]["currency"] == "账户类型"
    assert "commented_out" not in cbc["customer"]
    assert cbc["audit"]["supplier_name"] == "供应商名称"
    # || 条件:order 与 orderentrust 同块
    assert cbc["order"]["bl_no"] == cbc["orderentrust"]["bl_no"] == "提单号"
    # 嵌套数组值不收
    assert "fee_msg" not in cbc["order"]
    assert ml["Operation"]["payment_status"] == "回款状态"


def test_lang_zh_module_overrides_common(tmp_path):
    cbc, ml = load_langs(_app(tmp_path))
    v = lang_zh("Customer", "Operation", cbc, ml)
    assert v["customer_name_en"] == "模块级覆盖英文名"   # 模块级 > Common
    assert v["currency"] == "账户类型"                    # Common 兜底


def test_lang_zh_missing_controller_empty(tmp_path):
    cbc, ml = load_langs(_app(tmp_path))
    assert lang_zh("Nonexistent", "Operation", cbc, ml)["payment_status"] == "回款状态"
    assert "bl_no" not in lang_zh("Customer", "Order", cbc, ml)


CTRL_HEADER = """<?php
namespace Order\\Controller;
class OrderController {
    private $orderHeader = [
        'trade_term' => '成交方式',
        // 'is_usd_project' => '是否为美元项目',
        'bl_no' => '提单号',
        'nested' => ['a' => '嵌套不收'],
    ];
}
"""


def test_load_headers(tmp_path):
    from twin_generator.s3_lang import load_headers
    (tmp_path / "Order" / "Controller").mkdir(parents=True)
    (tmp_path / "Order" / "Controller" /
     "OrderController.class.php").write_text(CTRL_HEADER, encoding="utf-8")
    hs = load_headers(tmp_path)
    assert hs["order"]["trade_term"] == "成交方式"
    assert hs["order"]["bl_no"] == "提单号"
    assert "is_usd_project" not in hs["order"]    # 注释行不收
    assert "nested" not in hs["order"]            # 嵌套数组不收


def test_enrich_zh_chain_header_before_column(tmp_path):
    from twin_generator.ir import ActionIR, RuleEntry
    from twin_generator.s3_semantics import enrich
    from twin_generator.schema_source import ColumnCatalog, ColumnInfo

    a = ActionIR(module="Order", controller="Order", action="orderExport")
    a.rules = [RuleEntry(key="trade_term", rules="require")]
    cat = ColumnCatalog([ColumnInfo(
        table="sys_order", column="trade_term", col_type="varchar(8)",
        nullable=True, default=None, comment="列注释成交方式")])
    fs = enrich([a], cat, None, {}, {"order": {"trade_term": "表头成交方式"}})
    f = fs["fin.order.order_export"][0]
    assert f.zh == "表头成交方式" and f.zh_source == "header"


def test_enrich_zh_chain_rule_gt_lang(tmp_path):
    from twin_generator.ir import ActionIR, RuleEntry
    from twin_generator.s3_semantics import enrich
    from twin_generator.schema_source import ColumnCatalog

    a = ActionIR(module="Order", controller="OrderEntrust", action="orderAdd")
    a.rules = [
        RuleEntry(key="bl_no", rules="require", zh="规则提单号"),
        RuleEntry(key="pod_cn", rules="require"),          # 无规则 zh
    ]
    fs = enrich([a], ColumnCatalog([]), None,
                {"fin.order_entrust.order_add": {"bl_no": "语言包提单号",
                                                  "pod_cn": "目的港"}})
    by = {f.key: f for f in fs["fin.order_entrust.order_add"]}
    assert by["bl_no"].zh == "规则提单号" and by["bl_no"].zh_source == "rule"
    assert by["pod_cn"].zh == "目的港" and by["pod_cn"].zh_source == "lang"
