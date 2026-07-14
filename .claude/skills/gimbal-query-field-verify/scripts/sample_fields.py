#!/usr/bin/env python3
"""sample_fields.py — one-pass sampler: page through the baseline query and,
for every TESTABLE field simultaneously, collect up to N mutually-distinct
non-empty sample values, each anchored to its order_id/id.

Usage:
  python sample_fields.py --mapping mapping.json \
      --url "…baseline URL…" --header "Cookie: PHPSESSID=…" \
      [--max-rows 100] [--per-field 5] --out samples.json --md samples.md
"""
import argparse, datetime, json, re, sys, urllib.request
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

EMPTY = ("", None)


def canon(v):
    """Shared canonicalizer (assertion-side twin lives in build_scenario)."""
    if v in EMPTY:
        return None
    s = str(v).strip()
    if not s:
        return None
    m = re.fullmatch(r"[$￥¥]\s*([\d,]+(?:\.\d+)?)", s)
    if m:
        return m.group(1).replace(",", "")
    return s


def fetch(url, headers):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def set_qs(url, **kw):
    sp = urlsplit(url)
    q = parse_qsl(sp.query, keep_blank_values=True)
    q = [(k, str(kw.pop(k)) if k in kw else v) for k, v in q]
    q += [(k, str(v)) for k, v in kw.items()]
    return urlunsplit(sp._replace(query=urlencode(q)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mapping", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--header", action="append", default=[],
                    help="'Name: value', repeatable (Cookie, Authorization…)")
    ap.add_argument("--max-rows", type=int, default=100)
    ap.add_argument("--per-field", type=int, default=5)
    ap.add_argument("--page-size", type=int, default=50)
    ap.add_argument("--out", default="samples.json")
    ap.add_argument("--md", default="samples.md")
    args = ap.parse_args()

    mapping = json.load(open(args.mapping, encoding="utf-8"))
    headers = dict(h.split(":", 1) for h in args.header)
    headers = {k.strip(): v.strip() for k, v in headers.items()}
    headers.setdefault("X-Requested-With", "XMLHttpRequest")

    testable = [p for p in mapping["params"] if p["status"] == "TESTABLE"]
    # target response fields per param (FUZZY watches several, samples the 1st)
    watch = {}
    for p in testable:
        fields = p.get("response_fields") or [p["response_field"]]
        watch[p["param"]] = fields

    # inverse value maps for query_code lookup (label → code)
    inv_map = {p["param"]: {v: k for k, v in p.get("value_map", {}).items()}
               for p in testable}

    result = {p["param"]: {"samples": [], "seen": set()} for p in testable}
    scanned, page, baseline_count = 0, 1, None

    while scanned < args.max_rows:
        url = set_qs(args.url, page=page, size=args.page_size)
        resp = fetch(url, headers)
        baseline_count = resp.get("count", baseline_count)
        rows = resp.get("list", [])
        if not rows:
            break
        for row in rows:
            scanned += 1
            anchor_order, anchor_id = row.get("order_id"), row.get("id")
            for p in testable:
                bucket = result[p["param"]]
                if len(bucket["samples"]) >= args.per_field:
                    continue
                raw = row.get(watch[p["param"]][0])
                c = canon(raw)
                if c is None or c in bucket["seen"]:
                    continue
                bucket["seen"].add(c)
                qcode = inv_map[p["param"]].get(str(raw).strip(), c) \
                    if p["category"] == "ENUM" else c
                bucket["samples"].append({
                    "value": raw, "canon": c, "query_code": qcode,
                    "order_id": anchor_order, "row_id": anchor_id})
            if scanned >= args.max_rows:
                break
        if all(len(b["samples"]) >= args.per_field for b in result.values()):
            break
        page += 1

    fields = {}
    for p in testable:
        b = result[p["param"]]
        fields[p["param"]] = (
            {"samples": b["samples"], "distinct_seen": len(b["seen"]),
             "status": "SAMPLED"}
            if b["samples"] else
            {"samples": [], "status": "NO_SAMPLE", "scanned": scanned})

    out = {"scanned_rows": scanned, "baseline_count": baseline_count,
           "scan_ts": datetime.datetime.now().astimezone().isoformat(),
           "fields": fields}
    json.dump(out, open(args.out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    sampled = [k for k, v in fields.items() if v["status"] == "SAMPLED"]
    empty = [k for k, v in fields.items() if v["status"] == "NO_SAMPLE"]
    with open(args.md, "w", encoding="utf-8") as f:
        f.write(f"# samples — scanned {scanned} rows, baseline_count="
                f"{baseline_count}\n\n## SAMPLED ({len(sampled)})\n\n")
        for k in sampled:
            vals = ", ".join(repr(s["canon"]) for s in fields[k]["samples"])
            f.write(f"- `{k}` ×{len(fields[k]['samples'])}: {vals}\n")
        f.write(f"\n## NO_SAMPLE ({len(empty)}) — data gap, "
                f"not an interface verdict\n\n")
        for k in empty:
            f.write(f"- `{k}`\n")
    print(f"sampled={len(sampled)} no_sample={len(empty)} "
          f"scanned={scanned} baseline_count={baseline_count}")
    sys.exit(0)


if __name__ == "__main__":
    main()
