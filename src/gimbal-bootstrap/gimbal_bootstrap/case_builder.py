"""用例 YAML → plate Scenario definition。

definition 必须是能过 plate /convert 的合法 Scenario。实测最小必填集：
scenarioId / meta(11 项) / config.services / config.timePolicy / resource /
steps[].call / steps[].request / steps[].strategy。
"""

from __future__ import annotations

import re
import uuid
from typing import Any

SERVICE = "platform-service"
SERVICE_URL = "http://127.0.0.1:8000"
FIXED_CREATE_TIME = "2026-09-28T00:00:00Z"

SCENARIO_ID_RE = re.compile(r"^sc-[a-z0-9-]+$")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", text.lower()).strip("-")


def _username_slug(text: str) -> str:
    """平台 RegisterIn.username = ^[A-Za-z0-9_]+$ —— 比 _slug 还窄：
    连字符和点都不收。"""
    return re.sub(r"[^A-Za-z0-9_]+", "", text)


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


def build_definition(
    case: dict,
    *,
    sb_username: str,
    sb_password: str = "",
    run_token: str = "",
    new_username: str = "",
    new_password: str = "",
) -> dict:
    """用例 YAML → plate Scenario definition。

    **管理员口令不进 definition。** definition 就是 POST /api/scenarios 的
    body，平台把它存进 composer_scenario.payload，每次运行再深拷贝进
    execution_snapshots —— 那张表本仓库里没人清理。管理员口令从这条路进去
    等于把平台交出去，而且绕开了「口令不入库」那条原则。

    所以这里根本没有 `${sb.password}` 这个占位符：验 register/login 用的是
    一次性账号，口令由编排器当场随机生成（`new_password`），跟管理员口令
    无关，跑完就把那个账号删掉。
    """
    base = _slug(case["id"])
    token = _slug(run_token)
    scenario_id = f"sc-{base}-{token}" if token else f"sc-{base}"
    if not SCENARIO_ID_RE.match(scenario_id):
        raise ValueError(f"scenario_id 不合规: {scenario_id!r}")

    subs = {
        "sb.username": sb_username,
        "sb.scenario_id": scenario_id,
        # 一次性账号：验 register / login 端点本身。不能复用 sb.username ——
        # 那是编排器已经建好并提权过的那个，同名必 409。必须由编排器按
        # **轮次**传进来：按用例派生的话，注册的账号和后续登录的账号就
        # 不是同一个。
        "sb.new_username": new_username
        or "sb_" + _username_slug(token or uuid.uuid4().hex[:6]),
        "sb.new_password": new_password,
    }

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
            # call 是唯一调用形态（v2.1 批次 F 退役了 step.api）。
            # plate 的 Step._reject_api_form 在 validate 期显式拒 api 形态，
            # 存量文件的迁移见 scripts/migrate_legacy_case.py；这里是生成器，
            # 直接按新形态产出，不走迁移。
            "call": {
                "kind": "call",
                "protocol": "http",
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
