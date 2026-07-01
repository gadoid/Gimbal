#!/usr/bin/env python3
"""
script_assemble.py — assemble scenario.json from a wiring-lint-clean
script.json + the scenario scaffold (Director, 发版链).

This is the ONLY place templating happens. It is intentionally symmetric
with analyze_flow.py's external-value matching: both independently scan for
literal values that match something declared in the scaffold's config.vars /
resource, using the SAME values + the SAME blacklist/length-floor rule — but
where analyze_flow.py uses the match to SKIP a field (剪辑链 should not wire
it), this script uses the match to REPLACE it with `${var.<name>}` (发版链's
actual injection job). The two scripts never share a data format, only the
same matching rule, by design — that is the decoupling point this pipeline
was rebuilt around.

This script also unconditionally overwrites every step's Authorization
header to `${auth.<user>.token}`, regardless of whether the header carried a
real captured token or a synthetic-step placeholder — token injection is
never value-matched, it is name-matched on the header key alone.

It must NOT touch anything inside `bindings` (extract/assign wiring), step
ordering, or which steps are kept — that was already finalized and
lint-clean coming out of the 剪辑链. This script is read-only on structure,
write-only on values.

Usage:
    python script_assemble.py script.json --scaffold scaffold.json \\
        --auth-user codfish --out scenario.json
"""
import argparse
import json
from collections import defaultdict

# Change 2B: header policy switched from denylist to whitelist.
#
# Rationale: the previous denylist (NOISE_HEADERS) only listed 10 well-known
# browser/transport headers, but Chromium-derived clients carry ~20 more
# (`sec-ch-ua*`, `Sec-Fetch-*`, `Pragma`, etc.) that all qualify as noise.
# Every new browser version tends to add another one, so chasing the denylist
# is whack-a-mole. A whitelist inverts the policy: by default, keep ONLY
# headers we know the runner needs (`Authorization` for token + `Content-Type`
# for JSON POSTs); drop everything else. Real functional headers that surface
# later (e.g. `X-Request-ID` for tracing) can be opted in via the
# `--keep-headers` flag without touching this script.
DEFAULT_KEEP_HEADERS = {"authorization", "content-type"}

DEFAULT_MIN_VALUE_LEN = 4


def walk(node, prefix="$"):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, f"{prefix}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{prefix}[{i}]")
    else:
        yield prefix, node


def build_value_to_template(scaffold, blacklist_values, min_len):
    """value(str) -> '${var.x}' or '${resource.path}' template string.
    Same matching rule as analyze_flow.py's build_external_value_set, but
    here the output is the replacement template, not a skip-set.
    """
    mapping = {}
    cfg_vars = (scaffold.get("config", {}) or {}).get("vars", {}) or {}
    for name, v in cfg_vars.items():
        sval = str(v)
        if len(sval) >= min_len and sval not in blacklist_values:
            mapping.setdefault(sval, f"${{var.{name}}}")
    resource = scaffold.get("resource", {}) or {}
    for jp, v in walk(resource, "$"):
        if v is None or isinstance(v, bool):
            continue
        sval = str(v)
        if len(sval) >= min_len and sval not in blacklist_values:
            ref = jp.replace("$.", "resource.")
            mapping.setdefault(sval, f"${{{ref}}}")
    return mapping


def template_value(v, value_to_template):
    if isinstance(v, str) and v in value_to_template:
        return value_to_template[v]
    if isinstance(v, (int, float)) and str(v) in value_to_template:
        return value_to_template[str(v)]
    return v


def template_tree(node, value_to_template):
    if isinstance(node, dict):
        return {k: template_tree(v, value_to_template) for k, v in node.items()}
    if isinstance(node, list):
        return [template_tree(v, value_to_template) for v in node]
    return template_value(node, value_to_template)


