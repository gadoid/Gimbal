# -*- coding: utf-8 -*-
"""Task 10 对照分析:键集召回/语义一致率/state 分歧分类(只读,零 HTTP)。"""
import json, sys
from pathlib import Path

REPO = Path(r"D:\Gimbal\Gimbal")
sys.path.insert(0, str(REPO / "src" / "gimbal-plate"))
from gimbal_plate.systems.fin.endpoint import ALL_ENDPOINTS  # noqa: E402

TWIN = REPO / "src/gimbal-plate/tmp/twin_gen"
routes = json.load(open(TWIN / "routes.json", encoding="utf-8"))
fields_raw = json.load(open(TWIN / "fields.json", encoding="utf-8"))

# fields.json 里 value_source 是 __dict__ 序列化(元组→list 或 str),按 JSON 读回
def gen_fields(act_id):
    out = {}
    for f in fields_raw.get(act_id, []):
        vs = f.get("value_source")
        if isinstance(vs, str):
            # default=str 把元组序列化成了 str "('view', 'col')"
            try:
                vs = tuple(json.loads(vs.replace("(", "[").replace(")", "]")))
            except Exception:
                vs = None
        elif isinstance(vs, list):
            vs = tuple(vs)
        f["value_source"] = vs
        out[f["key"]] = f
    return out

GEN = {r["id"]: gen_fields(r["id"]) for r in routes}
GEN_BY_PATH = {r["path"]: r["id"] for r in routes}

def hb_face(ep):
    if ep.request is None:
        return {}
    return {d.name: d for d in ep.request.declarations}

rows, unmapped = [], []
for ep in ALL_ENDPOINTS:
    hb = hb_face(ep)
    path = ep.api.path if ep.api else None
    gen_id = GEN_BY_PATH.get(path)
    via = "path"
    if gen_id is None:
        gen_id = ep.id
        via = "id"
    gen = GEN.get(gen_id, {})
    if gen_id not in GEN and via == "id":
        unmapped.append((ep.id, path))
        continue
    hb_keys, gen_keys = set(hb), set(gen)
    missing = sorted(hb_keys - gen_keys)
    extra = sorted(gen_keys - hb_keys)
    common = sorted(hb_keys & gen_keys)
    sem_bad, state_cls = [], {"match": 0, "form_cand": 0, "suspicious": 0}
    for k in common:
        d, g = hb[k], gen[k]
        genum = g.get("enum_values")
        ok = True
        if d.description and g.get("zh") != d.description:
            ok = False
        if (d.enum or None) and (genum or None) != d.enum:
            ok = False
        if d.enum and not genum:
            ok = False
        if bool(d.required) != bool(g.get("required")):
            ok = False
        if not ok:
            sem_bad.append(k)
        gs = g.get("state")
        if gs == d.state:
            state_cls["match"] += 1
        elif d.state == "carry" and gs == "form" and g.get("read"):
            state_cls["form_cand"] += 1
        else:
            state_cls["suspicious"] += 1
    rows.append(dict(id=ep.id, gen_id=gen_id, via=via, hb=len(hb), gen=len(gen),
                     missing=missing, extra=extra, common=len(common),
                     sem_bad=sem_bad, **state_cls))

print(f"{'handbuilt id':44s} {'via':4s} {'gen id':40s} hb  gen  miss extr 语义bad  st匹配/候选/疑")
tot = dict(hb=0, gen=0, miss=0, extr=0, sem=0, m=0, fc=0, sp=0)
for r in rows:
    print(f"{r['id']:44s} {r['via']:4s} {r['gen_id']:40s} "
          f"{r['hb']:3d} {r['gen']:4d} {len(r['missing']):4d} {len(r['extra']):4d} "
          f"{len(r['sem_bad']):4d}   {r['match']:3d}/{r['form_cand']:3d}/{r['suspicious']:3d}")
    tot["hb"] += r["hb"]; tot["gen"] += r["gen"]; tot["miss"] += len(r["missing"])
    tot["extr"] += len(r["extra"]); tot["sem"] += len(r["sem_bad"])
    tot["m"] += r["match"]; tot["fc"] += r["form_cand"]; tot["sp"] += r["suspicious"]
print()
print("TOTAL handbuilt keys:", tot["hb"], " gen keys(common ids):", tot["gen"])
print("missing:", tot["miss"], " extra:", tot["extr"])
common_all = tot["hb"] - tot["miss"]
print("common keys:", common_all, " sem_bad:", tot["sem"],
      " sem_ok:", common_all - tot["sem"],
      f" 一致率={100*(common_all-tot['sem'])/max(common_all,1):.1f}%")
print("state: match", tot["m"], " form候选(可解释)", tot["fc"],
      " 疑", tot["sp"])
print("unmapped:", unmapped)

json.dump(rows, open(TWIN / "analyze_rows.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
