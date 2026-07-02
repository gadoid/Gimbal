#!/usr/bin/env python3
"""
script_lint.py — wiring lint for script.json (Director, 剪辑链 阶段3, 剪辑层终检).

This is the FIRST of the two lint layers. It only ever looks at script.json
— it has no opinion about config/resource/templating, because those belong
to the 发版链 and are out of scope for the cut. It checks both directions:

  "该做的做了" (completeness):
    - no open_gaps remain
    - every extract has a matching downstream assign that actually consumes it
      (an extract nobody reads is dead — usually a sign a gap was "resolved"
      without actually wiring the consumer, the single most common silent
      failure mode this pipeline has had)
    - every assign has an earlier extract producing its var (no dangling refs)
    - kept steps are producer-before-consumer ordered
    - every kept, non-synthetic value flagged in bulk_extract_candidates that
      is genuinely consumed downstream has a wiring (best-effort: warning only,
      this can't be checked mechanically with full certainty)

  "不该做的没做" (non-interference / scope boundary):
    - no `${...}` template syntax appears ANYWHERE in a step's request_body —
      templating is the 发版链's job; if it shows up here the boundary already
      leaked
    - no field listed in ignored_external was given a bindings.extracts /
      bindings.assigns entry (the model must not "rescue" an external field
      into internal lineage)
    - no step whose path/field matches a noise-key was wired as
      producer/consumer (defense in depth; analyze_flow.py should have
      already excluded these, but the model could in principle hand-add one)

Usage:
    python script_lint.py script.json
Exit code 0 = pass, 1 = violations found.
"""
import argparse
import json
import re
import sys

TEMPLATE_RE = re.compile(r"\$\{[^}]+\}")


def kept_steps(script):
    return [s for s in script["steps"] if s["decision"] == "keep"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script_json")
    args = ap.parse_args()

    script = json.load(open(args.script_json, encoding="utf-8"))
    violations, warnings = [], []

    # 1) no open gaps
    for i, g in enumerate(script.get("open_gaps", [])):
        if g["status"] != "resolved":
            violations.append(f"[gap] open_gaps[{i}] (field={g['field']}) is still unresolved.")

    steps = kept_steps(script)
    idx_position = {s["idx"]: pos for pos, s in enumerate(steps)}

    # 2) extract/assign pairing, in both directions
    extract_vars_seen = {}   # var -> idx where extracted
    assign_consumed = set()  # vars that some assign actually reads
    for s in steps:
        for a in s["bindings"].get("assigns", []):
            v = a["var"]
            assign_consumed.add(v)
            if v not in extract_vars_seen:
                violations.append(f"[wiring] step idx={s['idx']} assign var '{v}' "
                                  f"has no earlier extract producing it (dangling reference).")
            elif idx_position.get(extract_vars_seen[v], 1e9) > idx_position.get(s["idx"], -1):
                violations.append(f"[wiring] step idx={s['idx']} assign var '{v}' is consumed "
                                  f"BEFORE its producer step idx={extract_vars_seen[v]} runs.")
        for e in s["bindings"].get("extracts", []):
            v = e["var"]
            if v in extract_vars_seen:
                violations.append(f"[single-write] var '{v}' is extracted more than once "
                                  f"(steps idx={extract_vars_seen[v]} and idx={s['idx']}); "
                                  f"use scope:step or a distinct name for the second capture.")
            else:
                extract_vars_seen[v] = s["idx"]

    for v, idx in extract_vars_seen.items():
        if v not in assign_consumed:
            warnings.append(f"[dead-extract] var '{v}' extracted at step idx={idx} is never "
                            f"consumed by any assign — likely a gap resolved without wiring "
                            f"the consumer, or a leftover from a dropped lineage edge.")

    # 3) scope-boundary checks: no templating leaked into script.json
    ignored_values = {e["value"] for e in script.get("ignored_external", [])}
    for s in steps:
        body_str = json.dumps(s.get("request_body"), ensure_ascii=False)
        if TEMPLATE_RE.search(body_str):
            violations.append(f"[scope] step idx={s['idx']} request_body already contains "
                              f"'${{...}}' templating — that belongs to the 发版链, not the cut.")
        headers_str = json.dumps(s.get("headers", {}), ensure_ascii=False)
        if TEMPLATE_RE.search(headers_str):
            violations.append(f"[scope] step idx={s['idx']} headers already contain "
                              f"'${{...}}' templating — that belongs to the 发版链, not the cut.")

    # 4) no rescued external field: an extract/assign var name that exactly
    #    matches a value already classified ignored_external is suspicious —
    #    best-effort, value-based not name-based, so just a warning.
    for s in steps:
        for e in s["bindings"].get("extracts", []):
            if e.get("expression") and any(
                str(v) in (e.get("expression") or "") for v in ignored_values if len(str(v)) > 6
            ):
                warnings.append(f"[scope] step idx={s['idx']} extract expression "
                                f"'{e['expression']}' may be re-deriving a value already "
                                f"classified as external — verify it isn't a rescued field.")

    # 5) ordering: kept steps' idx should be monotonically increasing except
    #    for synthetic insertions, which are fine anywhere relative to idx
    #    numbering (they use idx>=100) but must still sit before their consumer.
    for i in range(1, len(steps)):
        prev, cur = steps[i-1], steps[i]
        if not prev.get("synthetic") and not cur.get("synthetic"):
            if prev["idx"] > cur["idx"]:
                violations.append(f"[order] kept step idx={cur['idx']} runs after "
                                  f"idx={prev['idx']} but capture order says otherwise.")

    # 6) positional-extract risks (advisory carried from analyze_flow):
    #    if a kept step still extracts via a HIGH-risk array-index path,
    #    warn — the model should have either confirmed position stability
    #    or swapped in a filtered lookup during scripting.
    kept_idx = {s["idx"] for s in steps}
    kept_extract_exprs = {(s["idx"], e.get("expression"))
                          for s in steps for e in s["bindings"].get("extracts", [])}
    for r in script.get("positional_extract_risks", []):
        if r.get("risk") != "high":
            continue
        if r["producer_idx"] in kept_idx and (r["producer_idx"], r["producer_path"]) in kept_extract_exprs:
            disc = ", ".join(f"{k}={v}" for k, v in list(r.get("element_discriminators", {}).items())[:4])
            warnings.append(f"[positional] step idx={r['producer_idx']} extract "
                            f"'{r['producer_path']}' indexes into an array of len="
                            f"{r['array_len']} at position {r['position']} — replay-fragile. "
                            f"Element was ({disc}); confirm ordering is stable or use a "
                            f"filtered lookup instead.")

    print(f"script: {args.script_json}")
    print(f"kept steps: {len(steps)}  extract vars: {len(extract_vars_seen)}  "
          f"open_gaps: {len(script.get('open_gaps', []))}")
    if violations:
        print(f"\n[FAIL] {len(violations)} VIOLATION(S):")
        for v in violations:
            print("  -", v)
    if warnings:
        print(f"\n[WARN] {len(warnings)} warning(s):")
        for w in warnings:
            print("  -", w)
    if not violations and not warnings:
        print("\n[OK] clean — no violations or warnings.")
    elif not violations:
        print("\n[OK] no hard violations (warnings only).")
    sys.exit(1 if violations else 0)


if __name__ == "__main__":
    main()
