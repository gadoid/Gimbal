import json

# Find all fields where the captured value is "GIMBAL_TEST_1"
records_arr = json.load(open("D:/Gimbal/Gimbal/gimbal-tmp/keep_records.json", encoding="utf-8"))
bl_keys_by_step = {}

def walk(obj, path, results):
    if isinstance(obj, dict):
        for k, v in obj.items():
            walk(v, path + [k], results)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk(v, path + ["[%d]" % i], results)
    else:
        if obj == "GIMBAL_TEST_1":
            results.append(".".join(path))

for r in records_arr:
    results = []
    body = json.loads(r["body"])
    walk(body, [], results)
    if results:
        bl_keys_by_step[r["idx"]] = results

for idx, keys in sorted(bl_keys_by_step.items()):
    print("idx %d: %s" % (idx, keys[:10]))