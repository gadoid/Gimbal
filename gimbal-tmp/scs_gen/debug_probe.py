#!/usr/bin/env python3
"""debug_probe.py — diagnostic: dump the captured response_body of the
first HTTP call so we can see what shape the yhr backend returns.

This is throwaway — kept only inside gimbal-tmp/ and deleted after the
real probe is verified."""
from __future__ import annotations

import copy
import json
import sys

from gimbal.cli.context import CLIContext
from gimbal.core.bootstrap import bootstrap, shutdown
from gimbal.core.runner import Engine
from gimbal.schema.scenario import Scenario


def main() -> int:
    scaffold = json.load(open("gimbal-tmp/scs_gen/scenario_merged.json", encoding="utf-8"))
    mapping  = json.load(open("gimbal-tmp/scs_gen/mapping.json", encoding="utf-8"))

    # Force-enable step 0 only (no probes), keep strategy as-is
    probe = copy.deepcopy(scaffold)
    seed = probe["steps"][0]
    seed["enabled"] = True
    seed["strategy"] = [
        {
            "kind": "assertion",
            "name": "assert_http_status_eq_200",
            "phase": "verifying",
            "order": 0,
            "enabled": True,
            "onFailure": "abort",
            "target": "$.response_status",
            "operator": "eq",
            "expected": 200,
            "message": "probe",
            "soft": False,
        },
    ]
    probe["steps"] = [seed]   # only step 0

    cli_ctx = CLIContext(env="dev", mode="local", log_level="info",
                         input_format="json", output="console", extras={})
    cfg = bootstrap(cli_ctx)

    sink = []
    def _on(event):
        sink.append({
            "step_id":  getattr(event, "step_id", None),
            "status":   getattr(event, "status_code", None),
            "body_keys": (list((getattr(event, "response_body", None) or {}).keys())
                          if isinstance(getattr(event, "response_body", None), dict)
                          else type(getattr(event, "response_body", None)).__name__),
            "body_head": (str(getattr(event, "response_body", None))[:400]
                          if getattr(event, "response_body", None) is not None else None),
            "duration_ms": getattr(event, "duration_ms", None),
        })
    sub_id = cfg.event_bus.subscribe(_on, "http.response")

    scenario_obj = Scenario.model_validate(probe)
    engine = Engine(cfg)
    result = engine.run(scenario_obj)
    print(f"[debug] exit={result.exit_code} total={result.total} "
          f"passed={result.passed} failed={result.failed}")
    print(f"[debug] captured {len(sink)} http.response events:")
    for i, s in enumerate(sink):
        print(f"--- [{i}] step_id={s['step_id']} status={s['status']} "
              f"duration={s['duration_ms']:.0f}ms")
        print(f"    body_keys={s['body_keys']}")
        print(f"    body_head={s['body_head']!r}")

    cfg.event_bus.unsubscribe(sub_id)
    shutdown(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
