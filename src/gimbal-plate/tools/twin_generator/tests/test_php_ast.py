from twin_generator.php_ast import load, text_of, classes
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
