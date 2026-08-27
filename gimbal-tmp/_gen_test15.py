"""
Generate Scenario_Test_15_HUOSHAN_YIHANGDAO.json from Scenario_Test_14.json
by applying the field replacements specified by the user.

Replacements are based on the new customer/policy/mains:
- Customer: 北京火山引擎科技有限公司 (id=60934)
- Policy: 陆旭阳多主体服务策略-自动匹配 (id=296905601001193472)
- Mains: 易航道(1), 易汇联(3), 青岛易汇航(2), 上海一帜(6)
- Supplier: 青岛菲尔斯特物流有限公司 (id=14)
- Service: 李明丹tidb (id=40)
- Operator: 孙奉盛 (id=41)
"""
import json
import re
from pathlib import Path

SRC = Path(r"D:\Gimbal\Gimbal\gimbal-tmp\Scenario_Test_14.json")
DST = Path(r"D:\Gimbal\Gimbal\gimbal-tmp\Scenario_Test_15_HUOSHAN_YIHANGDAO.json")

# Read source as text so we can apply targeted replacements while keeping
# the rest of the file (IDs, strategy blocks, etc.) byte-for-byte identical.
text = SRC.read_text(encoding="utf-8")

# ---------- Replacement definitions ----------
# Each entry: (old, new). Apply ALL occurrences with replace_all semantics.
# Strings are matched literally (case-sensitive, no regex). We avoid regex
# to not accidentally hit unrelated fields.

