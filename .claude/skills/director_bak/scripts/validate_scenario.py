#!/usr/bin/env python3
"""
validate_scenario.py — lint a generated GIMBAL scenario.

Enforces the core GIMBAL execution semantics and structural invariants so the
rules are checked mechanically, not left to the model's discretion.

THE KEY RULE (static vs dynamic):
  * `${var.x}`  -> resolved from config.vars BEFORE execution. Static, known
    test inputs only (bl_no, account, customer/policy master-data ids).
  * scenario context (an `extract` target) -> injected AT RUNTIME via `assign`
    source `$.x`. Business-process ids generated during the flow (order_id,
    order_sub_id, audit_id, ...) MUST flow this way and must NEVER appear in
    config.vars or as `${var.<that id>}`.

A field that is extracted anywhere is dynamic by definition; if it is also a
config.var or used as `${var.<same>}`, that is a violation.

Usage:
    python validate_scenario.py scenario.json [--capture flow.ndjson]
                                              [--process-ids a,b,c]
Exit code 0 = pass, 1 = violations found.
"""
import argparse, json, re, sys

# Ids that are generated/changed by the business process itself -> always
# dynamic. (Master-data ids you merely *select* — customer_id, policy_id,
# supplier_id, carrier_id, country_id — are static inputs and may be vars.)
DEFAULT_PROCESS_IDS = {
    "order_id", "order_no", "order_sub_id", "order_sub_no",
    "order_fee_real_id", "order_container_id",
    "audit_id", "audit_no",
    "receive_account_id", "receive_invoice_id",
    "finance_id", "apply_id", "batch_id", "confirm_id",
}

VAR_RE = re.compile(r"\$\{var\.([A-Za-z0-9_]+)\}")


def parse_body(raw):
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return None


def resolve(obj, expr):
    """Resolve $.response_body.a.b[0].c against a parsed body dict."""
    cur = obj
    body = expr.replace("$.response_body", "", 1)
    for key, ix in re.findall(r"\.([A-Za-z0-9_]+)|\[(\d+)\]", body):
        try:
            cur = cur[key] if key else cur[int(ix)]
        except Exception:
            return False
    return True


def _script_steps_list(sc_script):
    """script.json's step container. The exact key is authoritative in
    references/script-schema.md; tolerate the couple of plausible names so this
    check degrades to a warning instead of crashing if the schema drifts."""
    for key in ("steps", "script_steps", "records"):
        if isinstance(sc_script.get(key), list):
            return sc_script[key]
    return None


def _step_path_method(step):
    """A script step's path/method may be flat (mirrors analyze_flow.py's
    record shape) or nested under 'api' (mirrors the assembled scenario)."""
    api = step.get("api")
    if isinstance(api, dict):
        return api.get("path"), api.get("method")
    return step.get("path"), step.get("method")