def sanitize_headers(headers, auth_template, keep_headers=None):
    """Change 2B: whitelist policy.

    Default behavior keeps ONLY headers in DEFAULT_KEEP_HEADERS (currently
    Authorization + Content-Type). Anything else is dropped unconditionally,
    which is the inversion of the old denylist policy that leaked browser
    noise (`sec-ch-ua*`, `Sec-Fetch-*`, ...) the denylist did not list.

    Pass `keep_headers` (a set of lower-cased header names) to extend the
    whitelist for this run — for example when a tracing header
    (`x-request-id`) is known to be functional and the runner needs it.

    The auth injection rule is independent of whitelist membership: if the
    caller-supplied headers (or the whitelist extension set) already names an
    Authorization header, it is replaced with the auth_template. If no
    Authorization header is present at all, one is added — because every
    business request in the GIMBAL framework requires auth, and silently
    dropping it from a previously-authed capture would break the run.
    """
    keep = set(keep_headers or ())
    keep |= DEFAULT_KEEP_HEADERS
    out = {}
    saw_auth = False
    for k, v in (headers or {}).items():
        lk = k.lower()
        if lk not in keep:
            continue
        if lk == "authorization":
            out[k] = auth_template
            saw_auth = True
        else:
            out[k] = v
    if not saw_auth and "authorization" in keep:
        out["Authorization"] = auth_template
    return out


