#!/usr/bin/env python3
"""
analyze_flow.py — GIMBAL traffic preprocessor.

Reads a Prism/mitmproxy ndjson capture and produces a deterministic
"scaffold" report that an LLM uses to assemble a GIMBAL scenario:

  1. path frequency table (helps spot UI-noise reads)
  2. value-lineage graph: which RESPONSE field produced an id that is later
     consumed by a REQUEST field  -> these become extract/assign pairs
  3. signal / noise classification per record, with a reason

The script never invents JSONPaths: every path it emits is verified by
walking the actual parsed request/response body.

Usage:
    python analyze_flow.py CAPTURE.ndjson [--business-host HOST]
                                          [--out report.json]
                                          [--md report.md]

If --business-host is omitted, the most frequent host is treated as the
business host and everything else is flagged as cross-domain noise.
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict

# Path last-segment verbs that indicate a state-changing business call.
MUTATION_VERBS = (
    "add", "edit", "submit", "execute", "confirm", "generate", "book",
    "batch", "writeoff", "apply", "allocation", "toggle", "lock", "del",
    "delete", "update", "create", "save", "cancel", "put",
)

# Field-name patterns that look like identifiers worth tracing.
ID_KEY_RE = re.compile(r"(_id$|_ids$|_no$|_sn$|^id$|token$)", re.IGNORECASE)
# A value that is "id-shaped": long digit run (snowflake) or order-no-like token.
SNOWFLAKE_RE = re.compile(r"^\d{12,}$")
ORDERNO_RE = re.compile(r"^[A-Z]{2,}\d{6,}$")
# Business identifiers/单号 often contain underscores or hyphens (e.g. a
# fixture bl_no like "GIMBAL_TEST_32"). str.isalnum() rejects those outright,
# which silently made such values invisible to the lineage graph AND the
# missing-producer / var-candidate detection below. Use an explicit charset.
ID_CHARSET_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def load_records(path):
    recs = []
    with open(path, encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[warn] line {ln}: bad json ({e})", file=sys.stderr)
    return recs


def parse_body(raw):
    """Body / response.body arrive as JSON strings; parse best-effort."""
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return None
    return None


def walk(node, prefix="$"):
    """Yield (jsonpath, value) for every scalar leaf in a nested structure."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, f"{prefix}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{prefix}[{i}]")
    else:
        yield prefix, node


def is_id_value(key_path, value):
    """Heuristic: is this leaf an identifier we should trace?"""
    if value is None or isinstance(value, bool):
        return False
    sval = str(value)
    if sval in ("", "0", "1"):  # too ambiguous to anchor a lineage edge
        return False
    last_key = key_path.rsplit(".", 1)[-1].split("[")[0]
    key_hit = bool(ID_KEY_RE.search(last_key))
    shape_hit = bool(SNOWFLAKE_RE.match(sval) or ORDERNO_RE.match(sval))
    # Require id-shaped value; key-name match alone (e.g. customer_id=16) is
    # too collision-prone for short values.
    if shape_hit:
        return True
    if key_hit and len(sval) >= 6 and ID_CHARSET_RE.match(sval):
        return True
    return False


def verb_of(path):
    seg = path.rstrip("/").rsplit("/", 1)[-1].lower()
    return seg


# A path whose tail ENDS in one of these is a read, even if it embeds a verb
# (e.g. realAmountEditDetail contains "edit" but is a detail read).
READ_SUFFIX = ("detail", "page", "list", "info", "view", "query", "part", "record")


def is_mutation(path):
    seg = verb_of(path)
    if seg.endswith(READ_SUFFIX):
        return False
    return any(v in seg for v in MUTATION_VERBS)


