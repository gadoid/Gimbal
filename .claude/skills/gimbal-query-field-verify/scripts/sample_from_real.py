#!/usr/bin/env python3
"""sample_from_real.py — Stage 2 (real sampling via the gimbal engine).

Replaces the synthetic `samples.json` that build_scenario.py normally
consumes. We use the user-validated working scaffold
(`scenario_merged.json`) as a probe: run it once, register an
`HTTP_AFTER_RECV` hook that captures `response_body` from the state
machine scratch, then derive per-field real samples (canon, query_code,
row_id, order_id) from the actual `list[*]` rows.

Why this exists:
    The legacy Stage 2 (`sample_fields.py`) shells out its own HTTP
    requests with the user's cookie. When the endpoint requires a
    session-bound auth token (e.g. yhr `Cookie: ${auth.codfish.token}`
    resolved at run time), that path is fragile. Running the actual
    gimbal engine is the only way to get a fully-authenticated
    response without re-implementing the auth manager.

Why we use a hook, not HttpResponseEvent:
    `HttpResponseEvent.response_body` is set from
    `getattr(result, "body", None)` — but `CallExecutor.execute()`
    returns `StrategyResult(status=PASSED, extracted={...})` WITHOUT a
    `.body` attribute. The body actually lives in
    `view.write_scratch("response_body", resp_body)`. The
    `HTTP_AFTER_RECV` hook payload includes `ctx = self._view`, so we
    can `ctx.read_scratch("response_body")` directly.

Usage:
    python sample_from_real.py \
        --scaffold scenario_merged.json \
        --mapping   mapping.json \
        --out       samples.json \
        [--max-per-field 3] [--max-rows 80]

Outputs:
    samples.json — same shape as `sample_fields.py` output, but with
    `status: REAL_SAMPLED` per field. Consumed by `build_scenario.py`.

Scaffold contract:
    The scaffold **must** contain exactly one step at index 0 (the
    seed). It must be `enabled: false` OR have an empty `strategy[]`
    so the engine does not assert anything. We re-enable that step
    programmatically for the probe — we only need its HTTP
    response_body, not its assertions.
"""
from __future__ import annotations

import argparse
import copy
import datetime
import json
import re
import sys
from typing import Any

# ---------- gimbal internal API (the CLI itself imports these) ----------

from gimbal.cli.context import CLIContext
from gimbal.core.bootstrap import bootstrap, shutdown
from gimbal.core.runner import Engine
from gimbal.schema.scenario import Scenario


EMPTY = ("", None)


# ---------- canonicalizer (mirrors build_scenario.py canon rules) ----------

def canon(v: Any) -> str | None:
    if v in EMPTY:
        return None
    s = str(v).strip()
    if not s:
        return None
    m = re.fullmatch(r"[$￥¥]\s*([\d,]+(?:\.\d+)?)", s)
    if m:
        return m.group(1).replace(",", "")
    return s


def derive_query_code(category: str, value: Any, value_map: dict | None) -> str:
    """Backend wire-format value: ENUM uses value_map reverse-lookup;
    everything else is the canon of the raw cell value."""
    if category == "ENUM" and value_map:
        inv = {v: k for k, v in value_map.items()}
        s = str(value).strip()
        if s in inv:
            return inv[s]
    return canon(value) or ""


# ---------- probe scaffolding -------------------------------------------

def build_probe_scenario(scaffold: dict, mapping: dict) -> dict:
    """Mutate the scaffold into a probe scenario:

    * step 0 (the seed) is force-enabled with a single `assert HTTP 200`
      so the engine reports success and our hook fires. We only need
      its response_body, not detailed assertions.
    * Steps 1..N are field-probe steps, one per TESTABLE param. They
      call the same endpoint with that param set to a placeholder, so
      the captured response_body covers filtered calls too. Each carries
      a single `assert_http_status_eq_200`.
    """
    probe = copy.deepcopy(scaffold)
    seed = probe["steps"][0]
    seed["enabled"] = True
    seed["strategy"] = [_http_200_assert()]
    base_api = seed["api"]
    base_body = (seed.get("request") or {}).get("body") or {}

    testable = [p for p in mapping["params"] if p["status"] == "TESTABLE"]
    for param_entry in testable:
        p = param_entry["param"]
        body = dict(base_body)
        body[p] = "<probe>"   # placeholder — capture real response anyway
        probe["steps"].append({
            "kind": "step",
            "enabled": True,
            "description": f"probe field={p}",
            "api": copy.deepcopy(base_api),
            "request": {"kind": "request", "body": body},
            "strategy": [_http_200_assert()],
        })
    return probe


