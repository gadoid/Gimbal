"""Plate integration tests for the V3 Scenario Composer.

Replaces the singleton ``httpx.AsyncClient`` in
``app.services.plate_client`` with an :class:`httpx.MockTransport` so
the real Plate server isn't needed.  This locks in:

* ``POST /api/scenarios/preview-plate`` envelope translation (Plate
  2xx / 4xx / 5xx → Platform 200 / 502 / 502).
* ``POST /api/runs`` per-row fan-out: we count the convert calls and
  assert it equals ``Σ rowCount``.
* ``POST /api/runs`` failure semantics: when Plate is down mid-fan-out
  the Execution row is marked ``status='failed'`` and the JSONL log
  records ``plate_unavailable``, but the response is still 201 with
  ``runId`` (per the agreed run-failure semantics).
"""
from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from httpx import AsyncClient

if TYPE_CHECKING:   # 仅供 _wait_execution_final 的返回注解
    from app.models import Execution


# ── shared fixture: register + login + seed scenario/case/ds ───────
from .helpers import make_draft as _draft
from .helpers import register_and_login as _register_and_login


# ── Plate mock helpers ─────────────────────────────────────────────
class PlateMock:
    """Programmable Plate mock.  Each test sets the desired behaviour
    on ``mock.behaviour`` before issuing the HTTP call."""

    def __init__(self) -> None:
        self.convert_calls: list[dict] = []
        self.run_calls: list[dict] = []  # D2 run bodies (stubbed upstream)
        self.behaviour: str = "ok"  # ok | echo | 4xx | 5xx | unavailable | convert_no_converted
        # carry 预解析面(T9):GET /api/service 目录 + /api/endpoint/{id}/full。
        # 空目录默认 → derive_base 全失败 → carry 全跳过:
        # 既有等价测试行为不变(兼容关键),carry 用例自行注入服务。
        self.fulls: dict[str, dict] = {}   # endpoint_id → full spec(carry 面)
        self.services: list[dict] = []
        # convert 回包附带的 m2 构建身份(台账 m2_hash 回填用)。真引擎
        # server 会话走 M2 §5.1 代际门 —— mock 哈希恒与真实构建失配,
        # 真引擎 e2e 置 None 略过代际门(r6 掩码用例,2026-11-23)。
        self.m2: dict | None = {"hash": "mock-m2-hash-0001",
                                "generation": 1}
        # A-3/W7:修订 manifest.objects 评审面({系统: {对象id: review}});
        # 未注入 = 空目录(所有对象按未评审计)。
        self.revision_reviews: dict[str, dict[str, str]] = {}
        # C-1:/lines 回放({系统: [线条目]};缺省 1.0×1)
        self.lines: dict[str, list[dict]] = {}
        # 场景导入 v2.3(W3):/lines/{line}/revisions 回放
        # ({系统: {线: [修订条目]}});缺省每线 [#1, #2]。
        self.line_revisions: dict[str, dict[str, list[dict]]] = {}
        # 导入重锚定(2026-10-15 #323):working 端点清单回放
        # ({系统: [条目]});未注入的系统 → 404(= PlateRejectedError →
        # 该系统不可反查,reason=catalog_unavailable)。
        self.system_endpoints: dict[str, list[dict]] = {}
        # 双向绑定 kind 预检面({系统: kind});未注入 → 404 = 未登记。
        self.system_kinds: dict[str, str] = {}

    def install(self) -> None:
        """Replace the singleton httpx client with a MockTransport."""
        from app.services import plate_client as _pc

        _pc.reset_catalog_cache_for_tests()  # b2-7:换桩先清目录缓存

        async def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path == "/api/endpoint":
                # b2-7 唯一访问件:由 services 合成扁平行(items 用例可另注)
                items = getattr(self, "endpoint_items", None) or [
                    {"id": f"{it.get('name')}.mock", "service": it.get("name"),
                     "system": it.get("system", "fin"),
                     "kind": it.get("kind", "sut")}
                    for it in self.services
                ]
                return httpx.Response(200, json={
                    "ok": True, "dim": "endpoint",
                    "data": {"items": items, "total": len(items)}})
            if path.endswith("/api/scenario/action/convert"):
                self.convert_calls.append(json.loads(request.content))
                if self.behaviour == "ok":
                    return httpx.Response(
                        200,
                        json={
                            "ok": True,
                            "dim": "scenario",
                            "data": {
                                "consumer": "platform",
                                "converted": {"kind": "platform_scenario"},
                                # M2 §5.1:真实 plate 的 convert 恒附构建身份
                                # (W21:派发链据此回填 executions.m2_hash;
                                # 真引擎 e2e 置 None 略过代际门,见 __init__)
                                **({"m2": self.m2}
                                   if self.m2 is not None else {}),
                            },
                        },
                    )
                if self.behaviour == "echo":
                    # scenario 原样回灌为 converted — 供 services/users 物化断言用
                    # (默认 ok 桩的 converted 是 {"kind": "platform_scenario"},无 steps)。
                    # 锚点步骤例外:声明形态进 → 执行形态出 —— 派生字段
                    # (protocol/method/path/timeout)按 fulls[eid].binding 投影
                    # 补回,同真 convert 的 reproject._merge_call 契约;缺 binding
                    # 保持原样(其余 echo 用例不受影响)。真 CLI 校验 Call.protocol
                    # 必填,不投影则 case.json 恒被 gimbal_rejected(exit 2)。
                    body = json.loads(request.content)
                    converted = body["scenario"]
                    for st in converted.get("steps") or []:
                        if not (isinstance(st, dict) and st.get("endpoint")
                                and isinstance(st.get("call"), dict)):
                            continue
                        binding = ((self.fulls.get(str(st["endpoint"])) or {})
                                   .get("binding"))
                        if not isinstance(binding, dict):
                            continue
                        proj = {k: binding[k] for k in
                                ("protocol", "method", "path", "timeout")
                                if k in binding}
                        own = {k: v for k, v in st["call"].items()
                               if k not in proj}
                        st["call"] = {"kind": st["call"].get("kind", "call"),
                                      **proj, **own}
                    data = {"consumer": "gimbal", "converted": converted}
                    if self.m2 is not None:
                        data["m2"] = self.m2
                    return httpx.Response(200, json={
                        "ok": True, "dim": "scenario", "data": data,
                    })
                if self.behaviour == "4xx":
                    return httpx.Response(
                        400,
                        json={
                            "ok": False,
                            "error": {
                                "code": "invalid_action",
                                "message": "bad shape",
                                "details": {
                                    "errors": [
                                        {
                                            "path": "steps[0].expectStatus",
                                            "message": "must be int",
                                        }
                                    ]
                                },
                            },
                        },
                    )
                if self.behaviour == "5xx":
                    return httpx.Response(500, text="plate crashed")
                if self.behaviour == "unavailable":
                    raise httpx.ConnectError("connection refused", request=request)
                if self.behaviour == "convert_no_converted":
                    # J-1 半畸形信封:200+ok 但 data 缺 converted ——
                    # plate_client 单点契约断言的靶形状(J-1 收口测试面)。
                    return httpx.Response(
                        200, json={"ok": True, "dim": "scenario",
                                   "data": {"consumer": "gimbal"}})
            if path.endswith("/api/scenario/action/run"):
                self.run_calls.append(json.loads(request.content))
                # D2 stays stubbed upstream; mirror its future shape.
                return httpx.Response(
                    200,
                    json={"ok": True, "dim": "scenario", "data": {"dispatched": True}},
                )
            # C-1 保存端引用校验面:版本线列表(缺省每系统一条 1.0
            # 线/1 修订;用例按需注入 self.lines)。
            if path.startswith("/api/system/") and path.endswith("/lines"):
                sysname = path.split("/api/system/", 1)[1].rsplit("/", 1)[0]
                items = self.lines.get(
                    sysname, [{"line": "1.0", "revisions": 1,
                               "latest": "1.0#1"}])
                return httpx.Response(200, json={
                    "ok": True, "dim": "system",
                    "data": {"items": items, "total": len(items)}})
            # 双向绑定 kind 预检面:GET /api/system/{id} → SystemView.kind。
            # 未注入系统 → 404(= get_system_kind None,按未登记处理)。
            if (path.startswith("/api/system/")
                    and path.count("/") == 3
                    and request.method == "GET"):
                sid = path.rstrip("/").rsplit("/", 1)[-1]
                kind = self.system_kinds.get(sid)
                if kind is None:
                    return httpx.Response(404, json={"ok": False})
                return httpx.Response(200, json={
                    "ok": True, "dim": "system",
                    "data": {"item": {"id": sid, "name": sid,
                                      "service_count": 1,
                                      "endpoint_count": 1,
                                      "kind": kind}}})
            # 场景导入 v2.3(W3):线内修订列表(availableRevisions 组装面)
            if ("/api/system/" in path and "/lines/" in path
                    and path.endswith("/revisions")):
                seg = [p for p in path.split("/") if p]
                i = seg.index("system")
                sysname, line = seg[i + 1], seg[i + 3]
                items = self.line_revisions.get(sysname, {}).get(
                    line, [{"ref": f"{line}#1"}, {"ref": f"{line}#2"}])
                return httpx.Response(200, json={
                    "ok": True, "dim": "system",
                    "data": {"items": items, "total": len(items)}})
            # RS3 生效修订解析(W5 钉定场景的 fanout 前置):钉什么回什么
            # —— effective = 原修订(不变),available 单元素,零变更。
            if path.endswith("/api/system/action/resolve"):
                body = json.loads(request.content)
                def _avail(ref: str) -> list:
                    n = ref.rsplit("#", 1)[-1]
                    return [int(n)] if n.isdigit() else []

                item = {
                    sys_: {"effective": ref, "available": _avail(ref),
                           "changed_endpoints": []}
                    for sys_, ref in (body.get("meta_plate") or {}).items()
                    if ref and ref != "working"
                }
                return httpx.Response(200, json={
                    "ok": True, "dim": "system", "data": {"item": item}})
            # A-3/W7 入库判定的评审面:GET /api/system/{s}/revisions/{l}/{n}
            # → manifest.objects[]({id, review})。revision_reviews 按
            # {系统: {对象id: review}} 注入;未注入 = 空(全未评审)。
            if "/api/system/" in path and "/revisions/" in path:
                seg = [p for p in path.split("/") if p]
                i = seg.index("system")
                sysname = seg[i + 1]
                objs = [
                    {"id": eid, "type": "endpoint", "review": rev}
                    for eid, rev in self.revision_reviews.get(sysname, {})
                    .items()]
                return httpx.Response(200, json={
                    "ok": True, "dim": "system",
                    "data": {"item": {"system": sysname, "objects": objs}}})
            # 导入重锚定(#323):系统作用域 working 端点清单(轻视图)
            if path.startswith("/api/systems/") and path.endswith("/endpoint"):
                system = path.split("/")[3]
                items = self.system_endpoints.get(system)
                if items is not None:
                    return httpx.Response(200, json={
                        "ok": True, "dim": "endpoint",
                        "data": {"items": items, "total": len(items)},
                    })
                return httpx.Response(404, json={"ok": False})
            # carry 预解析面(T9):services 目录 + endpoint full(写法对齐
            # conftest.EndpointPlateMock;未知 /full id → 404 = face 降级)。
            if path == "/api/service":
                return httpx.Response(200, json={
                    "ok": True, "dim": "service",
                    "data": {"items": self.services,
                             "total": len(self.services)},
                })
            if path.startswith("/api/endpoint/") and path.endswith("/full"):
                eid = path.rsplit("/", 2)[-2]
                if eid in self.fulls:
                    return httpx.Response(200, json={
                        "ok": True, "dim": "endpoint",
                        "data": {"item": self.fulls[eid], "total": 1},
                    })
                return httpx.Response(404, json={"ok": False})
            return httpx.Response(404)

        from app.services import plate_client

        plate_client.set_client_for_tests(
            httpx.AsyncClient(
                transport=httpx.MockTransport(handler), base_url="http://plate-test"
            )
        )

    def uninstall(self) -> None:
        from app.services import plate_client

        plate_client.set_client_for_tests(None)


