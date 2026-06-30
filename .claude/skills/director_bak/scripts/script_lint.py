#!/usr/bin/env python3
"""
script_lint.py — structural-completeness check for a script.json (lenient mode).

This checks that the script is internally consistent and ready for assembly. It
does NOT judge whether the kept set is the "right" business flow, whether a
decision_reason is good, or whether an extract path is the semantically correct
id — those are model judgments, re-verified at final screening by
validate_scenario.py plus the model's own review.

Checks (see references/script-schema.md):
  1. every kept/collapsed step has an idx; order is a dense 0-based sequence
     over kept steps with no gaps or duplicates;
  2. collapsed steps name a real collapsed_into idx that is itself kept;
  3. every assign.var resolves to an earlier extract.var or a resolved gap
     (no dangling assigns), respecting execution order;
  4. no scenario-scope extract.var is written more than once (single-write rule);
  5. every gap is resolved (status != unresolved) with a well-formed resolution;
     lookup resolutions name an inserted_idx that exists in steps.

Usage:
    python script_lint.py CAPTURE.script.json
Exit 0 = pass, 1 = violations.
"""
import argparse
import json
import sys
from collections import defaultdict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    args = ap.parse_args()

    sc = json.load(open(args.script, encoding="utf-8"))
    steps = sc.get("steps", [])
    gaps = sc.get("open_gaps", [])
    violations = []
    warnings = []

    kept = [s for s in steps if s.get("status") == "kept"]
    by_idx = {s["idx"]: s for s in steps if "idx" in s}

    # ---- 1. idx present + dense order over kept steps ----
    for s in steps:
        if "idx" not in s:
            violations.append(f"[structure] a step is missing 'idx': {s.get('path')}")
    orders = sorted(s.get("order") for s in kept if s.get("order") is not None)
    missing_order = [s["idx"] for s in kept if s.get("order") is None]
    for idx in missing_order:
        violations.append(f"[order] kept step idx={idx} has no 'order'.")
    expected = list(range(len(kept)))
    if [o for o in orders] != expected:
        violations.append(f"[order] kept-step order is not a dense 0..{len(kept)-1} "
                          f"sequence; got {orders}.")

    # ---- 2. collapsed steps reference a real kept idx ----
    for s in steps:
        if s.get("status") == "collapsed":
            tgt = s.get("collapsed_into")
            if tgt is None or tgt not in by_idx:
                violations.append(f"[collapse] step idx={s.get('idx')} collapsed_into "
                                  f"{tgt} which is not a known step.")
            elif by_idx[tgt].get("status") != "kept":
                violations.append(f"[collapse] step idx={s.get('idx')} collapsed_into "
                                  f"{tgt} which is not 'kept'.")

    # ---- 4. single-write rule on scenario-scope extracts ----
    scenario_writes = defaultdict(list)
    for s in kept:
        for ex in s.get("bindings", {}).get("extracts", []):
            if ex.get("scope", "scenario") == "scenario":
                scenario_writes[ex["var"]].append(s["idx"])
    for var, idxs in scenario_writes.items():
        if len(idxs) > 1:
            violations.append(f"[single-write] scenario var '{var}' is extracted "
                              f"{len(idxs)}x (steps {idxs}); use scope:step or a "
                              f"distinct name ('{var}_pen').")

    # ---- 5. gaps resolved ----
    static_vars = set()           # gap-provided static var names
    lookup_provided_vars = set()  # vars an inserted lookup step extracts
    for g in gaps:
        st = g.get("status", "unresolved")
        res = g.get("resolution")
        if st == "unresolved" or res is None:
            violations.append(f"[gap] field '{g.get('field')}' (needed by "
                              f"idx={g.get('consumer_idx')}) is unresolved.")
            continue
        kind = res.get("kind")
        if kind == "static":
            if not res.get("var"):
                violations.append(f"[gap] static resolution for '{g.get('field')}' "
                                  f"has no 'var'.")
            else:
                static_vars.add(res["var"])
        elif kind == "lookup":
            ins = res.get("inserted_idx")
            if ins not in by_idx:
                violations.append(f"[gap] lookup resolution for '{g.get('field')}' "
                                  f"names inserted_idx {ins} not present in steps.")
            else:
                for ex in by_idx[ins].get("bindings", {}).get("extracts", []):
                    lookup_provided_vars.add(ex["var"])
        else:
            violations.append(f"[gap] resolution for '{g.get('field')}' has unknown "
                              f"kind '{kind}'.")

    # ---- 3. no dangling assigns (respecting order) ----
    # An assign.var must be produced by an extract on an EARLIER-ordered step,
    # or be a var supplied by a resolved lookup gap, or be a static var.
    ordered = sorted(kept, key=lambda s: s.get("order", 0))
    produced_so_far = set(static_vars) | set(lookup_provided_vars)
    for s in ordered:
        b = s.get("bindings", {})
        for asg in b.get("assigns", []):
            v = asg.get("var")
            if v not in produced_so_far:
                violations.append(f"[wiring] step idx={s['idx']} assign var '{v}' "
                                  f"has no earlier extract / resolved gap "
                                  f"(dangling reference).")
        for ex in b.get("extracts", []):
            produced_so_far.add(ex["var"])

    # ---- report ----
    print(f"script: {args.script}")
    print(f"steps: {len(steps)} ({len(kept)} kept)  open_gaps: {len(gaps)}")
    if violations:
        print(f"\n❌ {len(violations)} VIOLATION(S):")
        for v in violations:
            print("  -", v)
    if warnings:
        print(f"\n⚠️  {len(warnings)} warning(s):")
        for w in warnings:
            print("  -", w)
    if not violations and not warnings:
        print("\n✅ clean — script is structurally complete, ready for assembly.")
    elif not violations:
        print("\n✅ no hard violations (warnings only).")
    sys.exit(1 if violations else 0)


if __name__ == "__main__":
    main()
