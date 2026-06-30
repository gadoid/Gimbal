#!/usr/bin/env python3
"""
analyze_flow.py — GIMBAL traffic preprocessor (Director, 剪辑链 阶段0).

Reads a Prism/mitmproxy ndjson capture and produces a deterministic
"scaffold" report that drives script_init.py / the scripting stage:

  1. path frequency table (helps spot UI-noise reads)
  2. value-lineage graph: which RESPONSE field produced an id that is later
     consumed by a REQUEST field  -> these become extract/assign candidates
  3. signal / noise classification per record, with a reason
  4. external-value matches: request fields whose VALUE matches something
     already declared in the scenario scaffold's config.vars/resource — these
     are NOT internal lineage and must be left untouched (no policy), because
     supplying them is the 发版链 (assemble stage)'s job, not the 剪辑链's.
  5. noise-key exclusions: fields whose NAME (not value) is pure transport/
     audit noise (request_no, trace_id, ...) and must never be treated as a
     producer or consumer regardless of value.

The script never invents JSONPaths: every path it emits is verified by
walking the actual parsed request/response body.

Usage:
    python analyze_flow.py CAPTURE.ndjson \\
        --scaffold scenario_scaffold.json \\
        --catalog references/lookup_catalog.json \\
        --noise-keys references/noise-keys.json \\
        --value-blacklist references/common-values-blacklist.json \\
        [--business-host HOST] [--min-value-len 4] \\
        [--out flow.json] [--md flow.md]

If --business-host is omitted, the most frequent host is treated as the
business host and everything else is flagged as cross-domain noise.

--scaffold is the scenario JSON the steps will eventually be assembled into
(kind/scenarioId/meta/config/resource already decided, steps: []). It is the
ONLY source of "what counts as external input" — there is no dependency on
a golden example scenario for this judgment.
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

DEFAULT_MIN_VALUE_LEN = 4


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


def last_key(jsonpath):
    return jsonpath.rsplit(".", 1)[-1].split("[")[0]


def is_id_value(key_path, value):
    """Heuristic: is this leaf an identifier we should trace?"""
    if value is None or isinstance(value, bool):
        return False
    sval = str(value)
    if sval in ("", "0", "1"):  # too ambiguous to anchor a lineage edge
        return False
    k = last_key(key_path)
    key_hit = bool(ID_KEY_RE.search(k))
    shape_hit = bool(SNOWFLAKE_RE.match(sval) or ORDERNO_RE.match(sval))
    if shape_hit:
        return True
    if key_hit and len(sval) >= 6 and sval.isalnum():
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


def load_json_or_empty(path, key_for_log):
    if not path:
        return None
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception as e:
        print(f"[warn] could not read {key_for_log} ({path}): {e}", file=sys.stderr)
        return None


def build_external_value_set(scaffold, blacklist_values, min_len):
    """Walk config.vars / resource in the scaffold; return the set of
    stringified leaf values that count as 'externally declared input',
    after applying the length floor and the common-values blacklist.
    Also returns value -> declared name(s), for reporting only.
    """
    if not scaffold:
        return set(), {}
    external = set()
    value_to_names = defaultdict(set)
    cfg_vars = (scaffold.get("config", {}) or {}).get("vars", {}) or {}
    for name, v in cfg_vars.items():
        sval = str(v)
        value_to_names[sval].add(f"var.{name}")
        if len(sval) >= min_len and sval not in blacklist_values:
            external.add(sval)
    resource = scaffold.get("resource", {}) or {}
    for jp, v in walk(resource, "$.resource"):
        if v is None or isinstance(v, bool):
            continue
        sval = str(v)
        value_to_names[sval].add(jp)
        if len(sval) >= min_len and sval not in blacklist_values:
            external.add(sval)
    return external, dict(value_to_names)


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
    ap.add_argument("--scaffold", default=None,
                    help="scenario JSON with steps:[] but config/resource decided; "
                         "the source of truth for what counts as external input")
    ap.add_argument("--noise-keys", default=None,
                    help="noise-keys.json; field names excluded from lineage regardless of value")
    ap.add_argument("--value-blacklist", default=None,
                    help="common-values-blacklist.json; values excluded from external-value matching")
    ap.add_argument("--min-value-len", type=int, default=DEFAULT_MIN_VALUE_LEN,
                    help="minimum length for a value to participate in external-value matching")
    args = ap.parse_args()

    recs = load_records(args.ndjson)
    n = len(recs)

    host_counts = Counter(r.get("host", "") for r in recs)
    business_host = args.business_host or (host_counts.most_common(1)[0][0] if host_counts else "")

    scaffold = load_json_or_empty(args.scaffold, "scaffold")
    noise_keys_doc = load_json_or_empty(args.noise_keys, "noise-keys")
    noise_keys = set(noise_keys_doc.get("keys", [])) if noise_keys_doc else set()
    blacklist_doc = load_json_or_empty(args.value_blacklist, "value-blacklist")
    blacklist_values = set(blacklist_doc.get("values", [])) if blacklist_doc else set()

    external_values, value_to_names = build_external_value_set(
        scaffold, blacklist_values, args.min_value_len)

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
    # Noise keys are excluded here too — a noisy field should never anchor a
    # lineage edge even if it happens to look id-shaped.
    producers = {}  # value(str) -> (idx, jsonpath)
    for p in parsed:
        if p["resp"] is None:
            continue
        for jp, val in walk(p["resp"], "$.response_body"):
            if last_key(jp) in noise_keys:
                continue
            if not is_id_value(jp, val):
                continue
            sval = str(val)
            if sval not in producers:  # earliest wins
                producers[sval] = (p["idx"], jp)

    # For each request, classify every scalar leaf into exactly one bucket:
    #   noise        -> key hits noise-keys.json, excluded entirely
    #   external     -> value hits the scaffold's declared external-value set
    #   dynamic_lineage -> id-shaped value with a real earlier-response producer
    #   gap          -> id-shaped value with NO earlier-response producer
    #   literal      -> everything else (not even examined as lineage)
    lineage = []
    consumer_needs = defaultdict(list)
    producer_emits = defaultdict(list)
    ignored_external = []
    consumed_for_gap = defaultdict(list)  # value -> [(consumer_idx, field, consumer_path), ...]

    for p in parsed:
        if p["req"] is None:
            continue
        for jp, val in walk(p["req"], "$.request_body"):
            k = last_key(jp)
            if k in noise_keys:
                continue
            sval = str(val)
            if sval in external_values:
                ignored_external.append({
                    "idx": p["idx"], "path": p["path"], "field": k,
                    "consumer_path": jp, "value": sval,
                    "declared_as": sorted(value_to_names.get(sval, [])),
                })
                continue  # never enters lineage/gap analysis
            if not is_id_value(jp, val):
                continue
            # NOTE: deliberately NOT deduping by value here. The same id-shaped
            # value commonly appears at MULTIPLE distinct JSONPaths within one
            # request (e.g. both $.order_id and $.supplier[0].order_id in the
            # same orderAdd body) and EVERY occurrence needs its own assign —
            # skipping repeats silently left the second occurrence on its
            # original captured literal, which is exactly the bug class that
            # produced a step-9 runtime failure from a step-4 wiring gap (see
            # references/script-schema.md). Duplicate EXTRACTs on the producer
            # side are still deduped, but at the (producer step, var) level in
            # script_init.py, which is the correct place for that dedup.
            src = producers.get(sval)
            if src and src[0] < p["idx"]:
                edge = {
                    "value": sval,
                    "producer_idx": src[0],
                    "producer_path": src[1],          # $.response_body...
                    "consumer_idx": p["idx"],
                    "consumer_path": jp,              # $.request_body...
                    "field": k,
                }
                lineage.append(edge)
                consumer_needs[p["idx"]].append(edge)
                producer_emits[src[0]].append(edge)
            else:
                consumed_for_gap[sval].append((p["idx"], k, jp))

    # Classify each record (keep/drop), unaffected by the value-matching work above.
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

    # Missing-producer (gap) detection — ids consumed but produced nowhere in
    # this capture AND not matched to an external declaration. If a catalog is
    # supplied, suggest the query endpoint that could resolve each gap (insert
    # as a context-fetch step). This is now a PURELY internal concept: an id
    # the business process needs but this capture's traffic doesn't show how
    # to get. It is never "this should be a config.var" — that branch was
    # already removed upstream by the external-value match above.
    missing = []
    catalog = load_json_or_empty(args.catalog, "catalog")
    for val, occurrences in consumed_for_gap.items():
        first_idx, first_field, first_path = occurrences[0]
        entry = {"value": val, "consumer_idx": first_idx, "field": first_field,
                 "consumer_path": first_path,
                 "occurrences": [{"consumer_idx": ci, "field": f, "consumer_path": cp}
                                for ci, f, cp in occurrences],
                 "suggestions": []}
        if catalog:
            for r in catalog.get("resolution_index", {}).get(first_field, []):
                entry["suggestions"].append({"endpoint": r["endpoint"],
                                             "path": r["path"], "inputs": r["inputs"]})
        missing.append(entry)

    report = {
        "summary": {
            "total_records": n,
            "business_host": business_host,
            "unique_paths": len(path_freq),
            "kept": sum(1 for r in rows if r["decision"] == "KEEP"),
            "dropped": sum(1 for r in rows if r["decision"] == "DROP"),
            "lineage_edges": len(lineage),
            "external_matches": len(ignored_external),
            "open_gaps": len(missing),
            "scaffold_used": bool(scaffold),
            "noise_keys_loaded": len(noise_keys),
        },
        "host_counts": dict(host_counts),
        "path_frequency": path_freq.most_common(),
        "records": rows,
        "lineage": lineage,
        "bulk_extract_candidates": bulk_candidates,
        "missing_producers": missing,
        "ignored_external": ignored_external,
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
          f"{s['lineage_edges']} lineage edges / {s['external_matches']} external matches / "
          f"{s['open_gaps']} open gaps over {s['total_records']} records")


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
    out.append(f"- lineage edges: **{s['lineage_edges']}**  "
               f"external matches: **{s['external_matches']}**  "
               f"open gaps: **{s['open_gaps']}**")
    out.append(f"- scaffold used: {s['scaffold_used']}  noise keys loaded: {s['noise_keys_loaded']}\n")

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

    ext = report.get("ignored_external", [])
    if ext:
        out.append("\n## External matches — left untouched, will be filled at assemble stage\n")
        out.append("| idx | field | consumer_path | value | declared as |")
        out.append("|----:|-------|----------------|-------|-------------|")
        for e in ext:
            out.append(f"| {e['idx']} | `{e['field']}` | `{e['consumer_path']}` | `{e['value']}` | "
                       f"{', '.join(e['declared_as'])} |")

    miss = report.get("missing_producers", [])
    if miss:
        out.append("\n## Open gaps — internal id with no producer in this capture\n")
        out.append("Insert a context-fetch step via script_gap_resolve.py.\n")
        out.append("| value | needed by idx | field | suggested lookup (endpoint -> path) |")
        out.append("|-------|:------------:|-------|--------------------------------------|")
        for m in miss:
            sug = m["suggestions"][0] if m["suggestions"] else None
            s2 = f"`{sug['endpoint']}` -> `{sug['path']}`" if sug else "_(none in catalog)_"
            out.append(f"| `{m['value']}` | {m['consumer_idx']} | `{m['field']}` | {s2} |")

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