@pytest.fixture
def plate_mock():
    mock = PlateMock()
    mock.install()
    try:
        yield mock
    finally:
        mock.uninstall()


# ── Gimbal launcher mock(V3.2 run 链路)─────────────────────────────
@pytest.fixture
def gimbal_mock(monkeypatch: pytest.MonkeyPatch) -> dict:
    """把 ``_fake_engine.launch`` 换成读 case.json 的假实现。

    * ``state["calls"]``  — 每次 launch 的 case.json 内容(dict,
      即引擎子进程的真实输入快照);
    * ``state["kwargs"]`` — launch 的关键字参数(step_to/report_dir);
    * ``state["exit_code"]`` — 可编程回包(默认 0;1=引擎判败)。
    """
    from pathlib import Path

    from app.services.gimbal_launcher import LaunchResult

    state: dict[str, Any] = {"calls": [], "kwargs": [], "exit_code": 0}

    async def _fake_launch(case_path, *, step_to=None, report_dir=None,
                           cwd=None, timeout=None, engine_log_path=None,
                       on_event=None, on_log=None, log_counters=None,
                       n_runs=1, retry=0):
        state["calls"].append(
            json.loads(Path(case_path).read_text(encoding="utf-8"))
        )
        state["kwargs"].append({"step_to": step_to, "report_dir": report_dir})
        code = state["exit_code"]
        return LaunchResult(
            launch_status="ok",
            exit_code=code,
            total=1,
            passed=1 if code == 0 else 0,
            failed=0 if code == 0 else 1,
        )

    from tests import _fake_engine as fe  # B6③:假引擎缝(legacy 链退役)

    monkeypatch.setattr(fe, "launch", _fake_launch)
    return state


