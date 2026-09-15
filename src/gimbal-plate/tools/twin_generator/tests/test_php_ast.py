from twin_generator.php_ast import is_string_literal, load, text_of, classes
from conftest import FIXTURES

PHP = FIXTURES / "php" / "sample_validator.php"


def test_load_and_classes():
    pf = load(PHP)
    assert not pf.tree.root_node.has_error
    cls = classes(pf)
    assert len(cls) == 1
    name, cnode, decl = cls[0]
    assert name == "OrderEntrustValidator"
    # declaration_list 内可找到方法/属性节点(类型抽查)
    types = [n.type for n in pf.walk()]
    assert "property_element" in types
    assert "comment" in types


def test_text_of_and_walk():
    pf = load(PHP)
    strs = [text_of(pf, n) for n in pf.walk() if n.type == "string"]
    assert "'customer_id'" in strs          # 带引号原文
    assert "'require|num'" in strs


def test_is_string_literal_rejects_interpolation(tmp_path):
    """评审 Minor-3:插值排除分支的负例钉死 —— "a{$v}b"/"a$b" 不是字面量。"""
    f = tmp_path / "interp.php"
    f.write_bytes(b"""<?php
class T
{
    public static $x = [
        'interp_brace' => "a{$v}b",
        'interp_simple' => "a$b",
        'empty' => "",
        'plain_dq' => "plain",
        'plain_sq' => 'plain',
    ];
}
""")
    pf = load(f)
    assert not pf.tree.root_node.has_error
    by_text = {}
    for n in pf.walk():
        if n.type in ("string", "encapsed_string"):
            by_text.setdefault(text_of(pf, n), n)
    # 插值:encapsed_string 的 named_children 含变量 → 不得判字面量
    assert is_string_literal(by_text['"a{$v}b"']) is False
    assert is_string_literal(by_text['"a$b"']) is False
    # 无插值字面量:空串/普通双引号/单引号
    assert is_string_literal(by_text['""']) is True
    assert is_string_literal(by_text['"plain"']) is True
    assert is_string_literal(by_text["'plain'"]) is True
