# -*- coding: utf-8 -*-
"""Task 10 对照分析三:spec §8 维度(zh/enum/default)一致率 + required 单列 + 非 DB missing 清单。"""
import json, sys, csv
from pathlib import Path

REPO = Path(r"D:\Gimbal\Gimbal")
sys.path.insert(0, str(REPO / "src" / "gimbal-plate"))
from gimbal_plate.systems.fin.endpoint import ALL_ENDPOINTS  # noqa: E402

TWIN = REPO / "src/gimbal-plate/tmp/twin_gen"
fields_raw = json.load(open(TWIN / "fields.json", encoding="utf-8"))
routes = json.load(open(TWIN / "routes.json", encoding="utf-8"))
GEN = {r["id"]: {f["key"]: f for f in fields_raw.get(r["id"], [])} for r in routes}
GEN_BY_PATH = {r["path"].lower(): r["id"] for r in routes}

cols_by_name = set()
with open(r"D:\fin-test\fin_test_search.csv", encoding="utf-8-sig", newline="") as fh:
    for row in csv.DictReader(fh):
        cols_by_name.add(row.get("column_name") or row.get("COLUMN_NAME") or "")

core_bad = req_bad = total = enum_false_attach = 0
core_samples, reqA, reqB = [], [], []
nondb = {}
hb_keys_total = missing_total = extra_total = 0
zh_cmp = zh_ok = 0
enum_mismatch = 0
# 可选模块过滤(与 cli --modules 同口径):python analyze3.py Order,Customer,Audit
# 不传 = 全量手建对比(要求产物也是全量跑的,否则模块外全键计 missing 误导)
_mods = {m.strip().lower() for m in (sys.argv[1] if len(sys.argv) > 1 else "").split(",") if m.strip()}
for ep in ALL_ENDPOINTS:
    eid = ep.id
    if eid == "fin.order.order_add_demo":
        continue
    if _mods and eid.split(".")[1] not in _mods:
        continue
    hb = {d.name: d for d in (ep.request.declarations if ep.request else [])}
    gen = GEN.get(GEN_BY_PATH.get((ep.api.path or "").lower()) or eid, {})
    common = set(hb) & set(gen)
    total += len(common)
    hb_keys_total += len(hb)
    missing_total += len(set(hb) - set(gen))
    extra_total += len(set(gen) - set(hb))
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
        if d.description:
            zh_cmp += 1
            if g.get("zh") == d.description:
                zh_ok += 1
        if d.enum and (g.get("enum_values") or None) != d.enum:
            enum_mismatch += 1
        # 误挂方向:手建无 enum 而生成挂了
        if not d.enum and g.get("enum_values"):
            enum_false_attach += 1
        if bool(d.required) != bool(g.get("required")):
            req_bad += 1
            row = (eid, k, f"hb={d.required}", f"gen={g.get('required')}")
            (reqA if d.required else reqB).append(row)

# 生成面全局 zh 覆盖率(fields.json 全量)
_gen_all = [f for fs in fields_raw.values() for f in fs]
_gen_zh_hit = sum(1 for f in _gen_all if f.get("zh"))
_gen_total = len(_gen_all)

summary = {
    "scope": "handbuilt ground truth(排除 demo)",
    "hb_keys_total": hb_keys_total,
    "missing_total": missing_total,
    "missing_pct": round(100 * missing_total / hb_keys_total, 1) if hb_keys_total else None,
    "extra_total": extra_total,
    "common": total,
    "core_bad": core_bad,
    "core_consistency_pct": round(100 * (total - core_bad) / total, 1) if total else None,
    "zh_compared": zh_cmp,
    "zh_match": zh_ok,
    # 口径注:手建 DeclarationEntry 无 description(中文不在手建面),
    # zh 一致率仅当 hb 偶带 description 时才有意义 —— zh 验收以生成面
    # 自评覆盖率(gen_zh_coverage_pct)为准。
    "zh_consistency_pct": round(100 * zh_ok / zh_cmp, 1) if zh_cmp else None,
    "enum_mismatch": enum_mismatch,
    "enum_false_attach": enum_false_attach,
    "req_bad": req_bad,
    "reqA_hbTrue_genFalse": len(reqA),
    "reqB_hbFalse_genTrue": len(reqB),
    "gen_field_total": _gen_total,
    "gen_zh_coverage_pct": round(100 * _gen_zh_hit / _gen_total, 1) if _gen_total else None,
    "missing_non_db": nondb,
}
(TWIN / "summary.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"common={total} 核心维度坏={core_bad} 一致率={100*(total-core_bad)/total:.1f}%")
print(f"missing={missing_total}/{hb_keys_total} extra={extra_total}")
print(f"summary.json → {TWIN / 'summary.json'}")
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