replacements = [
    # --- meta ---
    ("山东悦慕-易汇瀚-成都空港", "北京火山引擎-易航道-陆旭阳自动匹配"),

    # --- vars (bank / finance ids) ---
    ("319666690256273408_MainBank", "11_MainBank"),
    ("319666690256274432_MainBank", "26_MainBank"),
    ("4416_CustomerFinance", "335703029267300352_CustomerFinance"),
    ("4415_CustomerFinance", "335703029334409216_CustomerFinance"),

    # --- client_expand ---
    ("\"client_expand_id\": \"261\"", "\"client_expand_id\": \"16\""),
    ("\"client_expand_name\": \"唐欣雨\"", "\"client_expand_name\": \"荣洋\""),

    # --- customer identity ---
    ("\"customer_id\": \"320\"", "\"customer_id\": \"60934\""),
    ("\"customer_name\": \"山东悦慕食品有限公司\"", "\"customer_name\": \"北京火山引擎科技有限公司\""),
    ("\"customer_tax_number\": \"91370786MA3D6MW35A\"", "\"customer_tax_number\": \"91110108MA01R70K8D\""),
    ("\"customer_address_cn\": \"山东省潍坊市昌邑市围子街道206国道北(官道郜北)\"",
     "\"customer_address_cn\": \"测试1\""),

    # --- customer_category: Test14 had ",1,2," (direct + agent). New customer
    #     category list is ["1"] -> ",1,"
    ("\"customer_category\": \",1,2,\"", "\"customer_category\": \",1,\""),

    # --- customer_main (subject) ---
    ("\"customer_main_id\": \"15\"", "\"customer_main_id\": \"1\""),
    ("\"customer_main_name\": \"成都易汇瀚供应链管理有限公司\"",
     "\"customer_main_name\": \"青岛易航道物流科技有限公司\""),

    # --- service / operator ---
    ("\"service_id\": \"55\"", "\"service_id\": \"40\""),
    ("\"service_name\": \"曲静霞\"", "\"service_name\": \"李明丹tidb\""),
    ("\"operator_id\": \"336\"", "\"operator_id\": \"41\""),
    ("\"operator_name\": \"闫航\"", "\"operator_name\": \"孙奉盛\""),

    # --- main_sort / main_ids / main_ids_name ---
    ("\"main_sort\": \"易汇瀚,易海,易航道\"",
     "\"main_sort\": \"易航道,易汇联,青岛易汇航,上海一帜\""),
    ("\"main_ids\": \"15,16,1\"", "\"main_ids\": \"1,3,2,6\""),
    ("\"main_ids\": \",15,16,1,\"", "\"main_ids\": \",1,3,2,6,\""),
    ("\"main_ids_name\": \"易汇瀚,易海,易航道\"",
     "\"main_ids_name\": \"易航道,易汇联,青岛易汇航,上海一帜\""),

    # --- policy ---
    ("\"policy_id\": \"134\"", "\"policy_id\": \"296905601001193472\""),
    ("\"policy_name\": \"【SPV对客】易汇瀚（仅人民币）\"",
     "\"policy_name\": \"陆旭阳多主体服务策略-自动匹配\""),

    # --- product / settle_type / deposit / period_delay ---
    ("\"product_id\": \"4\"", "\"product_id\": \"3\""),
    ("\"product_name\": \"月结-不延长-保证金\"",
     "\"product_name\": \"票结-不延长-保证金\""),
    ("\"settle_type\": \"1\"", "\"settle_type\": \"2\""),
    ("\"settle_type_name\": \"月结\"", "\"settle_type_name\": \"票结\""),

    # --- period / payment config ---
    ("\"receive_time_limit\": \"20\"", "\"receive_time_limit\": \"7\""),
    ("\"deposit_refund_day\": \"180\"", "\"deposit_refund_day\": \"60\""),
    ("\"payment_type\": \"0\"", "\"payment_type\": \"2\""),
    ("\"period_rule\": \"0\"", "\"period_rule\": \"1\""),

    # --- policy_match: Test14 was "semi" (manual select). New policy is auto-match ---
    ("\"policy_match\": \"semi\"", "\"policy_match\": \"auto\""),
    ("\"policy_match_name\": \"手动选择\"", "\"policy_match_name\": \"自动匹配\""),

    # --- policy_main_arr (note: order is now 易航道(1), 易汇联(3), 青岛易汇航(2), 上海一帜(6)) ---
    ("\"policy_main_arr\": [\n            {\n              \"fee_main_id\": \"15\",\n              \"main_name\": \"成都易汇瀚供应链管理有限公司\"\n            },\n            {\n              \"fee_main_id\": \"16\",\n              \"main_name\": \"青岛易海供应链管理有限公司\"\n            },\n            {\n              \"fee_main_id\": \"1\",\n              \"main_name\": \"青岛易航道物流科技有限公司\"\n            }\n          ]",
     "\"policy_main_arr\": [\n            {\n              \"fee_main_id\": \"1\",\n              \"main_name\": \"青岛易航道物流科技有限公司\"\n            },\n            {\n              \"fee_main_id\": \"3\",\n              \"main_name\": \"青岛易汇联供应链管理有限公司\"\n            },\n            {\n              \"fee_main_id\": \"2\",\n              \"main_name\": \"青岛易汇航供应链管理有限公司\"\n            },\n            {\n              \"fee_main_id\": \"6\",\n              \"main_name\": \"上海一帜供应链管理有限公司\"\n            }\n          ]"),

    # --- supplier ---
    ("\"supplier_id\": \"805\"", "\"supplier_id\": \"14\""),
    ("\"supplier_name\": \"青岛雅然国际物流有限公司\"",
     "\"supplier_name\": \"青岛菲尔斯特物流有限公司\""),
    ("\"settle_object_id\": \"1384\"", "\"settle_object_id\": \"46\""),
    ("\"supplier_label\": \"青岛雅然国际物流有限公司-订舱\"",
     "\"supplier_label\": \"青岛菲尔斯特物流有限公司-订舱\""),
]

# Track replacement counts for verification
counts = {}
for old, new in replacements:
    n = text.count(old)
    if n == 0:
        print(f"WARNING: pattern not found -> {old[:60]!r}")
    counts[(old, new)] = n
    text = text.replace(old, new)

DST.write_text(text, encoding="utf-8")

print(f"\nWrote: {DST}")
print(f"Size:  {DST.stat().st_size} bytes")
print(f"\nReplacement counts:")
for (old, new), n in counts.items():
    print(f"  {n:3d}x  {old[:70]!r}  ->  {new[:70]!r}")
