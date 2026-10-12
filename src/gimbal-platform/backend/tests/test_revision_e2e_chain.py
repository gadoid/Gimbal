"""W12(A-7/P1.7,2026-10-12):按修订编排→保存→执行→执行详情 端到端
同修订链路 + 版本模型不变量 I-1 回归。

真 plate 进程内起(httpx ASGITransport + lifespan_context,同
test_run_injection 的真 convert 先例);最小 fin 系统走
tests/plate/_release_fx 同款规范形模板,git 临时仓库 + 演练构件根,
冻结出 fin@1.0#1。平台侧走全 API 链(POST /api/scenarios →
POST /api/runs → GET /api/executions/{id})。

拦的缺陷形态:「单测全绿、链路不通」—— 读侧丢字段(meta.plate 水合)、
缓存键错配、修订快照与 working 树串味。I-1 断言:plate 冻结 1.0#2
(结构性变更:path 改写)后,钉定 1.0#1 的场景再次执行,plate_pins
不动、引擎输入 case.json 与首次逐键一致 —— plate 发修订不改变任何
场景的执行。
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import httpx
import pytest

# ── 最小 fin 系统(规范形模板,抄 tests/plate/_release_fx.py)────────
SYSTEM_MD = """---
type: system
system: fin
line: '1.0'
---

# fin

```gimbal:system
review: reviewed
name: fin-service
title: fin-service
version: 1.0.0
```
"""

ENDPOINT_MD = """---
id: fin.a.{name}
type: endpoints
system: fin
---

# {name}

```gimbal:endpoint
review: reviewed
id: fin.a.{name}
system: fin
service: fin-service
name: {name}
binding:
  protocol: http
  method: GET
  path: {path}
responses:
  '200': {{}}
```
"""


def _git(cwd: Path, *args: str) -> str:
    r = subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.name=e2e", "-c", "user.email=e@e",
         *args],
        capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, f"git {args} 失败: {r.stderr}"
    return r.stdout.strip()


def _write_endpoint(fin: Path, path: str) -> None:
    fin.joinpath("endpoints", "fin.a.get.md").write_text(
        ENDPOINT_MD.format(name="get", path=path),
        encoding="utf-8", newline="\n")


def _release(fin: Path, art: Path):
    from gimbal_plate.release.release import release_system

    r = release_system(fin, artifacts_root=art, signed_by="e2e")
    assert r.success, r.message
    return r


def _strip_volatile(node: Any) -> Any:
    """case.json 深比较前剥运行期易变键(执行 id/报告路径/时间戳)。"""
    if isinstance(node, dict):
        return {k: _strip_volatile(v) for k, v in node.items()
                if k not in {"executionId", "execution_id", "runId", "run_id",
                             "reportDir", "report_dir", "startedAt",
                             "started_at", "timestamp"}}
    if isinstance(node, list):
        return [_strip_volatile(x) for x in node]
    return node


async def test_pinned_chain_reads_same_revision_and_i1_holds(
        client, tmp_path, monkeypatch):
    from .helpers import make_draft as _draft, wait_until as _wait
    from .test_run_m1_capabilities import _patch_launch_capture
    from .test_scenario_visibility_and_copy import _member

    # ── 夹具面:git 临时仓库(fin@1.0 初始树) + 演练构件根 ──────────
    repo = tmp_path / "repo"
    fin = repo / "systems" / "fin"
    fin.joinpath("endpoints").mkdir(parents=True)
    fin.joinpath("system.md").write_text(SYSTEM_MD, encoding="utf-8",
                                         newline="\n")
    _write_endpoint(fin, "/a")
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    art = tmp_path / "art"
    art.mkdir()
    assert _release(fin, art).revision == "1.0#1"

    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    from gimbal_plate.http.app import create_app
    from app.services import plate_client

    monkeypatch.setenv("PLATE_SYSTEMS_PATH", str(repo / "systems"))
    monkeypatch.setenv("PLATE_ARTIFACTS_PATH", str(art))
    app = create_app()
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://plate-e2e",
        ) as real:
            plate_client.set_client_for_tests(real)
            try:
                bob = await _member(client, "e2ebob")
                steps = [{
                    "kind": "step", "endpoint": "fin.a.get",
                    "call": {"kind": "call", "protocol": "http",
                             "service": "fin-service", "method": "GET",
                             "path": "/a", "headers": {}},
                    "request": {"kind": "request", "body": {}},
                    "strategy": [],
                }]

                # ① 按修订编排 → 保存(meta.plate 钉 fin@1.0#1)
                draft = _draft(steps=steps, plate={"fin": "1.0#1"})
                r = await client.post("/api/scenarios", headers=bob,
                                      json=draft)
                assert r.status_code in (200, 201), r.text

                # ② 执行:resolve→pins→convert→引擎输入
                r = await client.post("/api/runs", headers=bob, json={
                    "scenarioId": "sc-test", "dataSetIds": []})
                assert r.status_code == 201, r.text
                eid = r.json()["executionId"]
                await _wait(lambda: len(cases) >= 1)

                # ③ 执行详情:台账面读到的就是编排时声明的修订
                d = (await client.get(f"/api/executions/{eid}",
                                      headers=bob)).json()
                assert d["plate_pins"] == {"fin": "1.0#1"}, d.get("plate_pins")
                # 钉定 + 全评审(reviewed 块)+ 无 external → 入库标准达标
                assert d["baseline_eligible"] is True
                assert d["baseline_block"] is None
                # 引擎输入的调用面 = 1.0#1 快照(path /a)
                assert cases[0]["steps"][0]["call"]["path"] == "/a"

                # ④ I-1:冻结 1.0#2(结构性变更:path /a → /a2)后,
                #    钉定 1.0#1 的场景再次执行 —— 修订不动、输入不变
                _write_endpoint(fin, "/a2")
                _git(repo, "add", "-A")
                _git(repo, "commit", "-q", "-m", "endpoint path /a2")
                assert _release(fin, art).revision == "1.0#2"

                r = await client.post("/api/runs", headers=bob, json={
                    "scenarioId": "sc-test", "dataSetIds": []})
                assert r.status_code == 201, r.text
                eid2 = r.json()["executionId"]
                await _wait(lambda: len(cases) >= 2)

                d2 = (await client.get(f"/api/executions/{eid2}",
                                       headers=bob)).json()
                assert d2["plate_pins"] == {"fin": "1.0#1"}, (
                    "I-1 违例:plate 发 1.0#2 改变了钉定场景的执行修订")
                assert _strip_volatile(cases[1]) == _strip_volatile(cases[0]), (
                    "I-1 违例:plate 发 1.0#2 改变了引擎输入(case.json)")
            finally:
                plate_client.set_client_for_tests(None)