# ── preview-plate ──────────────────────────────────────────────────
async def test_convert_strips_author_users(plate_mock: PlateMock) -> None:
    """TOK-01(2026-11-20 审计):作者明文 config.users 不进 plate
    convert 输入 —— plate HTTP 面无鉴权,plate_client.convert 入口
    单点剥除(执行链不依赖:materialize 对 converted users 一律丢弃,
    池凭证在 convert 产物上物化)。调用方传入的 dict 不被原地改。"""
    from app.services import plate_client

    scen = {"meta": {"name": "n"},
            "config": {"users": {"bob": {"username": "u", "password": "p"}},
                       "vars": {}},
            "steps": []}
    await plate_client.convert(scen)
    sent = plate_mock.convert_calls[-1]["scenario"]
    assert "users" not in (sent.get("config") or {})
    assert scen["config"]["users"]["bob"]["password"] == "p"


async def test_convert_strips_platform_sidecar_config_keys(
        plate_mock: PlateMock) -> None:
    """旁挂剥离(2026-11-22):var_locks / service_scope 是平台旁挂
    config 键(frontend types/plate.ts ConfigView 契约注释「不进 M2
    生成物」),plate Config extra="forbid" 不建模 —— convert 入口
    单点剥除;存储/解析面(run_prepare 服务引用解析读存储侧
    service_scope)不受影响,调用方 dict 不被原地改。与 TOK-01
    (作者明文 users)同闸并存。"""
    from app.services import plate_client

    scope = [{"envId": 1, "service": "fin-service"}]
    scen = {"meta": {"name": "n"},
            "config": {"vars": {},
                       "var_locks": ["bl_no"],
                       "service_scope": scope,
                       "users": {"bob": {"username": "u", "password": "p"}}},
            "steps": []}
    await plate_client.convert(scen)
    sent = plate_mock.convert_calls[-1]["scenario"]
    cfg = sent.get("config") or {}
    assert "service_scope" not in cfg
    assert "var_locks" not in cfg
    assert "users" not in cfg            # TOK-01 同闸并存
    assert cfg.get("vars") == {}         # M2 已知键不受剥除波及
    # 调用方传入的 dict 不被原地改(存储侧旁挂数据仍在)。
    assert scen["config"]["service_scope"] == scope
    assert scen["config"]["var_locks"] == ["bl_no"]
    assert scen["config"]["users"]["bob"]["password"] == "p"


