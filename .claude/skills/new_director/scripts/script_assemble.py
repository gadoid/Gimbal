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

NOISE_HEADERS = {
    "host", "connection", "content-length", "cookie", "origin", "referer",
    "user-agent", "accept", "accept-encoding", "accept-language",
}

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


def sanitize_headers(headers, auth_template):
    out = {}
    for k, v in (headers or {}).items():
        if k.lower() in NOISE_HEADERS:
            continue
        if k.lower() == "authorization":
            out[k] = auth_template
            continue
        out[k] = v
    if "Authorization" not in out and "authorization" not in {k.lower() for k in out}:
        out["Authorization"] = auth_template
    return out


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
    ap.add_argument("--auth-user", default=None,
                    help="config.users key to template Authorization with; "
                         "defaults to the only user if there's exactly one")
    ap.add_argument("--service", default=None,
                    help="config.services key to put in every step's api.service; "
                         "defaults to the only service if there's exactly one")
    ap.add_argument("--out", default="scenario.json")
    args = ap.parse_args()

    script = json.load(open(args.script_json, encoding="utf-8"))
    scaffold = json.load(open(args.scaffold, encoding="utf-8"))

    if any(g["status"] != "resolved" for g in script.get("open_gaps", [])):
        raise SystemExit("[error] script.json still has unresolved open_gaps; "
                         "run script_lint.py and resolve them before assembling.")

    blacklist_values = set()
    if args.value_blacklist:
        blacklist_values = set(json.load(open(args.value_blacklist, encoding="utf-8")).get("values", []))

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
        headers = sanitize_headers(s.get("headers"), auth_template)
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


if __name__ == "__main__":
    main()
