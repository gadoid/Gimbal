"""比较两个 JSON 文件,提取所有字段路径并对比差异 -> 输出到文件"""
import json
from collections import OrderedDict


def flatten(obj, prefix=""):
    out = OrderedDict()
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else k
            out.update(flatten(v, p))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            p = f"{prefix}[{i}]"
            out.update(flatten(v, p))
    else:
        out[prefix] = obj
    return out


with open('Scenario_Test_8.json', 'r', encoding='utf-8') as f:
    data8 = json.load(f)
with open('Scenario_Test_9.json', 'r', encoding='utf-8') as f:
    data9 = json.load(f)

flat8 = flatten(data8)
flat9 = flatten(data9)

keys8 = set(flat8.keys())
keys9 = set(flat9.keys())

only8 = keys8 - keys9
only9 = keys9 - keys8
common = keys8 & keys9

lines = []
def w(s=""):
    lines.append(s)

w("=" * 80)
w(f"Test_8 总字段数: {len(flat8)}")
w(f"Test_9 总字段数: {len(flat9)}")
w(f"共同字段数: {len(common)}")
w(f"仅 Test_8 存在: {len(only8)}")
w(f"仅 Test_9 存在: {len(only9)}")
w("=" * 80)

w("\n>>> 仅 Test_8 存在(且为非空值)的字段:")
count = 0
for k in sorted(only8):
    v = flat8[k]
    if v not in (None, "", [], {}):
        sv = repr(v)
        if len(sv) > 160:
            sv = sv[:160] + "..."
        w(f"  {k} = {sv}")
        count += 1
w(f"  (共 {count} 个非空字段)")

w("\n>>> 仅 Test_9 存在(且为非空值)的字段:")
count = 0
for k in sorted(only9):
    v = flat9[k]
    if v not in (None, "", [], {}):
        sv = repr(v)
        if len(sv) > 160:
            sv = sv[:160] + "..."
        w(f"  {k} = {sv}")
        count += 1
w(f"  (共 {count} 个非空字段)")

w("\n>>> 共同字段中值不同的:")
diff_count = 0
same_count = 0
diff_keys = []
for k in sorted(common):
    if flat8[k] != flat9[k]:
        diff_count += 1
        diff_keys.append(k)
    else:
        same_count += 1
w(f"  不同: {diff_count}, 相同: {same_count}")

# 按类型分组
diff_by_type = {}
for k in diff_keys:
    v = flat8[k]
    t = type(v).__name__
    diff_by_type.setdefault(t, []).append(k)

w("\n>>> 不同字段按类型分布:")
for t, ks in diff_by_type.items():
    w(f"  {t}: {len(ks)} 个")

w("\n>>> 所有差异字段 (路径 -> 8值 / 9值):")
for k in diff_keys:
    v8 = flat8[k]
    v9 = flat9[k]
    s8 = repr(v8)
    s9 = repr(v9)
    if len(s8) > 120:
        s8 = s8[:120] + "..."
    if len(s9) > 120:
        s9 = s9[:120] + "..."
    w(f"  {k}")
    w(f"    8: {s8}")
    w(f"    9: {s9}")

with open('_diff_result.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print(f"写入 {len(lines)} 行 -> _diff_result.txt")