def ordered_script_steps(sc_script):
    """Every step the script committed to assembling, in final replay order.

    `order` is the dense index script_init.py assigns to kept steps (and any
    inserted context_fetch / lookup steps get one too so they sort into place).
    A step with no `order` was left dropped / collapsed / an unresolved gap and
    must NOT reach the scenario. Sorting by `order` reproduces exactly the
    sequence script_assemble.py is supposed to walk — so diffing it against the
    scenario's actual step sequence catches anything assembly silently dropped,
    duplicated, or reordered.
    """
    raw = _script_steps_list(sc_script)
    if raw is None:
        return None
    committed = [s for s in raw if s.get("order") is not None]
    committed.sort(key=lambda s: s["order"])
    return committed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario")
    ap.add_argument("--capture", default=None,
                    help="ndjson; if given, verify extract paths resolve against real responses")
    ap.add_argument("--script", default=None,
                    help="script.json from stage (2)/(3); cross-check the assembled "
                         "scenario's step sequence against every step the script "
                         "committed to (non-null 'order') — catches steps assembly "
                         "silently dropped, duplicated, or reordered")
    ap.add_argument("--process-ids", default=None,
                    help="comma-separated extra process-id field names")
    args = ap.parse_args()

    sc = json.load(open(args.scenario, encoding="utf-8"))
    process_ids = set(DEFAULT_PROCESS_IDS)
    if args.process_ids:
        process_ids |= {s.strip() for s in args.process_ids.split(",") if s.strip()}

    steps = sc.get("steps", [])
    config_vars = set((sc.get("config", {}).get("vars", {}) or {}).keys())

    # collect extract targets (dynamic context vars) in order, and assign sources
    extract_targets_seen = set()
    violations, warnings = [], []

    # 1) extracted names must not also be config.vars
    all_extract_targets = set()
    for s in steps:
        for st in s.get("strategy", []):
            if st.get("kind") == "extract":
                t = st.get("target")
                if t and t not in ("request_body", "response_body"):
                    all_extract_targets.add(t)
    both = all_extract_targets & config_vars
    for name in sorted(both):
        violations.append(f"[static/dynamic] '{name}' is both an extract target "
                          f"(dynamic) and a config.var (static) — pick one; process "
                          f"ids must be dynamic only.")

    # 2) no process id declared as a config.var
    for name in sorted(process_ids & config_vars):
        violations.append(f"[static/dynamic] process id '{name}' is declared in "
                          f"config.vars; it must be wired via extract/assign, not ${{var.{name}}}.")

    # 2b) a scenario-scope context field may be written only ONCE. Re-extracting
    # to the same scenario name overwrites the earlier value (downstream assigns
    # may then read the wrong one). Repeated captures must use scope:step
    # (transient, local to that step) or a distinct scenario name (e.g. _pen, _2).
    from collections import defaultdict
    scenario_writes = defaultdict(list)
    for i, s in enumerate(steps):
        for st in s.get("strategy", []):
            if st.get("kind") == "extract" and st.get("scope", "scenario") == "scenario":
                t = st.get("target")
                if t and t not in ("request_body", "response_body"):
                    scenario_writes[t].append(i)
    for t, idxs in scenario_writes.items():
        if len(idxs) > 1:
            violations.append(f"[single-write] scenario field '{t}' is stored "
                              f"{len(idxs)}x (steps {idxs}); a scenario-scope field "
                              f"may be written only once. Use scope:step for transient "
                              f"capture, or distinct names ('{t}_2', '{t}_pen').")

    # walk steps for body-level ${var.x} of process ids / dynamic names, and ordering
    for i, s in enumerate(steps):
        body = parse_body((s.get("request", {}) or {}).get("body"))
        body_str = json.dumps(body, ensure_ascii=False) if body is not None else ""
        used_vars = set(VAR_RE.findall(body_str))
        # 3) ${var.X} must not reference a process id or a name produced by extract
        for v in sorted(used_vars):
            if v in process_ids:
                violations.append(f"[static/dynamic] step {i} uses ${{var.{v}}} for a "
                                  f"business-process id; inject it at runtime via assign "
                                  f"source $.{v} instead.")
            elif v in all_extract_targets:
                violations.append(f"[static/dynamic] step {i} uses ${{var.{v}}} but '{v}' "
                                  f"is produced by an extract; reference it as assign "
                                  f"source $.{v}, not a pre-execution var.")
            elif v not in config_vars:
                warnings.append(f"step {i} uses ${{var.{v}}} but '{v}' is not in config.vars.")

        # gather this step's strategies
        has_status_assert = False
        for st in s.get("strategy", []):
            k = st.get("kind")
            if k == "assertion" and st.get("target") == "$.response_status":
                has_status_assert = True
            if k == "assign":
                src = (st.get("source") or "").lstrip("$.").split(".")[0]
                # 4) no dangling assign: source must be produced by an earlier extract
                if src and src not in extract_targets_seen:
                    violations.append(f"[wiring] step {i} assign source $.{src} has no "
                                      f"earlier extract target (dangling reference).")
            if k == "extract":
                t = st.get("target")
                if t:
                    extract_targets_seen.add(t)
        if not has_status_assert:
            warnings.append(f"step {i} ({_path(s)}) has no $.response_status assertion.")

        # 5) header hygiene
        headers = (s.get("api", {}) or {}).get("headers", {}) or {}
        noisy = {h for h in headers if h.lower() in (
            "host","connection","content-length","cookie","origin","referer",
            "user-agent","accept","accept-encoding","accept-language") or h.lower().startswith(("sec-","sec-ch"))}
        for h in sorted(noisy):
            warnings.append(f"step {i} carries browser/transport header '{h}' — strip it.")
        auth = headers.get("Authorization", "")
        if auth and not auth.startswith("${auth."):
            violations.append(f"[sanitize] step {i} Authorization is not templated "
                              f"(${{auth.<user>.token}}); a raw captured token leaks.")

    # 6) extract paths resolve against real responses (optional)
    if args.capture:
        from collections import defaultdict, deque
        resp_by_path = defaultdict(deque)
        for line in open(args.capture, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            resp_by_path[r.get("path")].append(parse_body((r.get("response") or {}).get("body")))
        seen = defaultdict(int)
        for i, s in enumerate(steps):
            p = _path(s); idx = seen[p]; seen[p] += 1
            bodies = list(resp_by_path.get(p, []))
            body = bodies[idx] if idx < len(bodies) else (bodies[0] if bodies else None)
            for st in s.get("strategy", []):
                if st.get("kind") == "extract" and st.get("expression") not in (None, "$.response_body"):
                    if body is None or not resolve(body, st["expression"]):
                        violations.append(f"[hallucination] step {i} extract path "
                                          f"{st['expression']} does not resolve in the real response.")

    # 7) completeness vs script.json (order-based, catches silent drops in assembly)
    if args.script:
        try:
            sc_script = json.load(open(args.script, encoding="utf-8"))
        except Exception as e:
            print(f"[warn] could not read script: {e}", file=sys.stderr)
            sc_script = None
        script_steps = ordered_script_steps(sc_script) if sc_script is not None else None
        if script_steps is None:
            warnings.append(f"--script given but no recognizable step list found in "
                            f"'{args.script}' (expected key 'steps'/'script_steps'/'records'); "
                            f"skipping completeness check.")
        else:
            if len(script_steps) != len(steps):
                violations.append(
                    f"[completeness] script.json commits {len(script_steps)} ordered "
                    f"step(s) but the assembled scenario has {len(steps)} — assembly "
                    f"dropped or added step(s); see positional diff below.")
            mismatches = []
            n = max(len(script_steps), len(steps))
            for i in range(n):
                sp = script_steps[i] if i < len(script_steps) else None
                scen_step = steps[i] if i < len(steps) else None
                sp_path, sp_method = _step_path_method(sp) if sp else (None, None)
                scen_path = _path(scen_step) if scen_step else None
                scen_method = (scen_step.get("api", {}) or {}).get("method") if scen_step else None
                if sp is None:
                    mismatches.append(f"  pos {i}: scenario has `{scen_method} {scen_path}` "
                                      f"with no corresponding committed script step")
                elif scen_step is None:
                    mismatches.append(f"  pos {i}: script committed `{sp_method} {sp_path}` "
                                      f"(idx {sp.get('idx')}, order {sp.get('order')}) but the "
                                      f"scenario has no step at this position")
                elif (sp_path != scen_path
                      or (sp_method or "").upper() != (scen_method or "").upper()):
                    mismatches.append(f"  pos {i}: script says `{sp_method} {sp_path}` "
                                      f"(idx {sp.get('idx')}, order {sp.get('order')}) but "
                                      f"scenario has `{scen_method} {scen_path}`")
            if mismatches:
                violations.append("[completeness] step sequence diverges from script.json:\n"
                                  + "\n".join(mismatches))

    # report
    print(f"scenario: {args.scenario}")
    script_note = "  script-checked: no (pass --script script.json to enable)"
    if args.script:
        script_note = (f"  script-checked: yes ({len(script_steps)} committed steps)"
                       if script_steps is not None
                       else "  script-checked: no (could not read --script file)")
    print(f"steps: {len(steps)}  config.vars: {len(config_vars)}  "
          f"dynamic extract vars: {len(all_extract_targets)}{script_note}")
    if violations:
        print(f"\n❌ {len(violations)} VIOLATION(S):")
        for v in violations:
            print("  -", v)
    if warnings:
        print(f"\n⚠️  {len(warnings)} warning(s):")
        for w in warnings:
            print("  -", w)
    if not violations and not warnings:
        print("\n✅ clean — no violations or warnings.")
    elif not violations:
        print("\n✅ no hard violations (warnings only).")
    sys.exit(1 if violations else 0)


def _path(step):
    a = step.get("api", {}) or {}
    return a.get("path") if a.get("kind") == "api" else "REF:" + str(a.get("ref"))


if __name__ == "__main__":
    main()