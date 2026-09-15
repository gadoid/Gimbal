# -*- coding: utf-8 -*-
"""Task 10 对照分析三:spec §8 维度(zh/enum/default)一致率 + required 单列 + 非 DB missing 清单。"""
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

cols_by_name = set()
with open(r"D:\fin-test\fin_test_search.csv", encoding="utf-8-sig", newline="") as fh:
    for row in csv.DictReader(fh):
        cols_by_name.add(row.get("column_name") or row.get("COLUMN_NAME") or "")

core_bad = req_bad = total = 0
core_samples, reqA, reqB = [], [], []
nondb = {}
for ep in ALL_ENDPOINTS:
    eid = ep.id
    if eid == "fin.order.order_add_demo":
        continue
    hb = {d.name: d for d in (ep.request.declarations if ep.request else [])}
    gen = GEN.get(GEN_BY_PATH.get((ep.api.path or "").lower()) or eid, {})
    common = set(hb) & set(gen)
    total += len(common)
    miss_non_db = [k for k in sorted(set(hb) - set(gen)) if k not in cols_by_name]
    if miss_non_db:
        nondb[eid] = miss_non_db
    for k in common:
        d, g = hb[k], gen[k]
        bad = []
        if d.description and g.get("zh") != d.description:
            bad.append("zh")
        if d.enum and (g.get("enum_values") or None) != d.enum:
            bad.append("enum")
        if d.default is not None and (g.get("default") or None) != d.default:
            bad.append("default")
        if bad:
            core_bad += 1
            if len(core_samples) < 15:
                core_samples.append((eid, k, bad, d.description, d.enum, d.default,
                                     g.get("zh"), g.get("enum_values"), g.get("default")))
        if bool(d.required) != bool(g.get("required")):
            req_bad += 1
            row = (eid, k, f"hb={d.required}", f"gen={g.get('required')}")
            (reqA if d.required else reqB).append(row)

print(f"common={total} 核心维度坏={core_bad} 一致率={100*(total-core_bad)/total:.1f}%")
print(f"required 分歧={req_bad}(其中 hb=True/gen=False {len(reqA)},hb=False/gen=True {len(reqB)})")
print("\n-- 核心维度(zh/enum/default)分歧样例 --")
for s in core_samples:
    print("  ", s)
print("\n-- 非 DB 列 missing 逐条 --")
for eid, ks in nondb.items():
    print(f"  {eid}: {ks}")
print("\n-- required 分歧 hb=True→gen=False --")
for r in reqA:
    print("  ", r)
print("-- required 分歧 hb=False→gen=True(计数,样例10)--", len(reqB))
for r in reqB[:10]:
    print("  ", r)
