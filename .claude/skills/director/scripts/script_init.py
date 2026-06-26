#!/usr/bin/env python3
"""
script_init.py — fold a flow.json (from analyze_flow.py) into a step-centric
script.json skeleton.

This is the FIRST half of the script's life: a purely mechanical transform.
It does NOT make business judgments. It:

  * creates one step entry per record (KEEP -> status "kept", DROP -> "dropped"),
  * seeds bindings.extracts from lineage edges produced by each step,
  * seeds bindings.assigns from lineage edges consumed by each step,
  * lifts missing_producers into top-level open_gaps (with catalog candidates),
  * assigns a dense execution `order` over kept steps in capture order.

The model then edits the resulting script.json during scripting (flip
keep/drop, collapse dups, fix roles) and gap-resolution (resolve each gap).

Usage:
    python script_init.py CAPTURE.flow.json \
        --capture CAPTURE.ndjson \
        --golden golden_e2e.json \
        [--out CAPTURE.script.json]

`--capture` and `--golden` are recorded into the script header for the
assembly step; only `--capture` path is stored, the file is not read here.
See references/script-schema.md for the exact shape produced.
"""
import argparse
import json
import sys
from collections import defaultdict


def role_from_reason(reason: str) -> str:
    """Derive a coarse role label from analyze_flow's reason text."""
    if "mutation verb" in reason:
        return "mutation"
    if "produces downstream id" in reason:
        return "context_fetch"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("flow", help="flow.json from analyze_flow.py")
    ap.add_argument("--capture", required=True,
                    help="the .ndjson the flow was derived from (recorded for assembly)")
    ap.add_argument("--golden", required=True,
                    help="golden e2e.json (recorded for config fallback at assembly)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    flow = json.load(open(args.flow, encoding="utf-8"))
    records = flow.get("records", [])
    lineage = flow.get("lineage", [])
    missing = flow.get("missing_producers", [])

    # Index lineage edges by producer and consumer idx.
    produces = defaultdict(list)   # idx -> [edge, ...]
    consumes = defaultdict(list)   # idx -> [edge, ...]
    for e in lineage:
        produces[e["producer_idx"]].append(e)
        consumes[e["consumer_idx"]].append(e)

    # Choose ONE variable name per produced value. The field name is the natural
    # semantic name; if the same field is produced by multiple steps the model
    # must disambiguate later (single-write rule) — we flag nothing here, just
    # seed the obvious name.
    def var_for(edge):
        return edge["field"]

    steps = []
    order = 0
    for r in records:
        idx = r["idx"]
        decision = r["decision"]
        status = "kept" if decision == "KEEP" else "dropped"

        extracts, assigns = [], []
        if status == "kept":
            # extracts: this step is the producer of these edges
            seen_vars = set()
            for e in produces.get(idx, []):
                v = var_for(e)
                if v in seen_vars:
                    continue  # same field produced twice in one response -> first path
                seen_vars.add(v)
                extracts.append({
                    "var": v,
                    "expression": e["producer_path"],
                    "scope": "scenario",
                })
            # assigns: this step consumes these edges
            seen_targets = set()
            for e in consumes.get(idx, []):
                tgt = e["consumer_path"]
                if tgt in seen_targets:
                    continue
                seen_targets.add(tgt)
                assigns.append({
                    "var": var_for(e),
                    "target": tgt,
                })

        step = {
            "idx": idx,
            "order": order if status == "kept" else None,
            "status": status,
            "role": role_from_reason(r.get("reason", "")) if status == "kept" else None,
            "method": r.get("method"),
            "path": r.get("path"),
            "decision_reason": r.get("reason", ""),
            "collapsed_into": None,
            "bindings": {"extracts": extracts, "assigns": assigns},
        }
        # carry analyze_flow's dup hint through as a starting suggestion, but do
        # NOT auto-collapse — that is the model's judgment.
        if r.get("dup_of") is not None:
            step["decision_reason"] += f" [dup_of {r['dup_of']} — review for collapse]"
        steps.append(step)
        if status == "kept":
            order += 1

    open_gaps = []
    for m in missing:
        open_gaps.append({
            "field": m["field"],
            "value": m["value"],
            "consumer_idx": m["consumer_idx"],
            "status": "unresolved",
            "candidates": m.get("suggestions", []),
            "resolution": None,
        })

    script = {
        "kind": "script",
        "source_capture": args.capture,
        "business_host": flow.get("summary", {}).get("business_host", ""),
        "golden_ref": args.golden,
        "steps": steps,
        "open_gaps": open_gaps,
    }

    out_path = args.out or (args.flow.rsplit(".flow.json", 1)[0] + ".script.json")
    if out_path == args.flow:
        out_path = args.flow.rsplit(".", 1)[0] + ".script.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    kept = sum(1 for s in steps if s["status"] == "kept")
    print(f"[ok] wrote {out_path}")
    print(f"[summary] {kept} kept / {len(steps) - kept} dropped steps, "
          f"{len(open_gaps)} open gap(s)")
    if open_gaps:
        print("[next] resolve each open_gap (lookup / static), then run script_lint.py")


if __name__ == "__main__":
    main()