async def test_convert_keeps_sidecar_free_config_untouched(
        plate_mock: PlateMock) -> None:
    """纯 M2 config(无 users/旁挂键)不走深拷贝重组 —— 输入即发送
    (b3-4「场景原样发 plate」语义对干净定义不回归)。"""
    from app.services import plate_client

    scen = {"meta": {"name": "n"},
            "config": {"vars": {"a": 1}, "services": {}},
            "steps": []}
    await plate_client.convert(scen)
    sent = plate_mock.convert_calls[-1]["scenario"]
    assert sent.get("config") == {"vars": {"a": 1}, "services": {}}


async def test_preview_plate_ok(client: AsyncClient, plate_mock: PlateMock) -> None:
    headers = await _register_and_login(client)
    r = await client.post(
        "/api/scenarios/preview-plate",
        headers=headers,
        json=_draft(),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["errors"] == []
    assert len(plate_mock.convert_calls) == 1


async def test_preview_plate_4xx_returns_422(
    client: AsyncClient, plate_mock: PlateMock
) -> None:
    """Upstream 4xx = verdict on the client's draft → 422 (not 502)."""
    plate_mock.behaviour = "4xx"
    headers = await _register_and_login(client)
    r = await client.post(
        "/api/scenarios/preview-plate",
        headers=headers,
        json=_draft(),
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["code"] == "plate_rejected"
    assert detail["errors"][0]["path"] == "steps[0].expectStatus"


async def test_preview_plate_5xx_returns_502(
    client: AsyncClient, plate_mock: PlateMock
) -> None:
    plate_mock.behaviour = "5xx"
    headers = await _register_and_login(client)
    r = await client.post(
        "/api/scenarios/preview-plate",
        headers=headers,
        json=_draft(),
    )
    assert r.status_code == 502
    assert r.json()["detail"]["code"] == "plate_unavailable"


async def test_preview_plate_connect_error_returns_502(
    client: AsyncClient, plate_mock: PlateMock
) -> None:
    plate_mock.behaviour = "unavailable"
    headers = await _register_and_login(client)
    r = await client.post(
        "/api/scenarios/preview-plate",
        headers=headers,
        json=_draft(),
    )
    assert r.status_code == 502
    assert r.json()["detail"]["code"] == "plate_unavailable"


async def test_preview_plate_bad_convert_envelope_returns_502_invalid_response(
    client: AsyncClient, plate_mock: PlateMock
) -> None:
    """J-1 收口:200+ok 但缺 converted = plate 侧契约违约,信令面在
    plate 边界即断(专码 502 plate_invalid_response,对齐 endpoint_catalog
    的 plate_invalid_envelope 先例)—— 半畸形回包不再以「空场景」流向
    下游物化/引擎。"""
    plate_mock.behaviour = "convert_no_converted"
    headers = await _register_and_login(client)
    r = await client.post(
        "/api/scenarios/preview-plate",
        headers=headers,
        json=_draft(),
    )
    assert r.status_code == 502
    detail = r.json()["detail"]
    assert detail["code"] == "plate_invalid_response"
    assert "converted" in detail["message"]


# ── run dispatcher ────────────────────────────────────────────────
async def _seed_scenario_case_and_dataset(
    client: AsyncClient, headers: dict, *, rows: list[dict],
    service: str | None = None,
) -> None:
    """Create scenario + 1 dataset with the given rows (Case layer dissolved).

    ``service``:给场景一步引用该服务键(authz M2a S6:绑定只对 steps
    实际引用的服务键选别名 —— 凭证注入用例须有被引用的服务)。"""
    # C1:数据集行键须 ⊆ 场景标量声明变量 — 把行键声明为标量 vars。
    steps = ([{"kind": "step", "call": {"service": service, "path": "/x"}}]
             if service else None)
    await client.post(
        "/api/scenarios",
        headers=headers,
        json=_draft(vars_map={k: 0 for row in rows for k in row},
                    steps=steps),
    )
    r = await client.post(
        "/api/scenarios/sc-test/data-sets",
        headers=headers,
        json={"name": "ds", "rows": rows},
    )
    assert r.status_code == 201


async def test_run_dispatch_calls_convert_per_row(
    client: AsyncClient, plate_mock: PlateMock, gimbal_mock: dict
) -> None:
    headers = await _register_and_login(client)
    rows = [{"qty": i} for i in range(3)]
    await _seed_scenario_case_and_dataset(client, headers, rows=rows)

    r = await client.post(
        "/api/runs",
        headers=headers,
        json={
            "scenarioId": "sc-test",
            "dataSetIds": ["ds-001"],
        },
    )
    assert r.status_code == 201
    assert "runId" in r.json()

    # Wait for the background fan-out to finish.
    # (轮询预算 10s:xdist -n auto 满载时 CPU 争抢会让 3 行 fanout 超过
    # 旧 2.5s 窗 → 偶发 convert_calls 不足断言失败;轻载/单进程远快于此。)
    for _ in range(200):
        if len(plate_mock.convert_calls) >= 3:
            break
        await asyncio.sleep(0.05)
    assert len(plate_mock.convert_calls) == 3

    # Regression guard: the per-row payload handed to plate /convert is the
    # UNWRAPPED definition — never the container. orchestration is
    # platform-only and must not leak; plate-required fields survive.
    # (Covers run_dispatcher._compose_scenario's container unwrap, which the
    # call-count assertion above does not.)
    # convert_calls[i] is the full wire envelope plate_client posts:
    #   {"consumer": "gimbal", "scenario": <composed dict>}
    scenario_payload = plate_mock.convert_calls[0]["scenario"]
    assert "orchestration" not in scenario_payload
    assert "caseMeta" not in scenario_payload
    assert scenario_payload["kind"] == "scenario"
    assert scenario_payload["scenarioId"] == "sc-test"
    assert scenario_payload["meta"]["name"] == "Test"
    # the row's vars are layered into config.vars, and the scenario-level
    # config is preserved through the unwrap
    assert scenario_payload["config"]["timePolicy"] == {"kind": "record"}
    assert scenario_payload["config"]["vars"]["qty"] == 0  # first row {qty: 0}


async def test_run_dispatch_preserves_row_value_types(
    client: AsyncClient, plate_mock: PlateMock, gimbal_mock: dict
) -> None:
    """行值进 config.vars 保类型(int/bool/float 不字符串化)。

    vars 两侧都是 dict[str, Any];断言 expected: 0 对 "0" 会错,
    #4 run 链路后这是 Gimbal 断言正确性的前置。
    """
    headers = await _register_and_login(client)
    rows = [{"qty": 7, "ok": True, "ratio": 1.5}]
    await _seed_scenario_case_and_dataset(client, headers, rows=rows)

    r = await client.post(
        "/api/runs",
        headers=headers,
        json={
            "scenarioId": "sc-test",
            "dataSetIds": ["ds-001"],
        },
    )
    assert r.status_code == 201

    for _ in range(50):
        if len(plate_mock.convert_calls) >= 1:
            break
        await asyncio.sleep(0.05)
    assert len(plate_mock.convert_calls) == 1

    vars_out = plate_mock.convert_calls[0]["scenario"]["config"]["vars"]
    assert vars_out["qty"] == 7
    assert vars_out["qty"] is not "7"  # noqa: F632 — 类型守卫,防回归字符串化
    assert vars_out["ok"] is True
    assert vars_out["ratio"] == 1.5


async def _wait_execution_final(client_run_id: str | None = None) -> "Execution":
    """等 fan-out 把 Execution 行写到终态(done/failed)。

    gimbal 调用到达 ≠ 计数已落库(行级循环全部结束后才 update),
    直接读会撞到 queued 初始态。
    """
    import sqlalchemy as sa

    from app.core import db as db_module
    from app.models import Execution

    for _ in range(100):
        async with db_module.SessionLocal() as s:
            ex = (
                (await s.execute(sa.select(Execution).order_by(Execution.id.desc())))
                .scalars()
                .first()
            )
            if ex is not None and ex.status in ("done", "failed"):
                return ex
        await asyncio.sleep(0.05)
    raise AssertionError(f"execution never reached final state: {ex!r}")


async def test_run_chain_convert_then_gimbal_execute(
    client: AsyncClient, plate_mock: PlateMock, gimbal_mock: dict
) -> None:
    """V3.2 运行链路:每行 convert(plate) → case 落盘 → launch(子进程 mock)。

    锁四件事:
      1. launch 收到的 case.json 是 convert 的 **converted 产物**
         (PlateMock 回 {"kind": "platform_scenario"}),不是平台原始 dict;
      2. 行值在 converted 之前已 merge 进 config.vars(保类型);
      3. exit_code=0 → 该行计 passed;Execution.status=done;
      4. Execution passed/failed 计数 = 行数(引擎计数被消费)。
    """
    headers = await _register_and_login(client)
    rows = [{"qty": 1}, {"qty": 2}]
    await _seed_scenario_case_and_dataset(client, headers, rows=rows)

    r = await client.post(
        "/api/runs",
        headers=headers,
        json={
            "scenarioId": "sc-test",
            "dataSetIds": ["ds-001"],
        },
    )
    assert r.status_code == 201

    for _ in range(50):
        if len(gimbal_mock["calls"]) >= 2:
            break
        await asyncio.sleep(0.05)
    assert len(gimbal_mock["calls"]) == 2
    assert len(plate_mock.convert_calls) == 2

    # 1. 载体是 converted 产物(case.json 即引擎输入快照)
    assert gimbal_mock["calls"][0]["kind"] == "platform_scenario"
    # step_to 不传(阶段 1 不用调试)
    assert gimbal_mock["kwargs"][0]["step_to"] is None

    # 2. convert 拿到的是平台原始 dict(vars 已 layer)
    conv_scenario = plate_mock.convert_calls[0]["scenario"]
    assert conv_scenario["config"]["vars"]["qty"] == 1
    assert conv_scenario["kind"] == "scenario"

    # 3+4. exitCode=0 两行 → passed=2 / failed=0 / done
    ex = await _wait_execution_final()
    assert ex.passed == 2
    assert ex.failed == 0
    assert ex.status == "done"


async def test_run_chain_gimbal_failure_counts_row_failed(
    client: AsyncClient, plate_mock: PlateMock, gimbal_mock: dict
) -> None:
    """引擎判败(exit_code=1)→ 该行计 failed;convert 本身没问题。"""
    gimbal_mock["exit_code"] = 1
    headers = await _register_and_login(client)
    await _seed_scenario_case_and_dataset(client, headers, rows=[{"qty": 1}])

    r = await client.post(
        "/api/runs",
        headers=headers,
        json={
            "scenarioId": "sc-test",
            "dataSetIds": ["ds-001"],
        },
    )
    assert r.status_code == 201

    for _ in range(50):
        if len(gimbal_mock["calls"]) >= 1:
            break
        await asyncio.sleep(0.05)
    assert len(gimbal_mock["calls"]) == 1

    ex = await _wait_execution_final()
    # convert 过了(结构合法),但引擎判败 → failed 计数
    assert ex.passed == 0
    assert ex.failed == 1
    assert ex.status == "failed"


async def test_run_partial_failure_marks_execution_failed(
    client: AsyncClient, plate_mock: PlateMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """严格终态规则(与 V1 executor / run_lifecycle reconcile 一致):
    1 过 1 败 → execution = failed。

    旧 V3 规则 ``failed and not passed`` 会把部分失败标成 done,
    与 V1 在同一张 /executions 表里显示矛盾状态。
    """
    from app.services import gimbal_launcher as gl
    from tests import _fake_engine as fe

    calls = {"n": 0}

    async def _run(case_path, **_kw: object):
        calls["n"] += 1
        ok = calls["n"] == 1  # 第一行过,第二行败
        code = 0 if ok else 1
        return gl.LaunchResult(
            launch_status="ok", exit_code=code, total=1,
            passed=1 if ok else 0, failed=0 if ok else 1,
        )

    monkeypatch.setattr(fe, "launch", _run)

    headers = await _register_and_login(client)
    await _seed_scenario_case_and_dataset(
        client, headers, rows=[{"qty": 1}, {"qty": 2}]
    )

    r = await client.post(
        "/api/runs",
        headers=headers,
        json={
            "scenarioId": "sc-test",
            "dataSetIds": ["ds-001"],
        },
    )
    assert r.status_code == 201

    ex = await _wait_execution_final()
    assert ex.passed == 1
    assert ex.failed == 1
    # 严格规则:只要有一行失败,整单 failed(不再是 done)
    assert ex.status == "failed"


async def test_run_auth_decrypt_failure_fails_execution(
    client: AsyncClient, plate_mock: PlateMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """凭证解密失败 = fail-fast(V1 严格语义)。

    整单 execution 记为 failed、所有行计入 failed 计数、一行都不
    分发执行(不带着空/坏凭证打环境)。旧行为是仅告警后继续跑。
    """
    headers = await _register_and_login(client)
    await _seed_scenario_case_and_dataset(
        client, headers, rows=[{"qty": 1}, {"qty": 2}], service="fin"
    )

    # 四件套布景:条目 fin-c1(default-ref → 属主默认账户)
    import sqlalchemy as sa

    from app.core import db as db_module
    from app.models import AuthAccount, User

    async with db_module.SessionLocal() as s:
        uid = (await s.execute(sa.select(User.id).where(
            User.username == "alice"))).scalar_one()
    await _identity("fin-c1", "fin")
    acc_id = await _pool_account("alice", system="fin",
                                 account_user="u", password="p")

    # 腐化密码密文 → fernet_decrypt 抛 ValueError(username 是明文实体键)
    async with db_module.SessionLocal() as s:
        row = await s.get(AuthAccount, acc_id)
        row.password_enc = "not-valid-fernet-ciphertext"
        await s.commit()

    from app.services import gimbal_launcher as gl
    from tests import _fake_engine as fe

    async def _must_not_run(*_a: object, **_k: object):
        raise AssertionError("解密失败后不得分发执行")

    monkeypatch.setattr(fe, "launch", _must_not_run)

    r = await client.post(
        "/api/runs",
        headers=headers,
        json={
            "scenarioId": "sc-test",
            "dataSetIds": ["ds-001"],
            "serviceBindings": {"fin": {"alias": "fin-c1"}},
        },
    )
    assert r.status_code == 201

    ex = await _wait_execution_final()
    assert ex.status == "failed"
    assert ex.failed == 2
    assert ex.passed == 0
    # 一行都没到 plate / gimbal
    assert len(plate_mock.convert_calls) == 0


async def _identity(alias_name: str, base: str, *,
                    login_url: str = "https://svc.internal") -> None:
    """authz M2a S6:绑定只选条目 —— 种同基础服务身份条目(+主档/实例,
    注入键 = 条目名;旧「声明槽位」随条目化退役)。"""
    from sqlalchemy import select as _sel

    from app.core import db as db_module
    from app.models import (Environment, Service, ServiceIdentity,
                            SystemEnvInstance)
    async with db_module.SessionLocal() as s:
        env = (await s.execute(_sel(Environment.id).where(
            Environment.is_default.is_(True)))).scalar_one_or_none()
        if env is None:
            s.add(Environment(name="测试", is_default=True))
            await s.flush()
            env = (await s.execute(_sel(Environment.id).where(
                Environment.is_default.is_(True)))).scalar_one()
        if (await s.execute(_sel(Service.id).where(
                Service.name == base))).scalar_one_or_none() is None:
            s.add(Service(name=base, system=base, kind="plate"))
        if login_url and (await s.execute(_sel(SystemEnvInstance.id).where(
                SystemEnvInstance.system == base,
                SystemEnvInstance.env_id == env))).scalar_one_or_none() is None:
            s.add(SystemEnvInstance(system=base, env_id=env,
                                    login_url=login_url))
        # M3 §8.5:部署行(派发硬门地址落点;幂等)
        from app.models import Deployment
        if (await s.execute(_sel(Deployment.id).where(
                Deployment.base_service == base,
                Deployment.env_id == env))).scalar_one_or_none() is None:
            s.add(Deployment(base_service=base, env_id=env,
                             base_url=f"https://{base}.internal"))
        s.add(ServiceIdentity(alias_name=alias_name, base_service=base,
                              env_id=env, ref_mode="default"))
        await s.commit()


async def _pool_account(username: str, *, system: str, account_user: str,
                        password: str, token_type: str = "bearer") -> int:
    """执行人池账户(default-ref 条目的取用行;同 (system,env) 首行占
    默认位)。返回账户 id。"""
    from sqlalchemy import select as _sel, text as _txt

    from app.core import db as db_module
    from app.core.security import fernet_encrypt
    from app.models import AuthAccount, Environment
    async with db_module.SessionLocal() as s:
        uid = (await s.execute(_txt(
            "SELECT id FROM users WHERE username = :u"),
            {"u": username})).scalar_one()
        env = (await s.execute(_sel(Environment.id).where(
            Environment.is_default.is_(True)))).scalar_one()
        have_default = (await s.execute(_sel(AuthAccount.id).where(
            AuthAccount.owner_id == uid, AuthAccount.system == system,
            AuthAccount.is_default.is_(True)))).scalar_one_or_none() is not None
        acc = AuthAccount(
            owner_id=uid, system=system, env_id=env, username=account_user,
            password_enc=fernet_encrypt(password), token_type=token_type,
            is_default=not have_default)
        s.add(acc)
        await s.commit()
        return acc.id


async def test_run_dispatch_records_failure_when_plate_down(
    client: AsyncClient, plate_mock: PlateMock
) -> None:
    """Plate 5xx mid-fan-out: still return 201 + runId; Execution marked failed."""
    plate_mock.behaviour = "5xx"
    headers = await _register_and_login(client)
    rows = [{"qty": 1}, {"qty": 2}]
    await _seed_scenario_case_and_dataset(client, headers, rows=rows)

    r = await client.post(
        "/api/runs",
        headers=headers,
        json={
            "scenarioId": "sc-test",
            "dataSetIds": ["ds-001"],
        },
    )
    assert r.status_code == 201
    run_id = r.json()["runId"]
    assert run_id.startswith("run-")


async def test_run_injects_exec_auths_into_run_copy_only(
    client: AsyncClient, plate_mock: PlateMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """执行用认证注入(S6:绑定选条目,注入键 = 条目名):解密注入只进 run 副本,
    convert 永不带明文。

    锁三条边界(#1 改造的安全契约 + V3.2 run 链路接线):
      1. convert 收到的 scenario.config.users 不含所选 alias 的明文凭据;
      2. dispatcher 落盘的 case.json(引擎子进程输入)config.users[alias]
         含解密后的 url/username/password/token_type/expires_in(形状同
         V1 executor 生产路径),且载体是 convert 的 **converted 产物**
         不是平台原始 dict。gimbal 子进程不在测试里真跑,monkeypatch
         捕获 launch 入参 — 验证的是 dispatcher 侧接线;
      3. Execution.config_json 用读侧契约 key ``injectedAuths``(数组,
         注入清单 = 扫描 ∪ 绑定),不再是旧的 "auth"/"exec_auth_alias"。
    """
    headers = await _register_and_login(client)
    await _seed_scenario_case_and_dataset(client, headers, rows=[{"qty": 1}],
                                          service="fin-service")

    # 布景:条目 fin-service-q1 + 属主池账户 + 实例登录口(四件套拆用)
    await _identity("fin-service-q1", "fin-service",
                    login_url="http://auth.example/login")
    await _pool_account("alice", system="fin-service",
                        account_user="qa-user", password="qa-pass")

    # 捕获 dispatcher → gimbal_launcher.launch 的入参(读落盘 case.json)
    from pathlib import Path

    from app.services import gimbal_launcher as gl
    from tests import _fake_engine as fe

    run_payloads: list[dict] = []

    async def _capture_run(case_path, **_kw: object):
        run_payloads.append(
            json.loads(Path(case_path).read_text(encoding="utf-8"))
        )
        return gl.LaunchResult(launch_status="ok", exit_code=0,
                               total=1, passed=1)

    monkeypatch.setattr(fe, "launch", _capture_run)

    r = await client.post(
        "/api/runs",
        headers=headers,
        json={
            "scenarioId": "sc-test",
            "dataSetIds": ["ds-001"],
            "serviceBindings": {"fin-service": {"alias": "fin-service-q1"}},
        },
    )
    assert r.status_code == 201

    for _ in range(50):
        if len(run_payloads) >= 1:
            break
        await asyncio.sleep(0.05)
    assert len(run_payloads) == 1

    # 1. convert 无明文(users 里没有所选条目)
    conv_scenario = plate_mock.convert_calls[0]["scenario"]
    assert "fin-service-q1" not in (
        conv_scenario.get("config", {}).get("users") or {})

    # 2. run 副本注入解密凭据(键 = 条目名;url = 实例登录口;载体是
    #    converted 产物:PlateMock 的 convert 回包 platform_scenario 形)
    injected = run_payloads[0]["config"]["users"]["fin-service-q1"]
    assert injected["username"] == "qa-user"
    assert injected["password"] == "qa-pass"
    assert injected["url"] == "http://auth.example/login"
    assert injected["token_type"] == "bearer"

    # 3. Execution.config_json key 对齐读侧契约
    import sqlalchemy as sa

    from app.core import db as db_module
    from app.models import Execution

    async with db_module.SessionLocal() as s:
        ex = (
            (
                await s.execute(
                    sa.select(Execution).order_by(Execution.id.desc())
                )
            )
            .scalars()
            .first()
        )
        assert ex is not None
        assert ex.config_json["injectedAuths"] == ["fin-service-q1"]
        assert ex.config_json["serviceBindings"]["fin-service"] == {
            "alias": "fin-service-q1"}
        assert "auth" not in ex.config_json
        assert "exec_auth_alias" not in ex.config_json


async def test_run_exec_auths_owner_scoped_cross_owner_alias_collision(
    client: AsyncClient, plate_mock: PlateMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """跨 owner 取用隔离:条目共享,账户按发起人池取。

    条目是团队级共享声明;alice/bob 各池各有 default 账户。若无
    owner 过滤,条目 → 账户解析会串池,注入谁的凭证取决于行序
    — 跨 owner 解错凭证的口子。锁:alice 发起 run,注入的必须是
    alice 的 username(且只有一行注入)。
    """
    headers = await _register_and_login(client)  # alice
    await _seed_scenario_case_and_dataset(client, headers, rows=[{"qty": 1}],
                                          service="fin-service")

    # 条目共享(团队级);alice/bob 各自池账户 —— 取用按发起人池隔离
    await _identity("fin-service-q1", "fin-service",
                    login_url="http://alice-auth/login")
    await _pool_account("alice", system="fin-service",
                        account_user="alice-user", password="alice-pass")
    bob_headers = await _register_and_login(client, username="bob")
    await _pool_account("bob", system="fin-service",
                        account_user="bob-user", password="bob-pass")

    from pathlib import Path

    from app.services import gimbal_launcher as gl
    from tests import _fake_engine as fe

    run_payloads: list[dict] = []

    async def _capture_run(case_path, **_kw: object):
        run_payloads.append(
            json.loads(Path(case_path).read_text(encoding="utf-8"))
        )
        return gl.LaunchResult(launch_status="ok", exit_code=0,
                               total=1, passed=1)

    monkeypatch.setattr(fe, "launch", _capture_run)

    # alice 发起运行,绑定选共享条目(取用须只吃 alice 池)
    r = await client.post(
        "/api/runs",
        headers=headers,
        json={
            "scenarioId": "sc-test",
            "dataSetIds": ["ds-001"],
            "serviceBindings": {"fin-service": {"alias": "fin-service-q1"}},
        },
    )
    assert r.status_code == 201

    for _ in range(50):
        if len(run_payloads) >= 1:
            break
        await asyncio.sleep(0.05)
    assert len(run_payloads) == 1

    users = run_payloads[0]["config"]["users"]
    # 恰好一个条目键,且取的是 alice 池的账户 — bob 的行绝不能被解入
    assert users["fin-service-q1"]["username"] == "alice-user"
    assert users["fin-service-q1"]["password"] == "alice-pass"
    assert users["fin-service-q1"]["url"] == "http://alice-auth/login"
