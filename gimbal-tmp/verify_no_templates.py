import json, re

s = json.load(open("D:/Gimbal/Gimbal/gimbal-tmp/fin1_scenario.json", encoding="utf-8"))
patt = re.compile(r'\$\{([^}]+)\}')
non_bl_no = []
bl_count = 0
for i, st in enumerate(s["steps"]):
    body_str = json.dumps(st["request"]["body"], ensure_ascii=False)
    for m in patt.findall(body_str):
        if m == "var.bl_no":
            bl_count += 1
        else:
            non_bl_no.append((i, m))

if non_bl_no:
    print("NON-BL_NO templates still in bodies:")
    for x in non_bl_no:
        print("  step %d: $%s" % (x[0], "{" + x[1] + "}"))
else:
    print("OK: no non-bl_no template references in any request body.")
print()
print("bl_no template occurrences:", bl_count)

# Verify each step has assign for each dynamic field it depends on
print()
print("Self-check on assign coverage:")
ext_vars = set()
for i, st in enumerate(s["steps"]):
    for sg in st["strategy"]:
        if sg["kind"] == "extract":
            ext_vars.add(sg["target"])

for i, st in enumerate(s["steps"]):
    for sg in st["strategy"]:
        if sg["kind"] == "assign":
            src = sg["source"]
            if src.startswith("$."):
                var = src[2:]
                if var not in ext_vars:
                    print("  step %d: assign source $.%s has NO producer!" % (i, var))