def _http_200_assert() -> dict:
    return {
        "kind": "assertion",
        "name": "assert_http_status_eq_200",
        "phase": "verifying",
        "order": 0,
        "enabled": True,
        "onFailure": "abort",
        "target": "$.response_status",
        "operator": "eq",
        "expected": 200,
        "message": "probe should return HTTP 200",
        "soft": False,
    }


# ---------- hook ---------------------------------------------------------

def attach_response_hook(hook_registry, sink: list) -> str:
    """Register an HTTP_AFTER_RECV hook that reads response_body from the
    state-machine scratch (`ctx`) and appends a record to `sink`.

    Payload shape (from statemachine/engine.py:435):
        {method, url, status, headers, body, duration_ms, step_id, ctx}
    `ctx` exposes `read_scratch("response_body")` and
    `read_scratch("response_status")`."""
    def _hook(payload: dict) -> None:
        try:
            ctx = payload.get("ctx")
            if ctx is None:
                return
            body = ctx.read_scratch("response_body")
            status = ctx.read_scratch("response_status")
            sink.append({
                "step_id":     payload.get("step_id"),
                "url":         payload.get("url"),
                "method":      payload.get("method"),
                "status":      status,
                "duration_ms": payload.get("duration_ms"),
                "body":        body,
            })
        except Exception as exc:                          # noqa: BLE001
            sys.stderr.write(f"[hook] drop event: {exc}\n")
    return hook_registry.register(
        "http.after_recv", _hook, plugin_name="sample_from_real",
    )


# ---------- post-processing -----------------------------------------------

def extract_baseline_count(responses: list) -> int | None:
    """The first HTTP 200 response_body is the seed (baseline). Pull `count`."""
    for r in responses:
        if r["status"] == 200 and isinstance(r["body"], dict):
            c = r["body"].get("count")
            if isinstance(c, int):
                return c
    return None


def collect_rows(responses: list, max_rows: int) -> list[dict]:
    """The seed's `list` is what we want; subsequent responses are
    filtered probes (often empty or smaller). We take the FIRST 200
    response with a non-empty `list`."""
    for r in responses:
        if r["status"] == 200 and isinstance(r["body"], dict):
            rows = r["body"].get("list") or []
            if rows:
                return rows[:max_rows]
    return []


def sample_field(
    param_entry: dict,
    rows: list[dict],
    per_field: int,
) -> list[dict]:
    """For one TESTABLE param, build up to `per_field` distinct samples
    anchored to the first row that yields a non-empty canon."""
    fields = param_entry.get("response_fields") or (
        [param_entry["response_field"]] if param_entry.get("response_field") else []
    )
    if not fields:
        return []

    target_field = fields[0]
    value_map = param_entry.get("value_map") or {}

    seen: set[str] = set()
    out: list[dict] = []
    for row in rows:
        raw = row.get(target_field)
        c = canon(raw)
        if c is None or c in seen:
            continue
        seen.add(c)
        out.append({
            "value":       raw,
            "canon":       c,
            "query_code":  derive_query_code(param_entry["category"], raw, value_map),
            "order_id":    row.get("order_id") or row.get("order_no"),
            "row_id":      row.get("id"),
        })
        if len(out) >= per_field:
            break
    return out


