"""用例 YAML → plate Scenario definition。

definition 必须是能过 plate /convert 的合法 Scenario。实测最小必填集：
scenarioId / meta(11 项) / config.services / config.timePolicy / resource /
steps[].api / steps[].request / steps[].strategy。
"""

from __future__ import annotations

import re
from typing import Any

SERVICE = "platform-service"
SERVICE_URL = "http://127.0.0.1:8000"
FIXED_CREATE_TIME = "2026-09-28T00:00:00Z"

SCENARIO_ID_RE = re.compile(r"^sc-[a-z0-9-]+$")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", text.lower()).strip("-")


def _render(value: Any, subs: dict[str, str]) -> Any:
    if isinstance(value, str):
        for key, repl in subs.items():
            value = value.replace("${" + key + "}", repl)
        return value
    if isinstance(value, dict):
        return {k: _render(v, subs) for k, v in value.items()}
    if isinstance(value, list):
        return [_render(v, subs) for v in value]
    return value


def build_definition(case: dict, *, sb_username: str, run_token: str = "") -> dict:
    base = _slug(case["id"])
    token = _slug(run_token)
    scenario_id = f"sc-{base}-{token}" if token else f"sc-{base}"
    if not SCENARIO_ID_RE.match(scenario_id):
        raise ValueError(f"scenario_id 不合规: {scenario_id!r}")

    subs = {"sb.username": sb_username, "sb.scenario_id": scenario_id}

    steps: list[dict[str, Any]] = []
    for step in case["steps"]:
        service = step.get("service", SERVICE)
        if service != SERVICE:
            raise ValueError(
                f"只允许 service={SERVICE}，收到 {service!r} —— 自举只打平台自己"
            )
        strategy: list[dict[str, Any]] = []
        extract = step.get("extract")
        if extract:
            strategy.append({
                "kind": "extract",
                "expression": _render(extract["expr"], subs),
                "target": extract["target"],
                "scope": "scenario",
                "required": extract.get("required", True),
            })
        for a in step.get("asserts", []):
            strategy.append({
                "kind": "assertion",
                "target": _render(a["target"], subs),
                "operator": a["operator"],
                "expected": _render(a.get("expected"), subs),
                "message": a.get("message", case.get("name", "")),
                "soft": a.get("soft", False),
            })
        if not strategy:
            raise ValueError(f"step 至少要有 1 个 strategy（case {case['id']}）")

        headers = {"Content-Type": "application/json"}
        if step.get("auth", True):
            headers["Authorization"] = "Bearer ${auth.sb.token}"

        steps.append({
            "kind": "step",
            "api": {
                "kind": "api",
                "service": SERVICE,
                "method": step["method"],
                "path": _render(step["path"], subs),
                "headers": headers,
            },
            "request": {
                "kind": "request",
                "body": _render(step.get("body", {}), subs),
            },
            "strategy": strategy,
        })

    return {
        "kind": "scenario",
        "scenarioId": scenario_id,
        "meta": {
            "name": case.get("name", case["id"]),
            "description": case.get("description", ""),
            "module": "self-bootstrap",
            "priority": 1,
            "author": sb_username,
            "owner": sb_username,
            "tags": case.get("tags", ["smoke"]),
            "version": "1.0.0",
            "createTime": FIXED_CREATE_TIME,
            "expire": False,
            "requirementRef": [],
            "system": ["platform"],
        },
        "config": {
            "services": {SERVICE: SERVICE_URL},
            "users": {},
            "timePolicy": {"kind": "record"},
            "vars": {},
        },
        "resource": {},
        "steps": steps,
    }
