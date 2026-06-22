import json
from collections import Counter

s = json.load(open("D:/Gimbal/Gimbal/gimbal-tmp/fin1_scenario.json", encoding="utf-8"))

# Audit extract targets
extracts = []
for i, st in enumerate(s["steps"]):
    for sg in st.get("strategy", []):
        if sg["kind"] == "extract":
            extracts.append((i, sg["name"], sg["target"]))

c = Counter([e[2] for e in extracts])
dups = [(k, v) for k, v in c.most_common() if v > 1]
print("Duplicate extract.target counts:", dups)

print()
print("All unique extract.targets:")
for tgt in sorted(set([e[2] for e in extracts])):
    print(f"  {tgt}")

# Check that each assign.source has a producer
ext_targets = set([e[2] for e in extracts])
missing = []
for i, st in enumerate(s["steps"]):
    for sg in st.get("strategy", []):
        if sg["kind"] == "assign":
            src = sg["source"]
            if src.startswith("$."):
                var = src[2:]
                if var not in ext_targets:
                    missing.append((i, var))
print()
print("Missing producers for assign sources:", missing)

# Check for any duplicate assign targets within the same step
print()
print("Duplicate assign targets within same step:")
for i, st in enumerate(s["steps"]):
    targets = [sg["target"] for sg in st["strategy"] if sg["kind"] == "assign"]
    dups_in_step = set([t for t in targets if targets.count(t) > 1])
    if dups_in_step:
        print(f"  step {i}: {dups_in_step}")