def field_of_path(jp):
    return jp.rsplit(".", 1)[-1].split("[")[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ndjson")
    ap.add_argument("--business-host", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--md", default=None)
    ap.add_argument("--catalog", default=None,
                    help="lookup_catalog.json; suggests a query endpoint for any "
                         "id consumed in a request but never produced in this capture")
    args = ap.parse_args()

    recs = load_records(args.ndjson)
    n = len(recs)

    host_counts = Counter(r.get("host", "") for r in recs)
    business_host = args.business_host or (host_counts.most_common(1)[0][0] if host_counts else "")

    # Pre-parse bodies.
    parsed = []
    for r in recs:
        parsed.append({
            "idx": len(parsed),
            "ts": r.get("ts"),
            "method": r.get("method"),
            "host": r.get("host"),
            "path": r.get("path"),
            "req": parse_body(r.get("body")),
            "resp": parse_body((r.get("response") or {}).get("body")),
            "status": (r.get("response") or {}).get("status"),
        })

    # Build producer index: value -> earliest (idx, jsonpath) seen in a RESPONSE.
    # Use response_body root so emitted paths are GIMBAL-ready ($.response_body...).
    producers = {}  # value(str) -> (idx, jsonpath)
    for p in parsed:
        if p["resp"] is None:
            continue
        for jp, val in walk(p["resp"], "$.response_body"):
            if not is_id_value(jp, val):
                continue
            sval = str(val)
            if sval not in producers:  # earliest wins
                producers[sval] = (p["idx"], jp)

    # For each request, find id values whose source is an EARLIER response.
    # -> lineage edges (extract on producer, assign on consumer).
    lineage = []  # dicts
    consumer_needs = defaultdict(list)
    producer_emits = defaultdict(list)
    for p in parsed:
        if p["req"] is None:
            continue
        seen_vals = set()
        for jp, val in walk(p["req"], "$.request_body"):
            if not is_id_value(jp, val):
                continue
            sval = str(val)
            if sval in seen_vals:
                continue
            seen_vals.add(sval)
            src = producers.get(sval)
            if src and src[0] < p["idx"]:
                edge = {
                    "value": sval,
                    "producer_idx": src[0],
                    "producer_path": src[1],          # $.response_body...
                    "consumer_idx": p["idx"],
                    "consumer_path": jp,              # $.request_body...
                    "field": jp.rsplit(".", 1)[-1].split("[")[0],
                }
                lineage.append(edge)
                consumer_needs[p["idx"]].append(edge)
                producer_emits[src[0]].append(edge)

    # Classify each record.
    path_freq = Counter(p["path"] for p in parsed)
    rows = []
    for p in parsed:
        reasons = []
        keep = False
        if p["host"] != business_host:
            rows.append({**_slim(p), "decision": "DROP", "reason": "cross-domain host (non-business)"})
            continue
        if is_mutation(p["path"]):
            keep = True
            reasons.append("mutation verb")
        if producer_emits.get(p["idx"]):
            keep = True
            fields = sorted({e["field"] for e in producer_emits[p["idx"]]})
            reasons.append("produces downstream id(s): " + ", ".join(fields))
        if not keep:
            reasons.append(f"pure read, no downstream dependency (path x{path_freq[p['path']]})")
        rows.append({
            **_slim(p),
            "decision": "KEEP" if keep else "DROP",
            "reason": "; ".join(reasons),
        })

    # Flag duplicate KEEP records (same path, identical request body) so the
    # caller can collapse pure repeats. BUT never flag a record that produces a
    # downstream-consumed id: re-queries at different flow stages legitimately
    # extract DIFFERENT ids and must survive.
    dup_seen = {}
    for row in rows:
        if row["decision"] != "KEEP":
            continue
        if producer_emits.get(row["idx"]):          # producer -> not a true dup
            continue
        key = (row["path"], json.dumps(_req_of(parsed, row["idx"]), sort_keys=True, ensure_ascii=False))
        if key in dup_seen:
            row["dup_of"] = dup_seen[key]
        else:
            dup_seen[key] = row["idx"]

    # Soft hints: responses whose data is a non-empty list/object are candidates
    # for *wholesale* extraction (e.g. confirm_list, customer_file_list). The
    # scalar lineage graph cannot see these; the model must wire them by judgment.
    bulk_candidates = []
    for p in parsed:
        if p["resp"] is None:
            continue
        data = (p["resp"].get("data") if isinstance(p["resp"], dict) else None)
        if isinstance(data, list) and data:
            bulk_candidates.append({"idx": p["idx"], "path": p["path"],
                                    "expression": "$.response_body.data",
                                    "shape": f"list[{len(data)}]"})
        elif isinstance(data, dict) and any(isinstance(v, list) and v for v in data.values()):
            keys = [k for k, v in data.items() if isinstance(v, list) and v]
            bulk_candidates.append({"idx": p["idx"], "path": p["path"],
                                    "expression": "$.response_body.data",
                                    "shape": "dict with list fields: " + ", ".join(keys[:5])})

    # Missing-producer detection: ids that a request consumes but that no earlier
    # response in THIS capture produced. If a catalog is supplied, suggest the
    # query endpoint that could resolve each gap (insert as a context-fetch step).
    # We track EVERY occurrence (not just the first) so we can tell "consumed
    # once, probably a real business id that needs a context-fetch" apart from
    # "consumed repeatedly across many steps with no producer, probably a
    # static fixture value that belongs in config.vars". Previously only the
    # first occurrence was kept, so the report had no signal to distinguish
    # the two cases and a value like a recurring bl_no never got flagged as a
    # var candidate.
    consumed_vals = defaultdict(list)  # value -> [(idx, field), ...]
    for p in parsed:
        if p["req"] is None:
            continue
        for jp, val in walk(p["req"], "$.request_body"):
            if is_id_value(jp, val):
                consumed_vals[str(val)].append((p["idx"], field_of_path(jp)))

    missing = []
    catalog = None
    if args.catalog:
        try:
            catalog = json.load(open(args.catalog, encoding="utf-8"))
        except Exception as e:
            print(f"[warn] could not read catalog: {e}", file=sys.stderr)
    for val, occ in consumed_vals.items():
        if val in producers:
            continue  # produced somewhere in capture
        distinct_idxs = sorted({idx for idx, _ in occ})
        first_idx, first_field = occ[0]
        entry = {
            "value": val,
            "consumer_idx": first_idx,
            "field": first_field,
            "occurrence_count": len(distinct_idxs),
            "occurrence_steps": distinct_idxs,
            "suggestions": [],
        }
        if catalog:
            for r in catalog.get("resolution_index", {}).get(first_field, []):
                entry["suggestions"].append({"endpoint": r["endpoint"],
                                             "path": r["path"], "inputs": r["inputs"]})
        # Heuristic: repeated across >=2 steps with no catalog-resolvable
        # endpoint and no producer in this capture -> almost certainly a
        # pre-known test fixture (bl_no, a selected master-data id, a fixed
        # date/time window), not a business-process id we forgot to capture.
        # Surface this explicitly instead of leaving it to be inferred.
        entry["static_constant_candidate"] = (
            len(distinct_idxs) >= 2 and not entry["suggestions"]
        )
        missing.append(entry)
    missing.sort(key=lambda m: (-m["occurrence_count"]))

    report = {
        "summary": {
            "total_records": n,
            "business_host": business_host,
            "unique_paths": len(path_freq),
            "kept": sum(1 for r in rows if r["decision"] == "KEEP"),
            "dropped": sum(1 for r in rows if r["decision"] == "DROP"),
            "lineage_edges": len(lineage),
            "var_candidates": sum(1 for m in missing if m["static_constant_candidate"]),
            "context_fetch_candidates": sum(1 for m in missing if not m["static_constant_candidate"]),
        },
        "host_counts": dict(host_counts),
        "path_frequency": path_freq.most_common(),
        "records": rows,
        "lineage": lineage,
        "bulk_extract_candidates": bulk_candidates,
        "missing_producers": missing,
    }

    out_path = args.out or (args.ndjson.rsplit(".", 1)[0] + ".flow.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"[ok] wrote {out_path}")

    md_path = args.md or (args.ndjson.rsplit(".", 1)[0] + ".flow.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_md(report))
    print(f"[ok] wrote {md_path}")

    s = report["summary"]
    print(f"[summary] {s['kept']} keep / {s['dropped']} drop / "
          f"{s['lineage_edges']} lineage edges / "
          f"{s['var_candidates']} var candidates / "
          f"{s['context_fetch_candidates']} context-fetch candidates "
          f"over {s['total_records']} records")


def _slim(p):
    return {"idx": p["idx"], "path": p["path"], "method": p["method"], "status": p["status"]}


def _req_of(parsed, idx):
    return parsed[idx]["req"]


def render_md(report):
    s = report["summary"]
    out = []
    out.append("# Flow analysis\n")
    out.append(f"- records: **{s['total_records']}**  business host: `{s['business_host']}`")
    out.append(f"- keep: **{s['kept']}**  drop: **{s['dropped']}**  unique paths: {s['unique_paths']}")
    out.append(f"- lineage edges (extract/assign candidates): **{s['lineage_edges']}**")
    out.append(f"- var candidates (repeated, no producer, no catalog match): **{s['var_candidates']}**")
    out.append(f"- context-fetch candidates (no producer, catalog or single-use): **{s['context_fetch_candidates']}**\n")

    out.append("## Kept steps (in order)\n")
    out.append("| idx | path | reason | dup_of |")
    out.append("|----:|------|--------|:------:|")
    for r in report["records"]:
        if r["decision"] == "KEEP":
            out.append(f"| {r['idx']} | `{r['path']}` | {r['reason']} | "
                       f"{r.get('dup_of','')} |")

    out.append("\n## Lineage edges (suggested extract -> assign)\n")
    out.append("| value | producer idx | extract expression | consumer idx | assign target |")
    out.append("|-------|:-----------:|--------------------|:-----------:|---------------|")
    for e in report["lineage"]:
        out.append(f"| `{e['value']}` | {e['producer_idx']} | `{e['producer_path']}` | "
                   f"{e['consumer_idx']} | `{e['consumer_path']}` |")

    miss = report.get("missing_producers", [])
    var_candidates = [m for m in miss if m["static_constant_candidate"]]
    fetch_candidates = [m for m in miss if not m["static_constant_candidate"]]

    if var_candidates:
        out.append("\n## Var candidates — repeated constant, no producer, no catalog match\n")
        out.append("Pre-known test fixtures (bl_no, a fixed date window, a selected "
                   "master-data id). Promote to `config.vars` and reference as "
                   "`${var.x}`; do NOT wire as extract/assign.\n")
        out.append("| value | occurrences | first seen (idx/field) | steps |")
        out.append("|-------|:----------:|------------------------|-------|")
        for m in var_candidates:
            out.append(f"| `{m['value']}` | {m['occurrence_count']} | "
                       f"idx {m['consumer_idx']} / `{m['field']}` | {m['occurrence_steps']} |")

    if fetch_candidates:
        out.append("\n## Missing producers — ids consumed but not produced in capture\n")
        out.append("Either a business-process id the capture didn't generate (insert a "
                   "context-fetch step via a suggested lookup) or a single-use value with "
                   "no catalog match (use judgment).\n")
        out.append("| value | occurrences | needed by idx | field | suggested lookup (endpoint -> path) |")
        out.append("|-------|:----------:|:------------:|-------|--------------------------------------|")
        for m in fetch_candidates:
            sug = m["suggestions"][0] if m["suggestions"] else None
            s = f"`{sug['endpoint']}` -> `{sug['path']}`" if sug else "_(none in catalog)_"
            out.append(f"| `{m['value']}` | {m['occurrence_count']} | {m['consumer_idx']} | "
                       f"`{m['field']}` | {s} |")

    out.append("\n## Dropped paths (noise) — frequency\n")
    dropped_paths = Counter(r["path"] for r in report["records"] if r["decision"] == "DROP")
    out.append("| count | path |")
    out.append("|------:|------|")
    for path, c in dropped_paths.most_common():
        out.append(f"| {c} | `{path}` |")
    out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    main()