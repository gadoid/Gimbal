"""CLI 进程退出码契约(2026-10-13 A-3):失败场景进程退出码 ≠ 0。

此前 ``raise typer.Exit(code=result.exit_code)`` 误放在
apply_multiplication 的 return 之后(死代码),pyflakes 守卫(dca24c6)
清理时删除而未挪回 launch() 末尾 —— ``gimbal run launch`` 无论执行
结果如何进程退出码恒 0,CLI/CI 用法全部失效(平台按 JSON 判定,不受
影响)。本测试走**真实子进程**(starter 全链),钉住:

* 失败场景(断言 fail)→ 退出码 1;
* 成功场景 → 退出码 0;
* ``-o json`` 同样遵守(stdout 是纯 JSON 报告)。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]

# 最小合法形态(与 tests/integration/test_server_run.py 的 LEGAL_TARGET
# 同构):服务指向不存在的本机端口(127.0.0.1:9)→ 响应状态非 200 →
# 断言失败 → exit_code=1。注意无断言的死调用**不算失败面**(实测
# passed)—— 失败面必须由断言显式表达。成功面 = 空步骤场景。
_FAIL_STEP = {
    "kind": "scenario",
    "scenarioId": "sc-cli-exit-fail",
    "meta": {"name": "exit-code-fail"},
    "config": {"services": {"dead": "http://127.0.0.1:9"},
               "users": {}, "timePolicy": {"kind": "record"}},
    "resource": {},
    "steps": [{
        "kind": "step",
        "call": {"protocol": "http", "service": "dead",
                 "method": "GET", "path": "/ping"},
        "request": {"kind": "request", "body": {}},
        "strategy": [{"kind": "assertion",
                      "target": "$.call.response.status",
                      "operator": "eq", "expected": "200"}],
    }],
}


def _run(payload: dict, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "gimbal", "run", "launch", "--inline",
         json.dumps(payload), "-o", "json", *extra],
        capture_output=True, text=True, encoding="utf-8",
        cwd=str(_REPO), timeout=120,
    )


@pytest.mark.parametrize("payload, expect", [
    pytest.param(_FAIL_STEP, 1, id="失败场景→退出码 1"),
    pytest.param({"kind": "scenario",
                  "scenarioId": "sc-cli-exit-ok",
                  "meta": {"name": "exit-code-ok"},
                  "config": {"services": {}, "users": {},
                             "timePolicy": {"kind": "record"}},
                  "resource": {}, "steps": []},
                 0, id="空场景(无失败面)→退出码 0"),
])
def test_launch_process_exit_code(payload: dict, expect: int) -> None:
    r = _run(payload)
    assert r.returncode == expect, (
        f"stdout: {r.stdout[-400:]} stderr: {r.stderr[-400:]}")
    # -o json 的 stdout 是执行报告(进程码与报告 exit_code 一致)
    report = json.loads(r.stdout)
    assert report["exit_code"] == r.returncode
