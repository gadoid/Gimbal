#!/usr/bin/env python3
"""
script_gap_resolve.py — atomically resolve an open_gap in script.json
(Director, 剪辑链 阶段2 的配套工具).

In this design an open_gap means exactly ONE thing: a value this capture's
requests need but no earlier response in this capture produced it. (The
"maybe it's actually an external/static input" branch no longer exists here
— that case is filtered out before reaching script.json by analyze_flow.py's
external-value matching against the scaffold.) So there is exactly one way
to resolve a gap: insert a context-fetch step that queries some endpoint
(usually picked from the gap's `candidates`, mined from lookup_catalog.json)
and wire its response into the consumer via extract/assign.

Doing this by hand requires touching FOUR places at once — add a synthetic
step, give it an extract, add the matching assign on the consumer step,
mark the gap resolved — and forgetting any one of them is exactly the bug
class this tool exists to prevent. This script performs all four atomically.
The model's only judgment call is picking the candidate (or supplying a
custom endpoint) and naming the variable; everything else is mechanical.

Usage:
    # inspect gaps first
    python script_gap_resolve.py script.json --list

    # resolve gap 0 by inserting a context-fetch step
    python script_gap_resolve.py script.json --gap-index 0 \\
        --var order_id --candidate-index 0 \\
        --method POST --path /api/order/orderEntrust/orderPage \\
        --headers '{"Authorization": "${auth.codfish.token}"}' \\
        --request-body '{"bl_no": "${var.bl_no}"}' \\
        --extract-expression '$.response_body.data.data[0].order_id'
"""
import argparse
import json


def find_step(script, idx):
    for s in script["steps"]:
        if s["idx"] == idx:
            return s
    raise SystemExit(f"[error] no step with idx={idx} in script.json")


def next_synthetic_idx(script):
    existing = [s["idx"] for s in script["steps"] if s["idx"] >= 100]
    return (max(existing) + 1) if existing else 100


def list_gaps(script):
    gaps = script.get("open_gaps", [])
    if not gaps:
        print("[ok] no open_gaps.")
        return
    for i, g in enumerate(gaps):
        occ = g.get("occurrences", [])
        occ_note = f" ({len(occ)} occurrences)" if len(occ) > 1 else ""
        print(f"[{i}] field={g['field']} value={g['value']!r} "
              f"consumer_idx={g['consumer_idx']} consumer_path={g['consumer_path']}{occ_note} "
              f"status={g['status']}")
        if g.get("candidates"):
            for ci, c in enumerate(g["candidates"]):
                print(f"      candidate[{ci}]: {c['endpoint']} -> {c['path']} "
                      f"(inputs: {', '.join(c.get('inputs', []))})")
        else:
            print("      (no catalog candidates — supply --method/--path manually)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script_json")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--gap-index", type=int)
    ap.add_argument("--var", help="variable name to extract/assign")
    ap.add_argument("--candidate-index", type=int,
                    help="use this gap candidate's endpoint/path as the lookup call")
    ap.add_argument("--method", default="POST")
    ap.add_argument("--path")
    ap.add_argument("--headers", default='{"Authorization": "PENDING_TOKEN"}',
                    help="plain literal placeholder, NOT ${...} syntax — the 发版链 "
                         "unconditionally overwrites every step's Authorization header "
                         "regardless of its captured/placeholder value, so this never "
                         "needs to be templated here")
    ap.add_argument("--request-body", default="{}",
                    help="use the REAL literal test values here (e.g. the actual bl_no "
                         "string), not ${var.x} templates — value-matching against the "
                         "scaffold happens uniformly for every step at assemble time")
    ap.add_argument("--extract-expression")
    ap.add_argument("--out", default=None, help="default: overwrite in place")
    args = ap.parse_args()

    script = json.load(open(args.script_json, encoding="utf-8"))

    if args.list or args.gap_index is None:
        list_gaps(script)
        return

    gaps = script.get("open_gaps", [])
    if not (0 <= args.gap_index < len(gaps)):
        raise SystemExit(f"[error] gap-index {args.gap_index} out of range (0..{len(gaps)-1})")
    gap = gaps[args.gap_index]
    if gap["status"] == "resolved":
        raise SystemExit(f"[error] gap {args.gap_index} is already resolved")

    method = args.method
    path = args.path
    extract_expr = args.extract_expression
    if args.candidate_index is not None:
        cand = gap["candidates"][args.candidate_index]
        # catalog naming: "endpoint" = request path to call, "path" = the
        # response JSONPath that yields the value (i.e. the extract expression).
        path = path or cand["endpoint"]
        extract_expr = extract_expr or cand.get("path")
        method = method or "POST"
    if not path:
        raise SystemExit("[error] no --path and no --candidate-index given; cannot build the lookup call")
    if not extract_expr:
        raise SystemExit("[error] no --extract-expression; the catalog candidate didn't carry one either, supply it")
    if not args.var:
        raise SystemExit("[error] --var is required")

    try:
        headers = json.loads(args.headers)
        request_body = json.loads(args.request_body)
    except json.JSONDecodeError as e:
        raise SystemExit(f"[error] --headers/--request-body must be valid JSON: {e}")

    synth_idx = next_synthetic_idx(script)
    synth_step = {
        "idx": synth_idx,
        "path": path,
        "method": method,
        "decision": "keep",
        "reason": f"synthetic context-fetch inserted to resolve gap[{args.gap_index}] ({gap['field']})",
        "dup_of": None,
        "synthetic": True,
        "headers": headers,
        "request_body": request_body,
        "bindings": {
            "extracts": [{"var": args.var, "expression": extract_expr,
                          "scope": "scenario", "source_edge": False}],
            "assigns": [],
        },
        "notes": "",
    }

    occurrences = gap.get("occurrences") or [
        {"consumer_idx": gap["consumer_idx"], "field": gap["field"], "consumer_path": gap["consumer_path"]}
    ]
    assigned_at = []
    for occ in occurrences:
        target_step = find_step(script, occ["consumer_idx"])
        target_step.setdefault("bindings", {}).setdefault("assigns", [])
        target_step["bindings"]["assigns"].append({
            "var": args.var, "target": occ["consumer_path"], "source_edge": False,
        })
        assigned_at.append(f"idx={occ['consumer_idx']} {occ['consumer_path']}")

    # insert the synthetic step immediately before the EARLIEST consumer it
    # feeds — if the same gap value is needed at several occurrences across
    # different steps, every one of them must run after the lookup.
    earliest_consumer_idx = min(occ["consumer_idx"] for occ in occurrences)
    insert_at = next(i for i, s in enumerate(script["steps"]) if s["idx"] == earliest_consumer_idx)
    script["steps"].insert(insert_at, synth_step)

    gap["status"] = "resolved"
    gap["resolution"] = {"kind": "lookup", "var": args.var, "synthetic_idx": synth_idx,
                         "endpoint": f"{method} {path}", "extract_expression": extract_expr}

    out_path = args.out or args.script_json
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)
    print(f"[ok] gap[{args.gap_index}] resolved: inserted synthetic step idx={synth_idx} "
          f"({method} {path}), wired var '{args.var}' to {len(assigned_at)} occurrence(s): "
          + "; ".join(assigned_at) + f". Wrote {out_path}.")


if __name__ == "__main__":
    main()
