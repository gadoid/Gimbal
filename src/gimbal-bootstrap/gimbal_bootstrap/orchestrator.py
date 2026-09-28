"""自举编排器：注册账号 → 建资源 → 发起运行 → 轮询 → 清理。

全程以普通用户身份走平台公开 HTTP API，不碰任何内部接口。
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import yaml

from gimbal_bootstrap.assertions import evaluate
from gimbal_bootstrap.case_builder import build_definition
from gimbal_bootstrap.platform_client import Platform, PlatformError

BASE_URL = "http://127.0.0.1:8000"
# 自举账号口令不在源码里 —— 用户要登进平台检查，固定口令必须好打，
# 但账号是管理员，不该把口令提交进仓库。真值放 gitignore 掉的 .env
# （模板见同目录 .env.example），进程环境变量优先于它。
DOTENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def _resolve_password() -> str:
    from_env = os.environ.get("GIMBAL_SB_PASSWORD", "").strip()
    if from_env:
        return from_env
    if DOTENV_PATH.is_file():
        for line in DOTENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("GIMBAL_SB_PASSWORD="):
                return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit(
        f"找不到自举账号口令。设 GIMBAL_SB_PASSWORD，或把 {DOTENV_PATH.name} 补上"
        f"（模板见 .env.example）。"
    )


RUN_POLL_INTERVAL_SEC = 2.0
RUN_TIMEOUT_SEC = 180.0
TERMINAL_STATES = {"done", "failed", "canceled"}


def load_cases(path: Path) -> list[dict]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    return doc["cases"]


def _login(username: str, password: str) -> Platform:
    _, body = Platform(BASE_URL).post(
        "/api/auth/login", {"username": username, "password": password}
    )
    return Platform(BASE_URL, body["access_token"])


def _bootstrap_account(pause: bool = True) -> tuple[Platform, str, str]:
    """拿一个可用的自举账号（admin），优先复用环境变量里已提权的那个。

    新注册用户一律是 member（`app/routers/auth.py` 的 register 只在库里
    没用户时才给 admin），而每域用例要打 /api/users/roster 等需要管理员
    权限的端点。所以首次注册后必须停一下让人提权；提权好的账号写进
    GIMBAL_SB_USERNAME / GIMBAL_SB_PASSWORD，之后每次跑都直接复用，不再
    往平台里塞新账号。
    """
    existing = os.environ.get("GIMBAL_SB_USERNAME", "").strip()
    if existing:
        password = _resolve_password()
        return _login(existing, password), existing, password

    # 平台 app/schemas/auth.py 的 RegisterIn.username 是 `^[A-Za-z0-9_]+$` ——
    # 不含连字符。用 `sb_` 前缀，别用 `sb-`。
    username = f"sb_{uuid.uuid4().hex[:10]}"
    password = _resolve_password()
    Platform(BASE_URL).post(
        "/api/auth/register",
        {"username": username, "display_name": "gimbal-bootstrap", "password": password},
    )

    if pause:
        print()
        print("=" * 60)
        print(f"  自举账号已注册：{username}")
        print("  请到平台把该账号的权限改为管理员，改完回车继续。")
        print("=" * 60)
        print(f"  口令：{password}")
        print("=" * 60)
        input()

    return _login(username, password), username, password


def _cleanup(
    client: Platform,
    scenario_id: str | None,
    dataset_id: str | None,
    scheme_id: str | None,
) -> None:
    for path in (
        f"/api/scenarios/{scenario_id}/run-schemes/{scheme_id}" if scheme_id else None,
        f"/api/scenarios/{scenario_id}/data-sets/{dataset_id}" if dataset_id else None,
        f"/api/scenarios/{scenario_id}" if scenario_id else None,
    ):
        if not path:
            continue
        try:
            client.delete(path)
        except PlatformError as exc:
            print(f"  清理失败 {path}: {exc}", file=sys.stderr)


def _new_scenario(client: Platform, definition: dict) -> str:
    """建场景。orchestration 必须与 definition.steps 严格同序同长。"""
    _, created = client.post(
        "/api/scenarios",
        {
            "definition": definition,
            "orchestration": {
                "steps": [
                    {"enabled": True, "name": f"s{i}"}
                    for i in range(len(definition["steps"]))
                ],
                "resourceMeta": {},
            },
            "assertion_registry": {"entries": []},
        },
    )
    return (created or {}).get("scenarioId") or definition["scenarioId"]


def _poll(client: Platform, execution_id: Any, result: dict) -> None:
    deadline = time.monotonic() + RUN_TIMEOUT_SEC
    ex: dict = {}
    while time.monotonic() < deadline:
        _, ex = client.get(f"/api/executions/{execution_id}")
        if (ex or {}).get("status") in TERMINAL_STATES:
            break
        time.sleep(RUN_POLL_INTERVAL_SEC)
    result["status"] = (ex or {}).get("status")
    result["total"] = (ex or {}).get("totalRuns")
    result["ok"] = result["status"] == "done"


def _render(case: dict, sb_username: str, sb_password: str, scenario_id: str) -> dict:
    """把 ${...} 替成编排期已知的真实值。"""
    subs = {
        "sb.username": sb_username,
        "sb.password": sb_password,
        "sb.scenario_id": scenario_id,
    }

    def walk(v):
        if isinstance(v, str):
            for k, r in subs.items():
                v = v.replace("${" + k + "}", r)
            return v
        if isinstance(v, dict):
            return {k: walk(x) for k, x in v.items()}
        if isinstance(v, list):
            return [walk(x) for x in v]
        return v

    return walk(case)


def run_case(
    case: dict,
    client: Platform,
    sb_username: str,
    *,
    sb_password: str = "",
    run_token: str = "",
) -> dict:
    result: dict[str, Any] = {
        "id": case["id"],
        "name": case.get("name", ""),
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "error": None,
        "failures": [],
    }
    scenario_id = dataset_id = scheme_id = None
    try:
        definition = build_definition(
            case, sb_username=sb_username, sb_password=sb_password, run_token=run_token
        )
        scenario_id = _new_scenario(client, definition)
        rendered = _render(case, sb_username, sb_password, scenario_id)

        for step in rendered["steps"]:
            path, method = step["path"], step["method"]
            status, body = client.request(method, path, step.get("body") or None)
            scratch = {"call": {"response": {"status": status, "body": body}}}

            for a in step.get("asserts", []):
                if evaluate(scratch, a):
                    result["passed"] += 1
                else:
                    result["failed"] += 1
                    result["failures"].append(
                        f"{method} {path} :: {a['target']} {a['operator']} "
                        f"{a.get('expected')!r} —— 实得 {body!r:.200}"
                    )

            if path.endswith("/data-sets"):
                dataset_id = (body or {}).get("datasetId") or (body or {}).get("id")
            elif path.endswith("/run-schemes"):
                scheme_id = (body or {}).get("schemeId") or (body or {}).get("id")
            elif path == "/api/runs" and body:
                result["executionId"] = body.get("executionId")
                _poll(client, body.get("executionId"), result)
    except PlatformError as exc:
        result["error"] = f"HTTP {exc.status}: {exc.payload}"
    except Exception as exc:  # noqa: BLE001 — 编排器要吞掉一切并汇报
        result["error"] = repr(exc)
    finally:
        _cleanup(client, scenario_id, dataset_id, scheme_id)
    return result


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="在平台上编排并运行自举用例")
    parser.add_argument("--cases", default=str(Path(__file__).resolve().parents[1] / "cases"))
    parser.add_argument(
        "--no-pause", action="store_true",
        help="注册后不等人工提权，直接以 member 身份跑（域用例会 403）",
    )
    args = parser.parse_args()

    client, sb_username, sb_password = _bootstrap_account(pause=not args.no_pause)
    print(f"自举账号: {sb_username}")

    cases: list[dict] = []
    for path in sorted(Path(args.cases).glob("*.yaml")):
        cases.extend(load_cases(path))
    print(f"共 {len(cases)} 条用例\n")

    run_token = uuid.uuid4().hex[:6]
    results = [
        run_case(c, client, sb_username, sb_password=sb_password, run_token=run_token)
        for c in cases
    ]
    for r in results:
        mark = "OK " if not r["error"] and not r["failed"] and r.get("ok", True) else "FAIL"
        print(f"[{mark}] {r['id']:5} {r['name']}"
              + (f"  {r['error']}" if r["error"] else ""))

    failed = sum(1 for r in results if r["error"] or r["failed"])
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
