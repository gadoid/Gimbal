import json, re

s = json.load(open("D:/Gimbal/Gimbal/gimbal-tmp/fin1_scenario.json", encoding="utf-8"))

# Self-check
checks = []

# 1) top-level shape
expected_top = {"kind", "scenarioId", "meta", "config", "resource", "steps"}
checks.append(("top-level shape", set(s.keys()) == expected_top))

# 2) every step shape
ok = True
for i, st in enumerate(s["steps"]):
    if st.get("kind") != "step": ok = False
    if not st.get("api"): ok = False
    if not st.get("request"): ok = False
    if not st.get("strategy"): ok = False
checks.append(("step shape", ok))

# 3) every step has assertion
ok = True
for i, st in enumerate(s["steps"]):
    has_assert = any(sg["kind"] == "assertion" and sg.get("target") == "$.response_status" and sg.get("expected") == 200 for sg in st["strategy"])
    if not has_assert: ok = False
checks.append(("assert_status_200", ok))

# 4) every assign.source has earlier extract.target
ext_first = {}
for i, st in enumerate(s["steps"]):
    for sg in st.get("strategy", []):
        if sg["kind"] == "extract":
            ext_first.setdefault(sg["target"], i)
ok = True
for i, st in enumerate(s["steps"]):
    for sg in st.get("strategy", []):
        if sg["kind"] == "assign":
            src = sg["source"]
            if src.startswith("$."):
                var = src[2:]
                if var not in ext_first:
                    ok = False
                elif ext_first[var] >= i:
                    ok = False
checks.append(("assigns wired (earlier producer)", ok))

# 5) auth templated
ok = True
for i, st in enumerate(s["steps"]):
    auth = st["api"].get("headers", {}).get("Authorization", "")
    if auth and "${auth" not in auth: ok = False
checks.append(("auth templated", ok))

# 6) only var.bl_no templates in bodies
ok = True
patt = re.compile(r'\$\{([^}]+)\}')
for i, st in enumerate(s["steps"]):
    body_str = json.dumps(st["request"]["body"], ensure_ascii=False)
    for m in patt.findall(body_str):
        if m != "var.bl_no":
            ok = False
checks.append(("only var.bl_no template in bodies", ok))

# 7) bodies JSON-serializable
ok = True
for i, st in enumerate(s["steps"]):
    try:
        json.dumps(st["request"]["body"])
    except:
        ok = False
checks.append(("bodies JSON-serializable", ok))

# 8) all extracts expressions resolve against captured responses
def resolve_path(obj, path):
    p = path
    if p.startswith("$.response_body"):
        p = p[len("$.response_body"):]
    if p.startswith("."): p = p[1:]
    if not p: return obj
    tokens = []
    for piece in p.split("."):
        for tok in re.split(r'(\[\d+\])', piece):
            if tok: tokens.append(tok)
    cur = obj
    for tok in tokens:
        if cur is None: return None
        if tok.startswith("["):
            idx = int(tok.strip("[]"))
            if isinstance(cur, list) and idx < len(cur):
                cur = cur[idx]
            else:
                return None
        else:
            if isinstance(cur, dict):
                cur = cur.get(tok)
            else:
                return None
    return cur

records_arr = json.load(open("D:/Gimbal/Gimbal/gimbal-tmp/keep_records.json", encoding="utf-8"))
rec_by_idx = {r["idx"]: r for r in records_arr}
capture_idx = [0,1,2,3,12,14,19,26,28,29,30,32,42,56,57,66,68,70,72,90,91,92,96,151,159,160,161,163,176,187,188,189,195,196]

ok = True
for i, st in enumerate(s["steps"]):
    cap_idx = capture_idx[i]
    r = rec_by_idx[cap_idx]
    resp = json.loads(r["response_body"])
    for sg in st.get("strategy", []):
        if sg["kind"] == "extract":
            v = resolve_path(resp, sg["expression"])
            if v is None: ok = False
checks.append(("all extracts resolve", ok))

# Report
for name, passed in checks:
    print("[%s] %s" % ("OK" if passed else "FAIL", name))