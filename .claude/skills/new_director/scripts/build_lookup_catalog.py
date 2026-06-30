#!/usr/bin/env python3
"""
build_lookup_catalog.py — derive an id-resolution catalog from traffic.

Answers: "I hold id X, which endpoint do I query to get id Y, and where in the
response is Y?"  e.g. bl_no -> /api/order/orderEntrust/orderPage -> order_id at
$.response_body.data.data[0].order_id.

It mines real captures (one or more ndjson files): for each query/read
endpoint it records the id-shaped fields usable as INPUTS (request filters) and
the id-shaped fields produced as OUTPUTS (response JSONPaths). Co-occurrence of
two ids in one endpoint's response means that endpoint *joins* them.

Merge multiple captures to grow the catalog over time. An existing catalog can
be passed with --merge to accumulate knowledge across runs (the GIMBAL
knowledge-graph idea, in miniature).

Usage:
    python build_lookup_catalog.py CAP1.ndjson [CAP2.ndjson ...] \
        [--merge lookup_catalog.json] \
        [--out lookup_catalog.json] [--md lookup_catalog.md]
"""
import argparse, json, re, sys
from collections import defaultdict

ID_KEY_RE = re.compile(r"(_id$|_ids$|_no$|_nos$|_sn$|^id$|token$)", re.IGNORECASE)
# business identifiers that don't end in _id/_no but are still join keys
EXTRA_KEYS = {"bl_no", "keyword", "order_sn", "customer_order_sn"}
SNOWFLAKE_RE = re.compile(r"^\d{12,}$")
ORDERNO_RE = re.compile(r"^[A-Za-z]{2,}\w*\d{4,}$")
READ_SUFFIX = ("detail", "page", "list", "info", "view", "query", "part", "record")


def parse_body(raw):
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return None


def id_like(key, value):
    if value is None or isinstance(value, (bool, list, dict)):
        return False
    sval = str(value).strip()
    if sval in ("", "0", "1", "-1"):
        return False
    k = key.split("[")[0]
    if re.search(r"(_time|_date|_at)$", k, re.I):
        return False
    if k in EXTRA_KEYS:
        return True
    if ID_KEY_RE.search(k) and (SNOWFLAKE_RE.match(sval) or ORDERNO_RE.match(sval)
                                or (sval.isalnum() and len(sval) >= 6)):
        return True
    if SNOWFLAKE_RE.match(sval):
        return True
    return False


def walk(node, prefix="$"):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, f"{prefix}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{prefix}[{i}]")
    else:
        yield prefix, node


def is_read(path):
    seg = path.rstrip("/").rsplit("/", 1)[-1].lower()
    return seg.endswith(READ_SUFFIX)


def field_of(jsonpath):
    return jsonpath.rsplit(".", 1)[-1].split("[")[0]


def norm_path(jp):
    """Collapse array indices so $.data.data[0].order_id -> $.data.data[*].order_id."""
    return re.sub(r"\[\d+\]", "[*]", jp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("captures", nargs="+")
    ap.add_argument("--merge", default=None)
    ap.add_argument("--out", default="lookup_catalog.json")
    ap.add_argument("--md", default="lookup_catalog.md")
    args = ap.parse_args()

    # endpoint -> {"inputs": {field: sample}, "outputs": {field: {path, sample}}, "role": read/mutation}
    cat = defaultdict(lambda: {"inputs": {}, "outputs": {}, "role": "read", "seen": 0})

    if args.merge:
        try:
            prior = json.load(open(args.merge, encoding="utf-8"))
            for ep, info in prior.get("endpoints", {}).items():
                cat[ep]["inputs"].update(info.get("inputs", {}))
                cat[ep]["outputs"].update(info.get("outputs", {}))
                cat[ep]["role"] = info.get("role", "read")
                cat[ep]["seen"] += info.get("seen", 0)
        except FileNotFoundError:
            print(f"[warn] --merge file not found: {args.merge}", file=sys.stderr)

    for path in args.captures:
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            ep = r.get("path", "")
            if not ep:
                continue
            entry = cat[ep]
            entry["seen"] += 1
            entry["role"] = "read" if is_read(ep) else "mutation"
            req = parse_body(r.get("body"))
            resp = parse_body((r.get("response") or {}).get("body"))
            # inputs: id-shaped fields in the (shallow) request — candidate filters
            if isinstance(req, dict):
                for jp, val in walk(req, "$.request_body"):
                    if id_like(field_of(jp), val) and jp.count(".") <= 3:
                        entry["inputs"].setdefault(field_of(jp), str(val))
            # outputs: id-shaped leaves anywhere in the response
            if resp is not None:
                for jp, val in walk(resp, "$.response_body"):
                    if id_like(field_of(jp), val):
                        f = field_of(jp)
                        if f not in entry["outputs"]:
                            entry["outputs"][f] = {"path": norm_path(jp), "sample": str(val)}

    # Build resolution index: target id field -> [ {endpoint, path, inputs} ]
    resolvers = defaultdict(list)
    for ep, info in cat.items():
        if info["role"] != "read":
            continue  # only queries are safe "lookups" (no side effects)
        for out_field, meta in info["outputs"].items():
            resolvers[out_field].append({
                "endpoint": ep,
                "path": meta["path"],
                "inputs": sorted(info["inputs"].keys()),
            })

    report = {
        "endpoints": {ep: {k: info[k] for k in ("role", "seen", "inputs", "outputs")}
                      for ep, info in sorted(cat.items())},
        "resolution_index": {k: v for k, v in sorted(resolvers.items())},
    }
    json.dump(report, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    open(args.md, "w", encoding="utf-8").write(render_md(report))
    print(f"[ok] {args.out}  /  {args.md}")
    print(f"[summary] {len(cat)} endpoints, "
          f"{sum(1 for i in cat.values() if i['role']=='read')} queries, "
          f"{len(resolvers)} resolvable id fields")


def render_md(report):
    out = ["# ID Resolution Catalog\n",
           "Mined from real traffic. Use it when a needed id is **not produced**",
           "by any kept step in a capture: pick a query endpoint whose *outputs*",
           "include the id you need and whose *inputs* you already hold, insert it",
           "as a context-fetch step, then extract the id from the listed path.\n",
           "All response paths use `[*]` for array positions — replace with the",
           "concrete index (usually `[0]`) when wiring the extract.\n"]

    out.append("## Resolution index — \"to get X, query ...\"\n")
    out.append("| target id (X) | query endpoint | extract path | typical inputs |")
    out.append("|---------------|----------------|--------------|----------------|")
    for field, rs in report["resolution_index"].items():
        for r in rs:
            inputs = ", ".join(r["inputs"][:6]) or "—"
            out.append(f"| `{field}` | `{r['endpoint']}` | `{r['path']}` | {inputs} |")

    out.append("\n## Query endpoints — inputs / outputs\n")
    for ep, info in report["endpoints"].items():
        if info["role"] != "read":
            continue
        ins = ", ".join(sorted(info["inputs"].keys())) or "—"
        outs = ", ".join(sorted(info["outputs"].keys())) or "—"
        out.append(f"- `{ep}` (x{info['seen']})")
        out.append(f"    - inputs:  {ins}")
        out.append(f"    - outputs: {outs}")
    out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    main()
