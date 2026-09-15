# -*- coding: utf-8 -*-
"""Task 10 对照分析二:sem_bad 逐因拆解 + state 疑样本 + missing 键 schema 列核对。"""
import json, sys, csv
from pathlib import Path

REPO = Path(r"D:\Gimbal\Gimbal")
sys.path.insert(0, str(REPO / "src" / "gimbal-plate"))
from gimbal_plate.systems.fin.endpoint import ALL_ENDPOINTS  # noqa: E402

TWIN = REPO / "gimbal-tmp" / "twin_gen"
fields_raw = json.load(open(TWIN / "fields.json", encoding="utf-8"))
routes = json.load(open(TWIN / "routes.json", encoding="utf-8"))
GEN = {r["id"]: {f["key"]: f for f in fields_raw.get(r["id"], [])} for r in routes}
GEN_BY_PATH = {r["path"].lower(): r["id"] for r in routes}
RULES = {r["id"]: r["rules"] for r in routes}

# schema 列名集合(判断 missing 键是否为表列)
cols_by_name = {}
with open(r"D:\fin-test\fin_test_search.csv", encoding="utf-8-sig", newline="") as fh:
    for row in csv.DictReader(fh):
        cols_by_name.setdefault(row.get("column_name") or row.get("COLUMN_NAME") or "", []).append(
            row.get("table_name") or row.get("TABLE_NAME") or "?")

cause_cnt = {"zh": 0, "enum": 0, "required": 0, "multi": 0}
samples = {"zh": [], "enum": [], "required": []}
state_susp = []
total_bad = total_common = 0
missing_col_hit = {}

for ep in ALL_ENDPOINTS:
    eid = ep.id
    if eid == "fin.order.order_add_demo":       # 演示副本,排除统计
        continue
    hb = {d.name: d for d in (ep.request.declarations if ep.request else [])}
    path = (ep.api.path or "").lower()
    gen_id = GEN_BY_PATH.get(path) or eid
    gen = GEN.get(gen_id, {})
    common = set(hb) & set(gen)
    total_common += len(common)
    miss = sorted(set(hb) - set(gen))
    hit = sum(1 for k in miss if k in cols_by_name)
    missing_col_hit[eid] = (len(miss), hit)
    for k in common:
        d, g = hb[k], gen[k]
        bad = []
        if d.description and g.get("zh") != d.description:
            bad.append("zh")
        if d.enum and (g.get("enum_values") or None) != d.enum:
            bad.append("enum")
        if bool(d.required) != bool(g.get("required")):
            bad.append("required")
        for b in bad:
            cause_cnt[b] += 1
            if len(samples[b]) < 6:
                samples[b].append((eid, k, b,
                                   f"hb(zh={d.description!r},enum={d.enum!r},req={d.required})",
                                   f"gen(zh={g.get('zh')!r},enum={g.get('enum_values')!r},req={g.get('required')},rule_active={g.get('required')})"))
        if bad:
            total_bad += 1
        gs = g.get("state")
        if gs != d.state and not (d.state == "carry" and gs == "form" and g.get("read")):
            state_susp.append((eid, k, d.state, gs,
                               f"hb_vs={d.value_source} gen_read={g.get('read')} "
                               f"gen_vs={g.get('value_source')} flags={g.get('flags')}"))

print("common:", total_common, " sem_bad:", total_bad,
      f" 一致率={100*(total_common-total_bad)/max(total_common,1):.1f}%")
print("cause counts(zh/enum/required,含多因重复计):", cause_cnt)
for b in samples:
    print(f"\n-- {b} 样例 --")
    for s in samples[b]:
        print("  ", " | ".join(str(x) for x in s))
print("\n-- state 疑(", len(state_susp), ")全部 --")
for s in state_susp:
    print("  ", " | ".join(str(x) for x in s))
print("\n-- missing 键是表列的比例(逐 endpoint)--")
for eid, (m, h) in missing_col_hit.items():
    if m:
        print(f"   {eid:44s} missing={m:3d} 是DB列={h:3d}")
