#!/usr/bin/env python3
"""
script_init.py — fold flow.json into script.json (Director, 剪辑链 阶段1).

Purely mechanical: no judgment happens here. It just reshapes flow.json's
record list into the script.json scaffold that the model edits directly
during the scripting stage (阶段2).

script.json carries forward EVERYTHING from flow.json without dropping
fields — the historical bug class in this pipeline was always a silent
field drop at this exact seam (bulk_extract_candidates vanishing, gap
consumer_path missing, etc).

Usage:
    python script_init.py flow.json --capture capture.ndjson \\
        --scaffold scaffold.json --out script.json
"""
import argparse
import json


def parse_body(raw):
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return None


def load_capture_index(path):
    """idx -> raw record, for pulling method/headers/body into script.json."""
    out = {}
    if not path:
        return out
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            out[i] = json.loads(line)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("flow_json")
    ap.add_argument("--capture", required=True,
                    help="original ndjson, to pull each kept step's raw method/headers/body")
    ap.add_argument("--scaffold", required=True,
                    help="scenario scaffold (kind/scenarioId/meta/config/resource, steps:[])")
    ap.add_argument("--out", default="script.json")
    args = ap.parse_args()

    flow = json.load(open(args.flow_json, encoding="utf-8"))
    cap = load_capture_index(args.capture)
    scaffold = json.load(open(args.scaffold, encoding="utf-8"))

    records_by_idx = {r["idx"]: r for r in flow["records"]}

    steps = []
    for idx in sorted(records_by_idx):
        row = records_by_idx[idx]
        raw = cap.get(idx, {})
        decision = "keep" if row["decision"] == "KEEP" else "drop"
        # a flagged duplicate defaults to dropped (collapsed); the model may
        # override by setting decision back to "keep" with a reason.
        if row.get("dup_of") is not None:
            decision = "drop"
        steps.append({
            "idx": idx,
            "path": row["path"],
            "method": row["method"],
            "decision": decision,
            "reason": row["reason"],
            "dup_of": row.get("dup_of"),
            "headers": raw.get("headers", {}),
            "request_body": parse_body(raw.get("body")),
            "bindings": {"extracts": [], "assigns": []},
            "notes": "",
        })

    # Pre-fill bindings from the verified lineage graph. This is still
    # mechanical — every edge here was already confirmed against a real
    # response by analyze_flow.py. The model's job in scripting is to REVIEW
    # these (drop spurious ones, name the variables) and to additionally wire
    # bulk_extract_candidates and resolve open_gaps, not to invent new edges
    # from scratch.
    # Keyed by (field, producer_idx) — NOT by value. Two edges from the SAME
    # producer step for the same field always share one name (that's the
    # "multiple consumer JSONPaths need the same extract" case). Two edges
    # from DIFFERENT producer steps get DIFFERENT names even if their values
    # happen to be equal — e.g. a list/detail endpoint re-queried after a
    # mutation, whose id at the same JSONPath coincides with an earlier call.
    # Naming by value alone would silently fold those into one var name and
    # mask that two distinct real-world events produced it (see script-schema
    # single-write rule: repeated captures of "the same kind of value" must
    # get distinct suffixed names, e.g. order_sub_id_pen — that rule is about
    # producer occurrence, not string equality, so key on the occurrence).
    var_seq = {}       # (field, producer_idx) -> var name
    next_suffix = {}

    def var_name_for(field, producer_idx):
        pkey = (field, producer_idx)
        if pkey in var_seq:
            return var_seq[pkey]
        base = field
        n = next_suffix.get(base, 0)
        name = base if n == 0 else f"{base}_{n+1}"
        next_suffix[base] = n + 1
        var_seq[pkey] = name
        return name

    steps_by_idx = {s["idx"]: s for s in steps}
    extract_written = set()  # (producer_idx, var) — one extract per producer per var, even
                              # if multiple consumers downstream need the same value.
    for edge in flow.get("lineage", []):
        name = var_name_for(edge["field"], edge["producer_idx"])
        prod = steps_by_idx[edge["producer_idx"]]
        cons = steps_by_idx[edge["consumer_idx"]]
        key = (edge["producer_idx"], name)
        if key not in extract_written:
            prod["bindings"]["extracts"].append({
                "var": name,
                "expression": edge["producer_path"],
                "scope": "scenario",
                "source_edge": True,
            })
            extract_written.add(key)
        cons["bindings"]["assigns"].append({
            "var": name,
            "target": edge["consumer_path"],
            "source_edge": True,
        })

    open_gaps = []
    for m in flow.get("missing_producers", []):
        open_gaps.append({
            "field": m["field"],
            "value": m["value"],
            "consumer_idx": m["consumer_idx"],
            "consumer_path": m["consumer_path"],
            "occurrences": m.get("occurrences", [{"consumer_idx": m["consumer_idx"],
                                                   "field": m["field"],
                                                   "consumer_path": m["consumer_path"]}]),
            "candidates": m.get("suggestions", []),
            "status": "open",
            "resolution": None,
        })

    script = {
        "kind": "script",
        "source_capture": args.capture,
        "business_host": flow["summary"]["business_host"],
        "scaffold_ref": args.scaffold,
        "steps": steps,
        "open_gaps": open_gaps,
        "bulk_extract_candidates": flow.get("bulk_extract_candidates", []),
        "ignored_external": flow.get("ignored_external", []),
        "positional_extract_risks": flow.get("positional_extract_risks", []),
        "canonicalized_values": flow.get("canonicalized_values", []),
        "value_reuse_suspects": flow.get("value_reuse_suspects", []),
        "unclassified_verbs": flow.get("unclassified_verbs", {}),
        "business_code_warnings": flow.get("business_code_warnings", []),
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    kept = sum(1 for s in steps if s["decision"] == "keep")
    print(f"[ok] wrote {args.out}: {len(steps)} steps ({kept} keep / "
          f"{len(steps)-kept} drop), {len(open_gaps)} open gaps, "
          f"{len(script['bulk_extract_candidates'])} bulk candidates carried forward")


if __name__ == "__main__":
    main()
