from twin_generator.s1_routes import scan_actions
from twin_generator.s2_validator import attach_rules
from twin_generator.s2_reads import collect_reads
from twin_generator.s3_semantics import enrich, load_enums
from twin_generator.schema_source import load_columns
from conftest import FIXTURES

APP = FIXTURES / "php" / "app" / "Application"


def test_enrich():
    acts = scan_actions(APP)
    attach_rules(acts, APP)
    collect_reads(acts, APP)
    enums = load_enums(APP)
    assert ("0", "创建中") in enums["EXPECT_CREATING"]
    fields = enrich(acts, load_columns(FIXTURES / "schema" / "fin_test_search.csv"))
    by_key = {f.key: f for f in fields["fin.order_entrust.order_add"]}
    # zh 优先级:rule(客户ID) > column > derived
    assert by_key["customer_id"].zh == "客户ID" and by_key["customer_id"].zh_source == "rule"
    # customer_id 被读(getData)→ read=True
    assert by_key["customer_id"].read is True
    # bl_no:rule 注释「提单号」优先于 column「业务订单ID」
    assert by_key["bl_no"].zh == "提单号"
    # 被注释行 carrier:无 column 匹配 → zh 来自 rule 注释;
    # 但校验派生只认活跃行 —— 注释 present 不产 required
    assert by_key["carrier"].zh == "船公司/承运人"
    assert by_key["carrier"].required is False
    # 类型:etd column int → integer;default 来自 getDataString 第三参
    assert by_key["etd"].type_ == "integer"
    assert by_key["action"].default == "submit"
    # enum:rule in: 优先且为字符串
    assert by_key["settle_type"].enum_values == ["1", "2"]
    # _name 派生:customer_name 无任何源 → 客户ID+名称
    assert by_key["customer_name"].zh == "客户ID名称" and by_key["customer_name"].zh_source == "derived"