def _walk_strings(node, prefix="$"):
    """Yield (jsonpath, str_value) for every string leaf in `node`. Used by the
    report generator to surface untemplated string literals in request bodies.
    Skips strings that are already template references (${...})."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _walk_strings(v, f"{prefix}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk_strings(v, f"{prefix}[{i}]")
    elif isinstance(node, str):
        if node.startswith("${"):
            return
        yield prefix, node


def _write_report(report_path, kept_steps, final_steps, value_to_template, args, lint_result_path=None):
    """Change 9A: write scenario.report.md.

    Sections:
      1. Header: source paths, counts.
      2. External value templates (what got templated, by frequency).
      3. Extract/assign wiring table per kept step.
      4. Untemplated string literals in request bodies (candidates for
         manual review — these are values that survived assembly because no
         scaffold.var / scaffold.resource match was found).
      5. Lint summary (optional, from script_lint.py --out JSON).
    """
    lines = []
    lines.append("# Scenario Assembly Report")
    lines.append("")
    lines.append(f"- script: `{args.script_json}`")
    lines.append(f"- scaffold: `{args.scaffold}`")
    lines.append(f"- output scenario: `{args.out}`")
    lines.append(f"- auth user: `{args.auth_user}`")
    lines.append(f"- service: `{args.service}`")
    lines.append("")
    lines.append(f"## Counts")
    lines.append("")
    lines.append(f"- kept steps: **{len(kept_steps)}**")
    lines.append(f"- external values templated: **{len(value_to_template)}**")
    lines.append(f"- whitelist headers kept: `authorization, content-type`")
    if args.keep_headers:
        lines.append(f"- extra keep headers: `{args.keep_headers}`")
    lines.append("")

    # Section 2: external value templates by frequency
    if value_to_template:
        # Map template -> list of source values for reverse lookup
        tmpl_to_values = {}
        for v, tmpl in value_to_template.items():
            tmpl_to_values.setdefault(tmpl, []).append(v)
        lines.append("## External values templated")
        lines.append("")
        lines.append("| Template | # source values |")
        lines.append("|---|---:|")
        for tmpl in sorted(value_to_template.values()):
            lines.append(f"| `{tmpl}` | {len(tmpl_to_values.get(tmpl, []))} |")
        lines.append("")

    # Section 3: per-step wiring table
    lines.append("## Wiring (kept steps)")
    lines.append("")
    lines.append("| # | idx | method | path | extracts | assigns | synthetic |")
    lines.append("|---:|---:|---|---|---|---|---|")
    for pos, s in enumerate(kept_steps):
        extracts = ", ".join(f"`{e['var']}`" for e in s["bindings"].get("extracts", [])) or "—"
        assigns = ", ".join(f"`{a['var']}`→`{a['target']}`"
                            for a in s["bindings"].get("assigns", [])) or "—"
        synth = "yes" if s.get("synthetic") else ""
        lines.append(f"| {pos} | {s['idx']} | {s['method']} | `{s['path']}` | "
                     f"{extracts} | {assigns} | {synth} |")
    lines.append("")

    # Section 4: untemplated literal fields in request bodies
    lines.append("## Untemplated literals (review candidates)")
    lines.append("")
    lines.append("String values that survived assembly because no scaffold var / "
                 "resource matched. These may be either legitimate constant "
                 "payloads or missed wiring — review before shipping.")
    lines.append("")
    any_untemplated = False
    for pos, (s, fs) in enumerate(zip(kept_steps, final_steps)):
        body = fs["request"]["body"]
        hits = list(_walk_strings(body))
        if not hits:
            continue
        any_untemplated = True
        lines.append(f"**Step {pos} (idx={s['idx']}, {s['method']} `{s['path']}`)**")
        lines.append("")
        lines.append("| jsonpath | literal |")
        lines.append("|---|---|")
        for jp, val in hits:
            disp = val if len(val) <= 80 else val[:77] + "..."
            lines.append(f"| `{jp}` | `{disp}` |")
        lines.append("")
    if not any_untemplated:
        lines.append("_None — every string in request bodies is either templated or non-string._")
        lines.append("")

    # Section 5: lint summary (optional)
    if lint_result_path:
        try:
            with open(lint_result_path, encoding="utf-8") as f:
                lr = json.load(f)
            lines.append("## Lint summary")
            lines.append("")
            lines.append(f"- verdict: **{lr.get('verdict', 'unknown')}**")
            lines.append(f"- violations: {len(lr.get('violations', []))}")
            lines.append(f"- warnings: {len(lr.get('warnings', []))}")
            if lr.get("violations"):
                lines.append("")
                lines.append("### Violations")
                for v in lr["violations"]:
                    lines.append(f"- {v}")
            if lr.get("warnings"):
                lines.append("")
                lines.append("### Warnings")
                for w in lr["warnings"]:
                    lines.append(f"- {w}")
            lines.append("")
        except FileNotFoundError:
            lines.append(f"## Lint summary")
            lines.append("")
            lines.append(f"_lint result file not found: `{lint_result_path}`_")
            lines.append("")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[ok] wrote {report_path}")


def build_strategy(step):
    strategy = [{
        "kind": "assertion", "name": "assert_http_status_eq_200",
        "phase": "verifying", "order": 0, "enabled": True, "onFailure": "abort",
        "target": "$.response_status", "operator": "eq", "expected": 200,
        "message": f"{step['path']} 应返回200", "soft": False,
    }]
    for i, e in enumerate(step["bindings"].get("extracts", [])):
        strategy.append({
            "kind": "extract", "name": f"extract_{e['var']}",
            "phase": "after_request", "order": i, "enabled": True, "onFailure": "abort",
            "expression": e["expression"], "target": e["var"],
            "required": True, "default": None, "scope": e.get("scope", "scenario"),
        })
    for i, a in enumerate(step["bindings"].get("assigns", [])):
        strategy.append({
            "kind": "assign", "name": f"assign_{a['var']}",
            "phase": "before_request", "order": i, "enabled": True, "onFailure": "abort",
            "source": f"$.{a['var']}", "target": a["target"], "scope": "scenario",
        })
    return strategy


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script_json")
    ap.add_argument("--scaffold", required=True)
    ap.add_argument("--value-blacklist", default=None)
    ap.add_argument("--min-value-len", type=int, default=DEFAULT_MIN_VALUE_LEN)
    ap.add_argument("--keep-headers", default=None,
                    help="comma-separated extra headers to keep beyond the default "
                         "whitelist (authorization, content-type). Names are matched "
                         "case-insensitively. Example: --keep-headers x-request-id,traceparent")
    ap.add_argument("--auth-user", default=None,
                    help="config.users key to template Authorization with; "
                         "defaults to the only user if there's exactly one")
    ap.add_argument("--service", default=None,
                    help="config.services key to put in every step's api.service; "
                         "defaults to the only service if there's exactly one")
    ap.add_argument("--out", default="scenario.json")
    ap.add_argument("--report", default=None,
                    help="optional path to write a human-readable Markdown report "
                         "(scenario.report.md) listing extract/assign pairs, "
                         "fallback literal fields, and lint warnings. If omitted, "
                         "defaults to <out>.report.md next to --out.")
    ap.add_argument("--lint-result", default=None,
                    help="optional path to a JSON file produced by script_lint.py "
                         "--out; if present, its warnings/violations are appended "
                         "to the report. Not required for assembly.")
    args = ap.parse_args()

    script = json.load(open(args.script_json, encoding="utf-8"))
    scaffold = json.load(open(args.scaffold, encoding="utf-8"))

    if any(g["status"] != "resolved" for g in script.get("open_gaps", [])):
        raise SystemExit("[error] script.json still has unresolved open_gaps; "
                         "run script_lint.py and resolve them before assembling.")

    blacklist_values = set()
    if args.value_blacklist:
        blacklist_values = set(json.load(open(args.value_blacklist, encoding="utf-8")).get("values", []))

    keep_headers = set()
    if args.keep_headers:
        keep_headers = {h.strip().lower() for h in args.keep_headers.split(",") if h.strip()}

    value_to_template = build_value_to_template(scaffold, blacklist_values, args.min_value_len)

    users = (scaffold.get("config", {}) or {}).get("users", {}) or {}
    auth_user = args.auth_user or (next(iter(users)) if len(users) == 1 else None)
    if not auth_user:
        raise SystemExit("[error] multiple (or zero) config.users in scaffold; pass --auth-user explicitly.")
    auth_template = f"${{auth.{auth_user}.token}}"

    services = (scaffold.get("config", {}) or {}).get("services", {}) or {}
    service = args.service or (next(iter(services)) if len(services) == 1 else None)
    if not service:
        raise SystemExit("[error] multiple (or zero) config.services in scaffold; pass --service explicitly.")

    kept = [s for s in script["steps"] if s["decision"] == "keep"]
    final_steps = []
    synthetic_positions = []
    for pos, s in enumerate(kept):
        body = template_tree(s.get("request_body") or {}, value_to_template)
        headers = sanitize_headers(s.get("headers"), auth_template, keep_headers=keep_headers)
        final_steps.append({
            "kind": "step",
            "description": s.get("reason", ""),
            "api": {
                "kind": "api", "service": service, "method": s["method"],
                "path": s["path"], "headers": headers, "timeout": 30,
            },
            "request": {"kind": "request", "body": body},
            "strategy": build_strategy(s),
        })
        if s.get("synthetic"):
            synthetic_positions.append(pos)

    scenario = dict(scaffold)
    scenario["steps"] = final_steps

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(scenario, f, ensure_ascii=False, indent=2)
    print(f"[ok] wrote {args.out}: {len(final_steps)} steps "
          f"({len(synthetic_positions)} synthetic), {len(value_to_template)} "
          f"external values available for templating")

    if synthetic_positions:
        sidecar = args.out.rsplit(".", 1)[0] + ".synthetic_steps.json"
        with open(sidecar, "w", encoding="utf-8") as f:
            json.dump({"synthetic_step_positions": synthetic_positions}, f, indent=2)
        print(f"[ok] wrote {sidecar} — pass these positions to validate_scenario.py "
              f"--skip-extract-verify-positions (no backing capture record by design)")

    # Change 9A: emit a human-readable Markdown report alongside the scenario.
    report_path = args.report or (args.out.rsplit(".", 1)[0] + ".report.md")
    _write_report(report_path, kept, final_steps, value_to_template, args, lint_result_path=args.lint_result)


if __name__ == "__main__":
    main()