# ---------- main ---------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scaffold", required=True,
                    help="working scenario JSON (must have one seed step "
                         "with the same api template build_scenario.py reads)")
    ap.add_argument("--mapping",  required=True)
    ap.add_argument("--max-per-field", type=int, default=3,
                    help="max distinct samples per TESTABLE field")
    ap.add_argument("--max-rows", type=int, default=80,
                    help="cap on baseline rows consumed from response_body.list")
    ap.add_argument("--out", default="samples.json")
    ap.add_argument("--md",  default="samples.md")
    ap.add_argument("--env",  default="dev")
    ap.add_argument("--mode", default="local")
    args = ap.parse_args()

    mapping  = json.load(open(args.mapping,  encoding="utf-8"))
    scaffold = json.load(open(args.scaffold, encoding="utf-8"))

    probe = build_probe_scenario(scaffold, mapping)
    testable = [p for p in mapping["params"] if p["status"] == "TESTABLE"]
    print(f"[probe] steps={len(probe['steps'])} (1 seed + "
          f"{len(probe['steps']) - 1} field probes)", file=sys.stderr)

    cli_ctx = CLIContext(
        env=args.env, mode=args.mode,
        log_level="warning", input_format="json",
        output="console", extras={},
    )
    config = bootstrap(cli_ctx)

    sink: list[dict] = []
    hook_id = attach_response_hook(config.hook_registry, sink)
    print(f"[probe] registered HTTP_AFTER_RECV hook (id={hook_id})",
          file=sys.stderr)

    try:
        scenario_obj = Scenario.model_validate(probe)
    except Exception as exc:                                # noqa: BLE001
        config.hook_registry.unregister(hook_id)
        shutdown(config)
        sys.exit(f"[probe] Scenario.model_validate failed: {exc}")

    engine = Engine(config)
    result = engine.run(scenario_obj)
    print(f"[probe] engine.run() -> exit={result.exit_code} "
          f"total={result.total} passed={result.passed} "
          f"failed={result.failed} error={result.error}", file=sys.stderr)

    config.hook_registry.unregister(hook_id)
    shutdown(config)

    baseline_count = extract_baseline_count(sink)
    rows = collect_rows(sink, args.max_rows)
    print(f"[probe] baseline_count={baseline_count} rows_collected="
          f"{len(rows)} hook_events={len(sink)}", file=sys.stderr)

    fields: dict[str, dict] = {}
    for entry in testable:
        samples = sample_field(entry, rows, args.max_per_field)
        if samples:
            fields[entry["param"]] = {
                "samples": samples,
                "distinct_seen": len(samples),
                "status": "REAL_SAMPLED",
            }
        else:
            fields[entry["param"]] = {
                "samples": [],
                "status": "NO_SAMPLE",
                "scanned": len(rows),
            }

    out = {
        "_comment": ("REAL sampling via gimbal engine + HTTP_AFTER_RECV "
                     "hook. row_id anchors the assertion against the "
                     "backend's actual response."),
        "scanned_rows": len(rows),
        "baseline_count": baseline_count,
        "scan_ts": datetime.datetime.now().astimezone().isoformat(),
        "fields": fields,
    }
    json.dump(out, open(args.out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    sampled = [k for k, v in fields.items() if v["status"] == "REAL_SAMPLED"]
    empty   = [k for k, v in fields.items() if v["status"] == "NO_SAMPLE"]
    with open(args.md, "w", encoding="utf-8") as f:
        f.write(f"# samples (REAL) — scanned {len(rows)} rows, "
                f"baseline_count={baseline_count}\n\n"
                f"## SAMPLED ({len(sampled)})\n\n")
        for k in sampled:
            vals = ", ".join(repr(s["canon"]) for s in fields[k]["samples"])
            f.write(f"- `{k}` x{len(fields[k]['samples'])}: {vals}\n")
        f.write(f"\n## NO_SAMPLE ({len(empty)})\n\n")
        for k in empty:
            f.write(f"- `{k}`\n")
    print(f"[probe] wrote {args.out} sampled={len(sampled)} "
          f"no_sample={len(empty)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
