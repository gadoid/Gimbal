#!/usr/bin/env python3
"""
script_assemble.py — turn a resolved script.json into a final GIMBAL scenario.

This is the SECOND mechanical transform (the first being script_init.py). By the
time it runs, all judgment is already baked into script.json: which steps are
kept, how they are ordered, every extract/assign binding, every gap resolution.
Assembly performs NO judgment. It:

  * walks kept steps in `order`,
  * re-reads each step's raw request body from the capture (by idx),
  * sanitizes headers (template auth, strip browser noise),
  * emits strategy blocks from bindings (assertion + extract + assign),
  * pulls config/meta/resource from the golden (config fallback),
  * seeds config.vars from gap static resolutions.

The output is shaped to pass validate_scenario.py unchanged.

Usage:
    python script_assemble.py CAPTURE.script.json \
        [--out scenario.json]

The script header records source_capture and golden_ref, so both are read from
there; no extra flags are normally needed.

See references/scenario-schema.md for the target shape and
references/script-schema.md for the input shape.
"""
import argparse
import json
import os
import sys

# Reuse the capture parser from analyze_flow to avoid a second implementation.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze_flow import load_records, parse_body  # noqa: E402

# Headers to drop entirely (browser / transport noise).
NOISE_HEADERS = {
    "host", "connection", "content-length", "cookie", "origin", "referer",
    "user-agent", "accept", "accept-encoding", "accept-language",
}
AUTH_HEADERS = {"authorization", "admin-token"}


def sanitize_headers(headers: dict, auth_user: str) -> dict:
    """Keep only functional headers; template any auth header."""
    out = {}
    if not headers:
        return {"Authorization": f"${{auth.{auth_user}.token}}"}
    for k, v in headers.items():
        lk = k.lower()
        if lk in NOISE_HEADERS or lk.startswith(("sec-", "sec-ch")):
            continue
        if lk in AUTH_HEADERS:
            out["Authorization"] = f"${{auth.{auth_user}.token}}"
            continue
        out[k] = v
    out.setdefault("Authorization", f"${{auth.{auth_user}.token}}")
    return out


def strat_base(kind, name, phase, order):
    return {
        "kind": kind, "name": name, "phase": phase, "order": order,
        "enabled": True, "onFailure": "abort",
    }


def build_strategies(step, assign_targets_static):
    """assertion (always) + extracts + assigns, in GIMBAL strategy shape."""
    strategies = []
    # mandatory status assertion
    a = strat_base("assertion", "assert_status_200", "verifying", 0)
    a.update({
        "target": "$.response_status", "operator": "eq", "expected": 200,
        "message": f"{step.get('path')} should return 200", "soft": False,
        "scope": "scenario",
    })
    strategies.append(a)

    b = step.get("bindings", {})
    for i, ex in enumerate(b.get("extracts", [])):
        s = strat_base("extract", f"extract_{ex['var']}", "after_request", i)
        s.update({
            "expression": ex["expression"], "target": ex["var"],
            "required": True, "default": None,
            "scope": ex.get("scope", "scenario"),
        })
        strategies.append(s)
    for i, asg in enumerate(b.get("assigns", [])):
        # static gap vars inject as ${var.x} in the body instead of a runtime
        # assign; only dynamic vars get an assign strategy.
        if asg["var"] in assign_targets_static:
            continue
        s = strat_base("assign", f"assign_{asg['var']}", "before_request", i)
        s.update({
            "source": f"$.{asg['var']}", "target": asg["target"],
            "scope": "scenario",
        })
        strategies.append(s)
    return strategies


def inject_static_into_body(body, assigns, static_vars):
    """For gap-static vars, replace the captured value at the assign target with
    a ${var.x} template so the value comes from config.vars at run time."""
    if body is None:
        return body
    for asg in assigns:
        var = asg["var"]
        if var not in static_vars:
            continue
        # target is like $.request_body.a.b[0].c — walk and set
        path = asg["target"].replace("$.request_body", "", 1)
        import re
        keys = re.findall(r"\.([A-Za-z0-9_]+)|\[(\d+)\]", path)
        cur = body
        try:
            for j, (k, ix) in enumerate(keys):
                last = j == len(keys) - 1
                if last:
                    if k:
                        cur[k] = f"${{var.{var}}}"
                    else:
                        cur[int(ix)] = f"${{var.{var}}}"
                else:
                    cur = cur[k] if k else cur[int(ix)]
        except (KeyError, IndexError, TypeError):
            pass  # target not present in this body; skip silently
    return body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--out", default=None)
    ap.add_argument("--auth-user", default=None,
                    help="user key in config.users for token templating; "
                         "default: first user in the golden")
    args = ap.parse_args()

    sc = json.load(open(args.script, encoding="utf-8"))
    capture = sc["source_capture"]
    golden = json.load(open(sc["golden_ref"], encoding="utf-8"))

    # Raw records, keyed by idx (synthetic inserted-lookup idxs have no raw
    # record and must carry their own request body in the step — handled below).
    recs = load_records(capture)

    # config fallback: copy meta/config/resource from golden verbatim.
    config = json.loads(json.dumps(golden.get("config", {})))
    users = config.get("users", {})
    auth_user = args.auth_user or (next(iter(users), None) if users else "default")

    # gap static vars -> seed config.vars and mark for body templating.
    static_vars = {}
    for g in sc.get("open_gaps", []):
        res = g.get("resolution") or {}
        if res.get("kind") == "static":
            static_vars[res["var"]] = g.get("value")
    config.setdefault("vars", {})
    for var, val in static_vars.items():
        config["vars"].setdefault(var, val)
    static_var_names = set(static_vars)

    kept = sorted(
        [s for s in sc["steps"] if s.get("status") == "kept"],
        key=lambda s: s.get("order", 0),
    )

    services = config.get("services", {})
    service_name = next(iter(services), None) if services else None

    steps_out = []
    for s in kept:
        idx = s["idx"]
        raw = recs[idx] if idx < len(recs) else None
        if raw is not None:
            body = parse_body(raw.get("body"))
            headers = raw.get("headers", {}) or {}
            method = raw.get("method") or s.get("method") or "POST"
            path = raw.get("path") or s.get("path")
        else:
            # synthetic inserted-lookup step: body/headers must live on the step
            body = s.get("request_body")
            headers = s.get("headers", {})
            method = s.get("method", "POST")
            path = s.get("path")

        body = inject_static_into_body(body, s.get("bindings", {}).get("assigns", []),
                                       static_var_names)

        api = {
            "kind": "api", "method": method, "path": path,
            "headers": sanitize_headers(headers, auth_user), "timeout": 30,
        }
        if service_name:
            api["service"] = service_name

        steps_out.append({
            "kind": "step",
            "api": api,
            "request": {"kind": "request", "body": body if body is not None else {}},
            "strategy": build_strategies(s, static_var_names),
        })

    scenario = {
        "kind": "scenario",
        "scenarioId": golden.get("scenarioId", "generated") + "_from_capture",
        "meta": golden.get("meta", {}),
        "config": config,
        "resource": golden.get("resource", {}),
        "steps": steps_out,
    }

    out_path = args.out or (args.script.rsplit(".script.json", 1)[0] + ".scenario.json")
    if out_path == args.script:
        out_path = args.script.rsplit(".", 1)[0] + ".scenario.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(scenario, f, ensure_ascii=False, indent=2)

    print(f"[ok] wrote {out_path}")
    print(f"[summary] {len(steps_out)} steps, {len(static_vars)} static var(s) seeded")
    print(f"[next] run: python validate_scenario.py {out_path} --capture {capture}")


if __name__ == "__main__":
    main()
