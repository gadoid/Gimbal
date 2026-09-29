"""自举编排器：账号 → 建场景 → 发起运行 → 轮询 → 读回 gimbal 判定 → 清理。

编排器**不执行**用例里的 HTTP 步骤 —— 那是 gimbal 的活。它只负责把场景
建出来、让它在平台上跑起来、把引擎的判定读回来。全程以普通用户身份走平台
公开 HTTP API，不碰任何内部接口。
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import yaml

from gimbal_bootstrap.case_builder import build_definition
from gimbal_bootstrap.platform_client import Platform, PlatformError

BASE_URL = "http://127.0.0.1:8000"
# 自举账号口令不在源码里 —— 用户要登进平台检查，固定口令必须好打，
# 但账号是管理员，不该把口令提交进仓库。真值放 gitignore 掉的 .env
# （模板见同目录 .env.example），进程环境变量优先于它。
DOTENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def _resolve_env(key: str) -> str:
    """进程环境变量优先，其次本机 .env（gitignore 掉的）。"""
    from_env = os.environ.get(key, "").strip()
    if from_env:
        return from_env
    if DOTENV_PATH.is_file():
        for line in DOTENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip().strip("\"'")
    return ""


def _resolve_password() -> str:
    value = _resolve_env("GIMBAL_SB_PASSWORD")
    if not value:
        raise SystemExit(
            f"找不到自举账号口令。设 GIMBAL_SB_PASSWORD，或把 {DOTENV_PATH.name} 补上"
            f"（模板见 .env.example）。"
        )
    return value


RUN_POLL_INTERVAL_SEC = 2.0
RUN_TIMEOUT_SEC = 180.0
TERMINAL_STATES = {"done", "failed", "canceled"}


def load_cases(path: Path) -> list[dict]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    return doc["cases"]


CREDENTIAL_ALIAS = "sb"
CREDENTIAL_URL = f"{BASE_URL}/api/auth/login"


def _ensure_credential(client: Platform, username: str, password: str) -> str | None:
    """在平台凭证池里备一条自举账号的凭证，返回它的 id（供跑完退役）。

    场景步骤头写的是 `${auth.sb.token}`（平台 auth_ref_scan 按 alias 扫描），
    调度时从池里解析出这条凭证、塞进 config.users.sb，引擎再拿 auth.url
    现登一次换 token。池里没有这条，alias 解析不出来，gimbal 直接
    gimbal_rejected。

    池里存的是**口令**不是 token —— token 有有效期，存进去很快就废。

    幂等：`AuthCredential` 对 (owner_id, alias) 有唯一约束，两个终端同时跑
    会抢着建同一条 alias，第二个吃 409。那不是错误，是「别人先建好了」，
    回头读出来改掉就行。
    """
    _, listing = client.get("/api/auths")
    body = {
        "url": CREDENTIAL_URL,
        "username": username,
        "password": password,
        "token_type": "Bearer",
    }

    def _patch_existing(items) -> str | None:
        for item in (items or {}).get("items") or []:
            if item.get("alias") == CREDENTIAL_ALIAS:
                client.request("PATCH", f"/api/auths/{item['id']}", body)
                return item.get("id")
        return None

    patched = _patch_existing(listing)
    if patched:
        return patched
    try:
        _, created = client.post("/api/auths", {"alias": CREDENTIAL_ALIAS, **body})
        return (created or {}).get("id")
    except PlatformError as exc:
        if exc.status != 409:
            raise
        # 有人抢先建了。重新读一遍按 id 改，不跟对方抢。
        _, listing = client.get("/api/auths")
        patched = _patch_existing(listing)
        if not patched:
            raise
        return patched


def _retire_credential(client: Platform, credential_id: str | None) -> None:
    """删掉这一轮用过的那条凭证。

    池里存的是**管理员口令**，而凭证没有 TTL —— 跑完不删等于把 admin 明文
    长期留在平台数据库里。跑之前则必须有它：场景头写的是
    `${auth.sb.token}`，池里没这条 alias 解析不出来，引擎直接
    gimbal_rejected。
    """
    if not credential_id:
        return
    try:
        client.delete(f"/api/auths/{credential_id}")
    except PlatformError as exc:
        print(f"  清理凭证失败 /api/auths/{credential_id}: {exc}", file=sys.stderr)


def _remember_username(username: str) -> None:
    """把刚注册的账号名写回 .env，下次重跑直接复用，不用每次手工 export。

    只追加/替换 GIMBAL_SB_USERNAME 这一行，别的行（口令、注释）原样留着。
    """
    line = f"GIMBAL_SB_USERNAME={username}"
    existing = (
        DOTENV_PATH.read_text(encoding="utf-8").splitlines()
        if DOTENV_PATH.is_file() else []
    )
    kept = [
        l for l in existing
        if l.strip() and not l.strip().startswith("GIMBAL_SB_USERNAME=")
    ]
    DOTENV_PATH.write_text("\n".join(kept + [line]) + "\n", encoding="utf-8")


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
    existing = _resolve_env("GIMBAL_SB_USERNAME")
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

    # 先确认真的登得进去，再把账号名写回 .env。反过来的话，register 成功
    # 但 login 401 时账号名照样进了 .env，之后每次重跑都走「复用已有账号」
    # 分支，永远卡在这个登不上的账号上。
    client = _login(username, password)
    try:
        _remember_username(username)
    except OSError as exc:
        # .env 只读/写不了不该让已经注册好的账号白注册。下次记得手工
        # export GIMBAL_SB_USERNAME=...，或者直接看这行提示。
        print(f"  账号名没能写回 {DOTENV_PATH.name}（{exc}）", file=sys.stderr)
        print(f"  记住它，下次 export GIMBAL_SB_USERNAME={username}", file=sys.stderr)

    return client, username, password


def _retire_throwaway(client: Platform, username: str | None) -> None:
    """把这一轮注册的一次性账号删掉。

    不删的话每次重跑都往平台里堆一个死账号，而且它在 execution_snapshots
    里还留着一份明文口令 —— 账号没了那份口令才失效。
    自举账号本身绝不能删。
    """
    if not username:
        return
    try:
        _, listing = client.get("/api/users")
    except PlatformError as exc:
        print(f"  查一次性账号失败 {username}: {exc}", file=sys.stderr)
        return
    for item in (listing or {}).get("items") or []:
        if item.get("username") == username and item.get("id"):
            try:
                client.delete(f"/api/users/{item['id']}")
            except PlatformError as exc:
                print(f"  清理失败 /api/users/{item['id']}: {exc}", file=sys.stderr)


def _cleanup(
    client: Platform,
    scenario_id: str | None,
    dataset_id: str | None,
    scheme_id: str | None,
) -> None:
    for path in (
        f"/api/scenarios/{scenario_id}/run-schemes/{scheme_id}" if scheme_id else None,
        f"/api/data-sets/{dataset_id}" if dataset_id else None,
        f"/api/scenarios/{scenario_id}" if scenario_id else None,
    ):
        if not path:
            continue
        try:
            client.delete(path)
        except PlatformError as exc:
            print(f"  清理失败 {path}: {exc}", file=sys.stderr)


def _aligned_orchestration(definition: dict) -> dict:
    """orchestration 必须与 definition.steps 严格同序同长。"""
    return {
        "steps": [
            {"enabled": True, "name": f"s{i}"} for i in range(len(definition["steps"]))
        ],
        "resourceMeta": {},
    }


def _new_scenario(client: Platform, definition: dict) -> str:
    _, created = client.post(
        "/api/scenarios",
        {
            "definition": definition,
            "orchestration": _aligned_orchestration(definition),
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


def _dispatch(client: Platform, scenario_id: str) -> Any:
    """发起一次运行。步骤执行和断言求值都在 gimbal 那边发生。"""
    _, body = client.post(
        "/api/runs", {"scenarioId": scenario_id, "nRuns": 1, "parallel": 1}
    )
    return (body or {}).get("executionId")


def _read_gimbal_result(client: Platform, execution_id: Any, result: dict) -> None:
    """读 gimbal 的判定结果。

    真相源是每个 case 目录下的 result.json —— 断言是引擎求的，编排器不重复
    求值一遍（那才是"自己另写一套 runner"）。行状态里的 gimbal_rejected
    表示引擎连场景都没接受，同样算失败。
    """
    _, rows = client.get(f"/api/executions/{execution_id}/rows")
    for row in (rows or {}).get("items") or []:
        case_dir, row_status = row.get("caseDir"), row.get("status")
        if row_status == "gimbal_rejected":
            result["failed"] += 1
            result["failures"].append(f"gimbal 拒绝接受该场景（{case_dir}）")
            continue
        if not case_dir:
            continue
        _, blob = client.request(
            "GET",
            f"/api/executions/{execution_id}/case-artifact"
            f"?case={case_dir}&file=result",
        )
        if isinstance(blob, str):
            try:
                blob = json.loads(blob)
            except ValueError:
                result["failed"] += 1
                result["failures"].append(f"{case_dir} result.json 解析失败")
                continue
        if not isinstance(blob, dict):
            continue
        result["passed"] += int(blob.get("passed") or 0)
        result["failed"] += int(blob.get("failed") or 0)
        result["skipped"] += int(blob.get("skipped") or 0)
        for detail in blob.get("details") or []:
            for step in detail.get("steps") or []:
                if step.get("status") == "failed":
                    result["failures"].append(
                        f"{detail.get('scenario_id')} {step.get('step_id')}: "
                        f"{step.get('error') or '失败'}（{step.get('error_phase')}）"
                    )


def run_case(
    case: dict,
    client: Platform,
    sb_username: str,
    *,
    sb_password: str = "",
    run_token: str = "",
    new_username: str = "",
    new_password: str = "",
    keep: bool = False,
) -> dict:
    """建场景 → 发起运行 → 读回 gimbal 的判定 → 清理。

    编排器**不执行**用例里的 HTTP 步骤 —— 那是 gimbal 的活。编排器只负责
    把场景建出来、让它跑起来、把引擎的判定读回来。

    `new_password` 是一次性账号的口令，跟管理员口令无关 —— 管理员口令不进
    definition（见 `build_definition` 的说明）。

    一次性账号**不在这里删**。它是按轮次的：T2 注册它、T3 拿同一个用户名
    口令去登录，每条用例各删一次的话，账号在第一条用例收工时就没了，后面
    拿它的用例必然 401。退役由 `main` 在所有用例跑完之后做一次。
    """
    result: dict[str, Any] = {
        "id": case["id"],
        "name": case.get("name", ""),
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "error": None,
        "failures": [],
    }
    scenario_id = None
    try:
        definition = build_definition(
            case,
            sb_username=sb_username,
            sb_password=sb_password,
            run_token=run_token,
            new_username=new_username,
            new_password=new_password,
        )
        scenario_id = _new_scenario(client, definition)
        execution_id = _dispatch(client, scenario_id)
        result["executionId"] = execution_id
        result["scenarioId"] = scenario_id
        _poll(client, execution_id, result)
        if result.get("status") in TERMINAL_STATES:
            _read_gimbal_result(client, execution_id, result)
    except PlatformError as exc:
        result["error"] = f"HTTP {exc.status}: {exc.payload}"
    except Exception as exc:  # noqa: BLE001 — 编排器要吞掉一切并汇报
        result["error"] = repr(exc)
    finally:
        # keep 是给人看的：场景建在平台上，不删的话人登进平台才看得到编排器
        # 到底写了什么。默认还是清掉，不往平台里堆垃圾。
        if not keep:
            _cleanup(client, scenario_id, None, None)
    return result


def _is_failure(result: dict) -> bool:
    """一条用例算不算失败 —— 屏幕上的 `[FAIL]` 和进程退出码必须是同一个判断。

    三条缺一不可：编排器自己炸了（error）、引擎判定有失败步骤（failed）、
    这次运行压根没跑到 done（ok）。少看一条就会「满屏 FAIL 却 exit 0」。
    """
    return bool(result.get("error")) or bool(result.get("failed")) \
        or not result.get("ok", True)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="在平台上编排并运行自举用例")
    parser.add_argument("--cases", default=str(Path(__file__).resolve().parents[1] / "cases"))
    parser.add_argument(
        "--no-pause", action="store_true",
        help="注册后不等人工提权，直接以 member 身份跑（域用例会 403）",
    )
    parser.add_argument(
        "--keep", action="store_true",
        help="跑完不删场景 —— 留给人登进平台查看用例会往平台上写了什么",
    )
    args = parser.parse_args()

    client, sb_username, sb_password = _bootstrap_account(pause=not args.no_pause)
    print(f"自举账号: {sb_username}")
    credential_id = _ensure_credential(client, sb_username, sb_password)

    # run_token / new_username / new_password 都是**按轮次**取值：scenario_id
    # 带用例 id，从它派生的名字会让 T2 注册的和 T3 登录的不是同一个账号。
    # 一次性口令当场生成，跟管理员口令无关。
    run_token = uuid.uuid4().hex[:6]
    new_username = "sb_" + uuid.uuid4().hex[:8]
    new_password = "Sb" + uuid.uuid4().hex[:12] + "9"
    try:
        cases: list[dict] = []
        for path in sorted(Path(args.cases).glob("*.yaml")):
            cases.extend(load_cases(path))
        print(f"共 {len(cases)} 条用例\n")

        results = [
            run_case(
                c,
                client,
                sb_username,
                run_token=run_token,
                new_username=new_username,
                new_password=new_password,
                keep=args.keep,
            )
            for c in cases
        ]
    finally:
        # 两样带明文口令的东西都在这里退役：一次性账号（按轮次的，T2 注册、
        # T3 登录，任何一条用例跑完就删都会让后面那条必然 401）和凭证池里
        # 那条存着管理员口令的凭证。放 finally 里 —— 中途崩了也照样删，
        # 否则一次异常就把 admin 明文留在平台库里。
        if new_username and new_username != sb_username:
            _retire_throwaway(client, new_username)
        _retire_credential(client, credential_id)
    for r in results:
        mark = "OK " if not _is_failure(r) else "FAIL"
        print(f"[{mark}] {r['id']:5} {r['name']}"
              + (f"  {r['error']}" if r["error"] else ""))
        for f in r["failures"]:
            print(f"         └─ {f}")
        if r.get("status"):
            print(f"         运行状态 status={r['status']} total={r.get('total')}")

    failed = sum(1 for r in results if _is_failure(r))
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
