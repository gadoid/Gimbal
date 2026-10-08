"""P0-03:跨模块契约测试 — 真 plate /convert → 真 run_injection → 真 gimbal。

与 test_run_injectable_wire 的差别:plate 腿**不用 PlateMock echo**,
挂载真实 plate 应用(进程内 ASGI + lifespan 自动注册 fin 端点目录),
convert 产物必须被真 gimbal CLI 执行通过 —— 三侧契约(call 形态、
断言路径、注入物化)任何一侧漂移都会红。

覆盖(P0-03 验收):
  1. HTTP 单场景成功(GET,断言过);
  2. 断言失败(expected 错值 → 行 failed);
  3. Assign 注入生效(注入条目 value 是该字段唯一供值方 → 线上实收);
  4. carry 注入生效(值表带入 999,条目偏离 261 压过它 → 线上实收 261)。

引擎可用性:GIMBAL_BIN 或可导入 gimbal(``-m gimbal``),否则 skip
(与 wire 测试同款守卫;缺引擎的环境不红)。
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.services import plate_client
from app.services.endpoint_declarations import _reset_declared_paths_cache

_REPO = Path(__file__).resolve().parents[4]  # backend/tests → 仓库根
for _p in (_REPO / "src",):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from gimbal_plate.http.app import create_app as _create_plate_app  # noqa: E402

_EXEC_FINAL = {"done", "failed", "canceled"}


def _engine_available() -> bool:
    if settings.GIMBAL_BIN:
        return Path(settings.GIMBAL_BIN).exists()
    return importlib.util.find_spec("gimbal") is not None


def _engine_prefix() -> list[str] | None:
    if settings.GIMBAL_BIN:
        return [settings.GIMBAL_BIN] if Path(settings.GIMBAL_BIN).exists() else None
    if importlib.util.find_spec("gimbal") is not None:
        return [sys.executable, "-m", "gimbal"]
    return None


pytestmark = pytest.mark.skipif(
    not _engine_available(), reason="真 gimbal 引擎不可用(GIMBAL_BIN / importable gimbal)"
)


class _StubSut(BaseHTTPRequestHandler):
    """被测系统桩:GET/POST 都回 {"code":"0"},记录到达的 body。"""
    protocol_version = "HTTP/1.1"
    hits: list[dict] = []

    def _respond(self, body: dict | None) -> None:
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n).decode("utf-8", "replace") if n else ""
        try:
            type(self).hits.append(json.loads(raw) if raw else {})
        except json.JSONDecodeError:
            type(self).hits.append({"_raw": raw, "_path": self.path})
        out = json.dumps({"code": "0", "msg": "ok"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def do_GET(self):  # noqa: N802
        self._respond(None)

    def do_POST(self):  # noqa: N802
        self._respond(None)

    def log_message(self, *a):  # noqa: D102
        pass


@pytest.fixture
def stub_sut():
    _StubSut.hits = []
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _StubSut)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()
        srv.server_close()


@pytest_asyncio.fixture
async def real_plate():
    """进程内真实 plate:lifespan 注册 fin 目录,ASGI 挂到 plate_client。

    覆盖 conftest 的 autouse MockTransport 默认(显式请求的同 scope 夹具
    后实例化,后者胜)。
    """
    _reset_declared_paths_cache()
    plate_client._reset_full_cache_for_test()
    app = _create_plate_app()
    async with app.router.lifespan_context(app):
        plate_client.set_client_for_tests(AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://plate-real",
        ))
        try:
            yield
        finally:
            plate_client.set_client_for_tests(None)


@pytest.fixture
def real_engine(monkeypatch):
    from app.services import gimbal_launcher as gl
    prefix = _engine_prefix()
    assert prefix is not None
    monkeypatch.setattr(gl, "_base_argv", lambda: list(prefix))


@pytest.fixture
def isolated_data(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)   # Path(生产侧 DATA_DIR / "runs")
    return tmp_path


def _step_get_cost() -> dict:
    return {
        "id": "s1", "kind": "step",
        "call": {"kind": "call", "protocol": "http", "service": "fin-service",
                 "method": "GET", "path": "/api/home/cost/amountCostList",
                 "view_hints": {"endpoint_id": "fin.cost.amount_list"}},
        "request": {"kind": "request", "body": {}},
        "strategy": [{"kind": "assertion", "target": "$.call.response.body.code",
                      "operator": "eq", "expected": "0"}],
    }


def _step_settlement(body: dict, strategies: list | None = None) -> dict:
    return {
        "id": "s1", "kind": "step",
        "call": {"kind": "call", "protocol": "http", "service": "fin-service",
                 "method": "POST", "path": "/api/v1/fin/settlement/orders",
                 "headers": {"Content-Type": "application/json"},
                 "view_hints": {"endpoint_id": "fin.settlement.create_order"}},
        "request": {"kind": "request", "body": body},
        "strategy": strategies
        if strategies is not None
        else [{"kind": "assertion", "target": "$.call.response.body.code",
               "operator": "eq", "expected": "0"}],
    }


async def _post_scenario(client, token: str, draft: dict) -> None:
    r = await client.post("/api/scenarios", headers=token, json=draft)
    assert r.status_code in (200, 201), r.text


async def _run_and_wait(client, token: str, payload: dict,
                        data_root: "Path | None" = None) -> dict:
    r = await client.post("/api/runs", headers=token, json=payload)
    assert r.status_code == 201, r.text
    exec_id = r.json()["executionId"]
    ex = None
    for _ in range(600):
        ex = (await client.get(f"/api/executions/{exec_id}", headers=token)).json()
        if ex["status"] in _EXEC_FINAL:
            return ex
        await asyncio.sleep(0.1)
    rows = (await client.get(f"/api/executions/{exec_id}/rows",
                             headers=token)).json()["items"]
    diag = {"execution": ex, "rows": rows}
    if data_root is not None:
        for c in sorted(data_root.glob("runs/cases/*/*/")):
            diag[str(c)] = sorted(p.name for p in c.iterdir())
            engine_log = c / "engine.log"
            if engine_log.exists():
                diag["engine.log.tail"] = engine_log.read_text(
                    encoding="utf-8", errors="replace")[-2000:]
    pytest.fail(f"execution 未在 60s 内到终态: {json.dumps(diag, ensure_ascii=False, default=str)[:4000]}")


async def _rows(client, token: str, exec_id: int) -> list[dict]:
    r = await client.get(f"/api/executions/{exec_id}/rows", headers=token)
    assert r.status_code == 200, r.text
    return r.json()["items"]


async def test_contract_http_single_scenario_pass(
    client, real_plate, real_engine, stub_sut, isolated_data
):
    """①HTTP 单场景成功:真 plate convert 的 call 产物被真 gimbal 执行通过。"""
    from .helpers import make_draft
    from .test_scenario_visibility_and_copy import _member

    bob = await _member(client, "bob")
    await _post_scenario(client, bob, make_draft(
        steps=[_step_get_cost()],
        description="contract pass", author="t", owner="bob", tags=[],
        version="1", createTime="2026-09-28T00:00:00Z", expire=False,
        requirementRef=[],
    ))

    ex = await _run_and_wait(client, bob, {
        "scenarioId": "sc-test", "dataSetIds": [],
        "serviceBindings": {"fin-service": {"url": stub_sut}},
    }, data_root=isolated_data)
    assert ex["status"] == "done", ex
    assert ex["passed"] == 1 and ex["failed"] == 0
    assert len(_StubSut.hits) == 1                      # 真引擎发出去了

    # 契约守卫:convert 产物是 call 形态(不是 api 糖)——导出器若回退
    # api 渲染,gimbal(已删 api 糖)会 exit 2,上面就红了;这里再显式钉。
    case_files = sorted(isolated_data.glob("runs/cases/*/*/case.json"))
    assert len(case_files) == 1, case_files
    step = json.loads(case_files[0].read_text(encoding="utf-8"))["steps"][0]
    assert "call" in step and "api" not in step, step


async def test_contract_assertion_failure_visible(
    client, real_plate, real_engine, stub_sut, isolated_data
):
    """②断言失败:expected 错值 → 行 failed、execution failed=1。"""
    from .helpers import make_draft
    from .test_scenario_visibility_and_copy import _member

    bob = await _member(client, "bob")
    bad = _step_get_cost()
    bad["strategy"][0]["expected"] = "1"                # 桩永远回 "0"
    await _post_scenario(client, bob, make_draft(
        steps=[bad],
        description="contract fail", author="t", owner="bob", tags=[],
        version="1", createTime="2026-09-28T00:00:00Z", expire=False,
        requirementRef=[],
    ))

    ex = await _run_and_wait(client, bob, {
        "scenarioId": "sc-test", "dataSetIds": [],
        "serviceBindings": {"fin-service": {"url": stub_sut}},
    }, data_root=isolated_data)
    # 行级断言失败 → execution 终态 failed(有失败行的既有口径)
    assert ex["status"] == "failed", ex
    assert ex["failed"] == 1 and ex["passed"] == 0
    rows = await _rows(client, bob, ex["id"])
    assert rows[0]["status"] == "failed"
    assert len(_StubSut.hits) == 1                       # 请求确实到了


async def test_contract_assign_injection_on_the_wire(
    client, real_plate, real_engine, stub_sut, isolated_data
):
    """③Assign 注入生效:body 未供 remark,注入条目是唯一供值方
    (归因唯一——真 plate 的声明面把 $.remark 判为可注入)。"""
    from .helpers import make_draft
    from .test_scenario_visibility_and_copy import _member
    from app.services.endpoint_declarations import _reset_declared_paths_cache

    _reset_declared_paths_cache()
    bob = await _member(client, "bob")
    draft = make_draft(
        steps=[_step_settlement({"order_id": "O1", "amount": "10",
                                 "currency": "CNY"})],
        description="contract assign", author="t", owner="bob", tags=[],
        version="1", createTime="2026-09-28T00:00:00Z", expire=False,
        requirementRef=[],
    )
    draft["assertion_registry"] = {"entries": [{
        "id": "inj-remark", "name": "remark 偏离",
        "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.remark"},
        "value": 261, "asserts": []}]}
    await _post_scenario(client, bob, draft)

    ex = await _run_and_wait(client, bob, {
        "scenarioId": "sc-test", "dataSetIds": [],
        "injectionEntryIds": ["inj-remark"],
        "serviceBindings": {"fin-service": {"url": stub_sut}},
    }, data_root=isolated_data)
    assert ex["status"] == "done", ex
    rows = await _rows(client, bob, ex["id"])
    assert rows[0]["injectionId"] == "inj-remark"        # 条目未被 skip
    assert len(_StubSut.hits) == 1
    assert _StubSut.hits[0].get("remark") == 261         # Assign 落到线上


async def test_contract_carry_injection_overrides_carried_value(
    client, real_plate, real_engine, stub_sut, isolated_data
):
    """④carry 注入生效:真 plate 声明($.remark state=carry)+ 值表带入 999,
    条目偏离 261 在线上压过带入值(交给 CLI 的 case 里是 999)。"""
    from .helpers import make_draft
    from .test_scenario_visibility_and_copy import _member
    from app.core import db as _db_module
    from app.services import carry_store
    from app.services.endpoint_declarations import _reset_declared_paths_cache

    _reset_declared_paths_cache()
    bob = await _member(client, "bob")
    draft = make_draft(
        steps=[_step_settlement({"order_id": "O1", "amount": "10",
                                 "currency": "CNY"})],
        description="contract carry", author="t", owner="bob", tags=[],
        version="1", createTime="2026-09-28T00:00:00Z", expire=False,
        requirementRef=[],
    )
    draft["assertion_registry"] = {"entries": [{
        "id": "inj-remark", "name": "remark 偏离",
        "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.remark"},
        "value": 261, "asserts": []}]}
    await _post_scenario(client, bob, draft)

    # 服务在真 plate 目录(fin-service 由 fin 端点注册产生)→ carry 面可用;
    # 值表种 999(≠ 偏离值 261),覆盖才有观察面。
    async with _db_module.SessionLocal() as db:
        await carry_store.put_bindings(
            db, "fin-service", {"$.remark": "999"},
            updated_by_id=None, updated_by_name="bob")
        await db.commit()

    ex = await _run_and_wait(client, bob, {
        "scenarioId": "sc-test", "dataSetIds": [],
        "injectionEntryIds": ["inj-remark"],
        "serviceBindings": {"fin-service": {"url": stub_sut}},
    }, data_root=isolated_data)
    assert ex["status"] == "done", ex

    # 交给 CLI 的 case:平台 carry 确实把 999 带进了 body
    case_files = sorted(isolated_data.glob("runs/cases/*/*/case.json"))
    assert len(case_files) == 1, case_files
    body = json.loads(case_files[0].read_text(encoding="utf-8")
                      )["steps"][0]["request"]["body"]
    assert str(body.get("remark")) == "999", body

    # 线上:条目的偏离值压过带入值
    assert len(_StubSut.hits) == 1
    assert _StubSut.hits[0].get("remark") == 261
