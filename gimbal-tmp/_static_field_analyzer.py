"""提取 request.body 字段,排除框架字段和动态生成字段,只保留业务静态可配字段"""
import json
from collections import OrderedDict


def get_request_body_fields(data, label):
    """收集所有 step 的 request.body 字段路径 -> 值(只取第一个 step,作为模板参考)"""
    results = []
    for i, step in enumerate(data.get('steps', [])):
        req_body = step.get('request', {}).get('body', {})
        if not req_body:
            continue
        results.append((i, label, req_body))
    return results


def collect_paths(obj, prefix=""):
    out = OrderedDict()
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else k
            out.update(collect_paths(v, p))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            p = f"{prefix}[{i}]"
            out.update(collect_paths(v, p))
    else:
        out[prefix] = obj
    return out


with open('Scenario_Test_8.json', 'r', encoding='utf-8') as f:
    data8 = json.load(f)
with open('Scenario_Test_9.json', 'r', encoding='utf-8') as f:
    data9 = json.load(f)

# 取所有 step 的 request.body 字段并集
paths8 = set()
paths9 = set()
values8 = {}
values9 = {}

for i, label, body in get_request_body_fields(data8, '8'):
    for k, v in collect_paths(body).items():
        paths8.add(k)
        values8.setdefault(k, []).append((i, v))

for i, label, body in get_request_body_fields(data9, '9'):
    for k, v in collect_paths(body).items():
        paths9.add(k)
        values9.setdefault(k, []).append((i, v))

# 共同的字段
common = paths8 & paths9
only8 = paths8 - paths9
only9 = paths9 - paths8

# 排除框架字段(这些是固定必填的,与业务无关)
framework_fields = {
    'action',  # submit/check/audit, 由步骤语义决定(算业务字段,保留)
}

# 排除动态生成字段(每次跑都变,不是手动配置)
dynamic_value_patterns = [
    # 时间戳
    'create_time', 'update_time', 'sys_upttime', 'finance_date',
    'atd', 'etd', 'book_upload_date', 'bl_no_upload_date',
    'business_time', 'cancel_time', 'customer_confirm_date',
    'customer_due_date', 'customer_invoice_request_date',
    'customer_put_date', 'customer_put_date_manual',
    'discount_end', 'discount_start', 'effective_time',
    'first_financing_doc_ok_date', 'insurance_doc_ok_date',
    'real_cost_date', 'second_financing_doc_ok_date',
    'supplier_due_date', 'supplier_invoice_date',
    'supplier_pay_date', 'track_atd', 'trans_cost_put_preserve_date',
    'delete_time',
]

# 动态 ID 类字段(出现在 request.body 但本质是抓回来的 ID)
dynamic_id_fields = {
    'order_id', 'order_no', 'order_supplier_id', 'order_fee_real_ids',
    'audit_id', 'audit_ids', 'file_id',
}

# 输出
def classify(paths):
    """把字段分成:框架必填 / 动态生成 / 业务静态可配"""
    biz_static = []
    for p in sorted(paths):
        # 取最后一段 key
        last = p.split('.')[-1].split('[')[0]
        if last in dynamic_value_patterns or last in dynamic_id_fields:
            continue
        biz_static.append(p)
    return biz_static


print("=" * 80)
print("仅出现在 Test_8 的 request.body 字段(非空):")
only8_static = classify(only8)
for p in sorted(only8):
    if p in only8_static:
        # 找第一个非空值
        for i, v in values8[p]:
            if v not in (None, "", [], {}):
                print(f"  {p}  step[{i}] = {repr(v)[:80]}")
                break

print(f"\n(共 {len(only8_static)} 个 Test_8 独有 业务静态字段)")

print("\n" + "=" * 80)
print("仅出现在 Test_9 的 request.body 字段(非空):")
only9_static = classify(only9)
for p in sorted(only9):
    if p in only9_static:
        for i, v in values9[p]:
            if v not in (None, "", [], {}):
                print(f"  {p}  step[{i}] = {repr(v)[:80]}")
                break

print(f"\n(共 {len(only9_static)} 个 Test_9 独有 业务静态字段)")

print("\n" + "=" * 80)
print("共同字段中,业务静态可配但取值不同的:")
common_static = classify(common)
changed = []
for p in sorted(common):
    if p not in common_static:
        continue
    v8_list = [v for i, v in values8[p] if v not in (None, "", [], {})]
    v9_list = [v for i, v in values9[p] if v not in (None, "", [], {})]
    v8 = v8_list[0] if v8_list else None
    v9 = v9_list[0] if v9_list else None
    if v8 != v9:
        changed.append((p, v8, v9))

print(f"  共 {len(changed)} 个值不同的业务静态字段")
for p, v8, v9 in changed:
    print(f"  {p}")
    print(f"    Test_8: {repr(v8)[:80]}")
    print(f"    Test_9: {repr(v9)[:80]}")

print("\n" + "=" * 80)
print("共同字段中,业务静态可配且取值相同的(可作为'通用模板字段'复用):")
same = []
for p in sorted(common):
    if p not in common_static:
        continue
    v8_list = [v for i, v in values8[p] if v not in (None, "", [], {})]
    v9_list = [v for i, v in values9[p] if v not in (None, "", [], {})]
    v8 = v8_list[0] if v8_list else None
    v9 = v9_list[0] if v9_list else None
    if v8 == v9 and v8 is not None:
        same.append((p, v8))

print(f"  共 {len(same)} 个完全相同的业务静态字段")
for p, v in same:
    print(f"  {p} = {repr(v)[:80]}")