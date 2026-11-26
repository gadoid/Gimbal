"""执行设计(2026-09)E1/E1末 后端改造测试。

覆盖面(对应 §3.5 / §6 / §1.6 / §1.2):

* ``GET /executions/summary`` — KPI 带(路由顺序:``/summary`` 不被
  ``/{execution_id}`` 的 int Path 吃掉)与口径(owner 隔离、active 不受窗约束)
* ``GET /api/executions`` — status / 发起时间范围 / batch_id 筛选
* ``Execution.batch_id`` — POST /runs 带 batchId 落列 + config_json 双写
* ``POST /executions/{id}/rerun`` — 按 config_json 重建配方;重跑不带原批
* ``POST /run/precheck`` — 「用例 × 方案」失效判定的服务端唯一实现:
  数据集已删 / 注入条目悬空 / 未落点服务引用 / 场景不可读不泄露存在性

执行 mock 同 M1 测试:_fake_engine.launch 捕获式假实现,plate 走
PlateMock(behaviour ok)。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from .helpers import (
    launch_ok as _ok,
    make_draft as _draft,
    register_and_login as _register_and_login,
    wait_until as _wait,
)
from .test_scenario_composer_plate_integration import (
    PlateMock,
    plate_mock,  # noqa: F401  pytest fixture re-export
)
from .test_scenario_visibility_and_copy import _member, _seed_ds


def _patch_launch_capture(
    monkeypatch: pytest.MonkeyPatch, sink: list[dict]
) -> None:
    """把 ``_fake_engine.launch`` 换成读 case.json 并捕获的假实现。"""

    async def _capture(case_path, *, step_to=None, report_dir=None,
                       cwd=None, timeout=None, engine_log_path=None,
                       on_event=None, on_log=None, log_counters=None,
                       n_runs=1, retry=0):
        sink.append(json.loads(Path(case_path).read_text(encoding="utf-8")))
        return _ok()

    from tests import _fake_engine as fe  # B6③:假引擎缝(legacy 链退役)
    monkeypatch.setattr(fe, "launch", _capture)


async def _insert_execution(
    *,
    owner_id: int,
    scenario_id: str = "sc-e2e",
    status: str = "done",
    total_runs: int = 1,
    passed: int = 1,
    failed: int = 0,
    batch_id: str | None = None,
    created_at: datetime | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    plate_pins: dict | None = None,
    m2_hash: str | None = None,
    project_id: int | None = None,
) -> int:
    from app.core.db import SessionLocal
    from app.models import Execution

    async with SessionLocal() as s:
        ex = Execution(
            scenario_id=scenario_id,
            owner_id=owner_id,
            status=status,
            total_runs=total_runs,
            passed=passed,
            failed=failed,
            batch_id=batch_id,
            plate_pins=plate_pins,
            m2_hash=m2_hash,
            project_id=project_id,
        )
        if created_at is not None:
            ex.created_at = created_at
        if started_at is not None:
            ex.started_at = started_at
        if finished_at is not None:
            ex.finished_at = finished_at
        s.add(ex)
        await s.commit()
        await s.refresh(ex)
        return ex.id


async def _alice_id() -> int:
    from app.core.db import SessionLocal
    from app.models import User

    async with SessionLocal() as s:
        alice = (
            await s.execute(select(User).where(User.username == "alice"))
        ).scalar_one()
        return alice.id


# ── summary(KPI 带)───────────────────────────────────────────────
async def test_summary_route_order_and_kpi(client: AsyncClient) -> None:
    """/summary 在 /{execution_id} 之前声明 — 字面量不被 int Path 吃成 422;
    窗口锚 created_at;active 不受窗约束;执行维度 owner 硬隔离(§5.1)。"""
    auth = await _register_and_login(client)
    alice = await _alice_id()
    now = datetime.utcnow()
    await _insert_execution(
        owner_id=alice, status="done", total_runs=2, passed=1, failed=1,
        created_at=now - timedelta(days=1),
        started_at=now - timedelta(days=1), finished_at=now - timedelta(days=1),
    )
    await _insert_execution(
        owner_id=alice, status="failed", total_runs=1, passed=0, failed=1,
        created_at=now - timedelta(days=10),   # 窗外
    )
    await _insert_execution(owner_id=alice, status="running", created_at=now - timedelta(days=30))

    r = await client.get("/api/executions/summary", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    # 窗内(近 7 天)只有第一单;running 单在窗内计入 total_executions
    assert body["totalExecutions"] == 1
    assert body["totalRuns"] == 2 and body["passedRuns"] == 1 and body["failedRuns"] == 1
    assert abs(body["passRate"] - 0.5) < 1e-6
    assert body["activeExecutions"] == 1      # running 不受窗约束
    assert body["repeatFailureScenarios"] == 0
    assert body["todayExecutions"] == 0       # 三单均非今日(昨日/10 天/30 天前)


async def test_summary_today_executions(client: AsyncClient) -> None:
    """今日执行次数(stitch 0-2 批次 2026-11-23):自然日锚 created_at
    (服务器时区零点),含进行中单,与 windowDays 统计窗相互独立。"""
    auth = await _register_and_login(client, "today_u", "todaypass123")
    from sqlalchemy import select as sa_select

    from app.core.db import SessionLocal
    from app.models.user import User

    async with SessionLocal() as db:
        uid = (await db.execute(sa_select(User.id).where(
            User.username == "today_u"))).scalar_one()
    now = datetime.utcnow()
    # 今日两单(终态 + 进行中)+ 昨日一单
    await _insert_execution(owner_id=uid, status="done", total_runs=1, passed=1,
                            created_at=now)
    await _insert_execution(owner_id=uid, status="running", created_at=now)
    await _insert_execution(owner_id=uid, status="done", total_runs=1, passed=1,
                            created_at=now - timedelta(days=1))
    r = await client.get("/api/executions/summary", headers=auth)
    body = r.json()
    assert body["todayExecutions"] == 2
    # 窗口 1 天(滚动 24h)会把昨日边界单也计入 —— 证明两口径独立
    r = await client.get("/api/executions/summary?window_days=1", headers=auth)
    assert r.json()["todayExecutions"] == 2


async def test_summary_owner_isolation(client: AsyncClient) -> None:
    await _register_and_login(client, "alice", "alicepass123")
    await _insert_execution(owner_id=await _alice_id(), status="done", total_runs=3, passed=3)
    bob = await _register_and_login(client, "bob", "bobpass456")
    r = await client.get("/api/executions/summary", headers=bob)
    body = r.json()
    assert body["totalExecutions"] == 0
    assert body["totalRuns"] == 0 and body["passRate"] is None


# ── summary / list 项目口径(A 级批次,2026-11-18)────────────────────
async def _mk_project(name: str, *, members: dict[str, str]) -> int:
    """直插普通项目 + 成员(UPC §20 布景守卫单点:无 admin 自动补
    守夜人 —— 活跃普通项目 ≥1 有效 admin 的库层不变量)。"""
    from tests.helpers import mk_normal_project

    return await mk_normal_project(name, members)


async def _uid(username: str) -> int:
    from app.core.db import SessionLocal
    from app.models.user import User

    async with SessionLocal() as db:
        return (await db.execute(select(User.id).where(
            User.username == username))).scalar_one()


async def test_summary_project_scope_and_gate(client: AsyncClient) -> None:
    """projectId = 项目维度聚合:跨 owner 的项目行都算、非项目行不算;
    非成员 404(不泄露存在性)。"""
    alice_auth = await _register_and_login(client, "alice", "alicepass123")
    bob_auth = await _register_and_login(client, "bob", "bobpass456")
    carol_auth = await _register_and_login(client, "carol", "carolpass789")
    alice, bob, carol = await _uid("alice"), await _uid("bob"), await _uid("carol")
    pid = await _mk_project("p-exec", members={"alice": "admin", "bob": "member"})
    now = datetime.utcnow()
    await _insert_execution(owner_id=alice, project_id=pid, status="done",
                            total_runs=2, passed=1, failed=1,
                            created_at=now - timedelta(days=1))
    await _insert_execution(owner_id=bob, project_id=pid, status="done",
                            total_runs=4, passed=4, failed=0,
                            created_at=now - timedelta(days=2))
    # 项目外的个人执行不进项目口径
    await _insert_execution(owner_id=alice, status="done",
                            total_runs=10, passed=10,
                            created_at=now - timedelta(days=1))

    r = await client.get("/api/executions/summary",
                         params={"projectId": pid}, headers=alice_auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["totalExecutions"] == 2          # 跨 owner 的项目行
    assert body["totalRuns"] == 6 and body["passedRuns"] == 5
    assert abs(body["passRate"] - 5 / 6) < 1e-6
    # 非成员 404(carol 不在项目)
    r = await client.get("/api/executions/summary",
                         params={"projectId": pid}, headers=carol_auth)
    assert r.status_code == 404, r.text


async def test_summary_public_project_visible_to_all(client: AsyncClient) -> None:
    """公共项目例外(2026-11-19 复核补,与 get_project/facets 同口径):
    公共项目无成员行,非 Admin+ 普通用户也能读项目口径 summary ——
    项目详情页头卡「运行成功率」对普通访客可见(此前恒 404 显「—」)。"""
    from app.core.db import SessionLocal
    from sqlalchemy import select as _sel

    from app.models.project import Project

    alice_auth = await _register_and_login(client, "alice", "alicepass123")
    guest_auth = await _register_and_login(client, "guest", "guestpass123")
    alice = await _uid("alice")
    # 公共项目全库恰一行(conftest 种子;uq_projects_public_kind)
    async with SessionLocal() as db:
        pid = (await db.execute(_sel(Project.id).where(
            Project.kind == "public"))).scalar_one()
    now = datetime.utcnow()
    await _insert_execution(owner_id=alice, project_id=pid, status="done",
                            total_runs=4, passed=4, failed=0,
                            created_at=now - timedelta(days=1))
    # 非成员(亦非 Admin+)普通用户:公共项目 → 200
    r = await client.get("/api/executions/summary",
                         params={"projectId": pid}, headers=guest_auth)
    assert r.status_code == 200, r.text
    assert r.json()["totalExecutions"] == 1
    assert abs(r.json()["passRate"] - 1.0) < 1e-6


async def test_list_project_id_filter(client: AsyncClient) -> None:
    """列表 projectId 过滤:只回项目行(failedTotal 同口径)。"""
    alice_auth = await _register_and_login(client, "alice", "alicepass123")
    alice = await _uid("alice")
    pid = await _mk_project("p-list", members={"alice": "admin"})
    await _insert_execution(owner_id=alice, project_id=pid, status="done")
    await _insert_execution(owner_id=alice, project_id=pid, status="failed")
    await _insert_execution(owner_id=alice, status="done")   # 项目外

    r = await client.get("/api/executions",
                         params={"projectId": pid, "page_size": 50},
                         headers=alice_auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 2 and body["failedTotal"] == 1
    # 不带 projectId 的默认口径不受影响(个人 + 我所在项目 = 3)
    r = await client.get("/api/executions", params={"page_size": 50},
                         headers=alice_auth)
    assert r.json()["total"] == 3


# ── list 筛选(status / 时间 / 批次)──────────────────────────────
async def test_list_filters_status_batch_window(client: AsyncClient) -> None:
    auth = await _register_and_login(client)
    alice = await _alice_id()
    now = datetime.utcnow()
    b1 = await _insert_execution(owner_id=alice, status="done", batch_id="b-001",
                                 created_at=now - timedelta(days=1))
    b1f = await _insert_execution(owner_id=alice, status="failed", batch_id="b-001",
                                  created_at=now - timedelta(days=1))
    await _insert_execution(owner_id=alice, status="failed", batch_id="b-002",
                            created_at=now - timedelta(days=9))

    r = await client.get("/api/executions", params={"batch_id": "b-001"}, headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert {i["batch_id"] for i in body["items"]} == {"b-001"}

    r = await client.get("/api/executions", params={"status": "failed"}, headers=auth)
    assert r.json()["total"] == 2

    r = await client.get("/api/executions", params={"status": "nope"}, headers=auth)
    assert r.status_code == 422

    # 发起时间范围(锚 created_at):只命中昨天的两单
    r = await client.get("/api/executions", params={
        "created_from": (now - timedelta(days=2)).isoformat(),
        "created_to": now.isoformat(),
    }, headers=auth)
    assert r.json()["total"] == 2
    ids = {b1, b1f}
    assert {i["id"] for i in r.json()["items"]} == ids


# ── 版本台账面(RS3 §6.3)────────────────────────────────────────
async def test_version_ledger_pins_surface_list_and_detail(
    client: AsyncClient,
) -> None:
    """plate_pins/m2_hash 库里有、出参必须透出——两个构造器逐字段拼
    Out 模型,曾漏传这两个字段(2026-10-12 W16 试点实测 detail 恒 null)。
    键序 dump 用原名(本文件惯例:除 ownerName 手写别名外均 snake,
    前端 api/executions.ts 同款消费)。"""
    auth = await _register_and_login(client)
    alice = await _alice_id()
    ex_id = await _insert_execution(
        owner_id=alice, plate_pins={"fin": "1.0#1"}, m2_hash="8bbb8d85ccce",
    )

    r = await client.get(f"/api/executions/{ex_id}", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["plate_pins"] == {"fin": "1.0#1"}
    assert r.json()["m2_hash"] == "8bbb8d85ccce"

    r = await client.get("/api/executions", headers=auth)
    row = next(it for it in r.json()["items"] if it["id"] == ex_id)
    assert row["plate_pins"] == {"fin": "1.0#1"}
    assert row["m2_hash"] == "8bbb8d85ccce"


# ── 批次键(§1.2:平台一次只发一条,批只是归并键)─────────────────
async def test_run_with_batch_id_lands_column_and_config(
    client: AsyncClient, plate_mock: PlateMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    auth = await _member(client, "alice")
    r = await client.post("/api/scenarios", headers=auth, json=_draft())
    assert r.status_code == 201, r.text
    calls: list[dict] = []
    _patch_launch_capture(monkeypatch, calls)

    r = await client.post("/api/runs", headers=auth, json={
        "scenarioId": "sc-test", "batchId": "b-run-1",
    })
    assert r.status_code == 201, r.text
    eid = r.json()["executionId"]

    from app.core.db import SessionLocal
    from app.models import Execution

    async with SessionLocal() as s:
        ex = await s.get(Execution, eid)
        assert ex is not None and ex.batch_id == "b-run-1"
        assert (ex.config_json or {}).get("batchId") == "b-run-1"


# ── rerun(§3.4/§3.5:config_json 已存完整配方,重建即可)──────────
async def test_rerun_rebuilds_recipe_from_config(
    client: AsyncClient, plate_mock: PlateMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    auth = await _member(client, "alice")
    r = await client.post("/api/scenarios", headers=auth,
                          json=_draft(vars_map={"qty": 0}))
    assert r.status_code == 201
    await _seed_ds(client, auth)
    calls: list[dict] = []
    _patch_launch_capture(monkeypatch, calls)

    r = await client.post("/api/runs", headers=auth, json={
        "scenarioId": "sc-test", "dataSetIds": ["ds-001"], "batchId": "b-org",
        "runOptions": {"n_runs": 2, "parallel": 1},
        "schemeId": "rs-001", "schemeName": "冒烟",
    })
    assert r.status_code == 201, r.text
    origin = r.json()["executionId"]

    r = await client.post(f"/api/executions/{origin}/rerun", headers=auth)
    assert r.status_code == 201, r.text
    new_id = r.json()["executionId"]
    assert new_id != origin

    from app.core.db import SessionLocal
    from app.models import Execution

    async with SessionLocal() as s:
        new_ex = await s.get(Execution, new_id)
        origin_ex = await s.get(Execution, origin)
        assert new_ex is not None and origin_ex is not None
        cfg = new_ex.config_json or {}
        # 配方保真:数据集 / 方案溯源 / 参数逐键还原
        assert cfg.get("dataSetIds") == ["ds-001"]
        assert cfg.get("schemeId") == "rs-001" and cfg.get("schemeName") == "冒烟"
        assert cfg.get("runOptions", {}).get("n_runs") == 2
        # 重跑是新的一次独立发起:不带原批
        assert new_ex.batch_id is None and cfg.get("batchId") is None
        assert origin_ex.batch_id == "b-org"


async def test_rerun_missing_scenario_404(client: AsyncClient) -> None:
    auth = await _register_and_login(client)
    from app.core.db import SessionLocal
    from app.models import Execution, User

    async with SessionLocal() as s:
        alice = (
            await s.execute(select(User).where(User.username == "alice"))
        ).scalar_one()
        ex = Execution(scenario_id="sc-gone", owner_id=alice.id, status="done",
                       total_runs=1, passed=1,
                       config_json={"runId": "r-x", "scenarioId": "sc-gone"})
        s.add(ex)
        await s.commit()
        await s.refresh(ex)
        eid = ex.id
    r = await client.post(f"/api/executions/{eid}/rerun", headers=auth)
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "scenario_not_found"


# ── precheck(§1.6:失效判定服务端唯一实现)────────────────────────
async def _seed_empty_ds(client: AsyncClient, headers: dict) -> None:
    """存在性即够的数据集(空行;预检/配方重建不消费行内容)。"""
    r = await client.post(
        "/api/scenarios/sc-test/data-sets",
        headers=headers,
        json={"name": "ds", "rows": [{}]},
    )
    assert r.status_code == 201, r.text


def _steps_draft(services: dict | None = None, body: dict | None = None) -> dict:
    steps = [{
        "kind": "step", "description": "下单",
        "call": {"service": "fin.order", "method": "POST", "path": "/x"},
        "request": {"kind": "request", "body": body if body is not None else {"amount": 1}},
        "strategy": [],
    }]
    d = _draft(steps=steps)
    if services is not None:
        d["definition"]["config"]["services"] = services
    return d


async def _setup_scenario(
    client: AsyncClient, headers: dict, *, services: dict | None = None,
    body: dict | None = None,
) -> None:
    r = await client.post(
        "/api/scenarios", headers=headers,
        json={
            **_steps_draft(services=services, body=body),
            "assertion_registry": {"entries": [
                {"id": "inj-live", "name": "金额", "value": -1, "asserts": [],
                 "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount"}},
                {"id": "inj-dead", "name": "缺失字段", "value": 1, "asserts": [],
                 "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.nope"}},
            ]},
        },
    )
    assert r.status_code == 201, r.text


async def _make_scheme(client: AsyncClient, headers: dict, name: str, **over) -> str:
    body = {"name": name, "dataSetSelection": [], "injectionEntryIds": [],
            "serviceBindings": {},
            "options": {"step_from": None, "step_to": None, "n_runs": 1,
                        "parallel": 1, "subscribe": None}}
    body.update(over)
    r = await client.post("/api/scenarios/sc-test/run-schemes", headers=headers,
                          json=body)
    assert r.status_code == 201, r.text
    return r.json()["schemeId"]


async def test_precheck_reports_dead_dataset_dangling_and_unbound(
    client: AsyncClient, plate_mock: PlateMock
) -> None:
    from app.core import db as db_module
    from app.models import Deployment, Environment

    auth = await _member(client, "alice")
    await _setup_scenario(client, auth)          # steps 引用 fin.order,声明 services 缺
    await _seed_empty_ds(client, auth)
    # S6:方案选环境 → 该环境部署表给 fin.order 地址(绑定 url 退役)
    from app.models import Service, ServiceIdentity
    async with db_module.SessionLocal() as db:
        env = Environment(name="er-dev")
        db.add(env)
        await db.flush()
        # §8.2:标签来自有效身份 —— 条目(fin.order 自身)钉 er-dev,
        # 预检据此取该标签的部署地址(方案 environmentId 已退役不消费)
        db.add(Service(name="fin.order", system="fin", kind="plate"))
        db.add(ServiceIdentity(alias_name="fin.order", base_service="fin.order",
                               env_id=env.id, ref_mode="default"))
        db.add(Deployment(base_service="fin.order", env_id=env.id,
                          base_url="http://fin"))
        await db.commit()
        env_id = env.id

    good = await _make_scheme(client, auth, "好方案",
                              injectionEntryIds=["inj-live"])
    bad = await _make_scheme(client, auth, "坏方案",
                             dataSetSelection=[{"datasetId": "ds-gone", "rowIndexes": []}],
                             injectionEntryIds=["inj-live", "inj-dead"])

    r = await client.post("/api/run/precheck", headers=auth, json=[
        {"scenarioId": "sc-test", "schemeId": good},
        {"scenarioId": "sc-test", "schemeId": bad},
    ])
    assert r.status_code == 200, r.text
    res = {x["schemeId"]: x for x in r.json()}
    good_res, bad_res = res[good], res[bad]
    # 好方案:数据集在、条目活、方案环境有部署地址 → 可跑
    assert good_res["schemeValid"] is True
    assert good_res["deadDatasetIds"] == [] and good_res["danglingEntryIds"] == []
    assert good_res["unboundServices"] == []
    # 坏方案:数据集已删 + 条目悬空;换一个方案就能跑(不是用例禁跑)
    assert bad_res["schemeValid"] is False
    assert bad_res["deadDatasetIds"] == ["ds-gone"]
    assert bad_res["danglingEntryIds"] == ["inj-dead"]
    # §8.2:标签按场景身份解析(与方案无关)—— 条目钉 er-dev且该
    # 标签有部署行,坏方案的地址同样就绪(坏在数据集/注入,不在地址)
    assert bad_res["unboundServices"] == []


async def test_precheck_env_unspecified_signal(
    client: AsyncClient, plate_mock: PlateMock
) -> None:
    """§1.4 env 必填:环境链全空(方案无显式位、平台无默认环境)→
    envUnspecified 点名根因 —— 全数 missing 只是表象,先建默认环境;
    环境就位后信号熄灭(条目未装载是另一件事,不混同)。"""
    auth = await _member(client, "alice")
    # 步骤模板引用 ${auth.qa-entry.token} → 预检注入清单非空
    await _setup_scenario(client, auth, body={
        "amount": 1, "token": "${auth.qa-entry.token}"})
    await _seed_empty_ds(client, auth)
    scheme = await _make_scheme(client, auth, "无环境方案")

    r = await client.post("/api/run/precheck", headers=auth, json=[
        {"scenarioId": "sc-test", "schemeId": scheme}])
    assert r.status_code == 200, r.text
    one = r.json()[0]
    assert one["envUnspecified"] is True
    assert one["missingAuths"] == ["qa-entry"]

    from app.core import db as db_module
    from app.models import Environment
    async with db_module.SessionLocal() as db:
        db.add(Environment(name="测试", is_default=True))
        await db.commit()
    r2 = await client.post("/api/run/precheck", headers=auth, json=[
        {"scenarioId": "sc-test", "schemeId": scheme}])
    one2 = r2.json()[0]
    assert one2["envUnspecified"] is False
    assert one2["missingAuths"] == ["qa-entry"]


async def test_precheck_found_and_scheme_found_gates(
    client: AsyncClient, plate_mock: PlateMock
) -> None:
    auth = await _member(client, "alice")
    await _setup_scenario(client, auth)
    gone_scheme = await _make_scheme(client, auth, "将删方案")

    # 别人的私有场景:found=false(不泄露存在性,§5.3)
    bob = await _member(client, "bob")
    r = await client.post("/api/run/precheck", headers=bob, json=[
        {"scenarioId": "sc-test", "schemeId": gone_scheme},
    ])
    assert r.status_code == 200
    item = r.json()[0]
    assert item["found"] is False and item["schemeValid"] is False

    # 方案不存在:schemeFound=false
    r = await client.post("/api/run/precheck", headers=auth, json=[
        {"scenarioId": "sc-test", "schemeId": "rs-999"},
        {"scenarioId": "sc-none", "schemeId": gone_scheme},
    ])
    assert r.status_code == 200
    items = r.json()
    assert items[0]["schemeFound"] is False and items[0]["schemeValid"] is False
    assert items[1]["found"] is False


# ── W21:详情带 current_plate(重跑将使用的修订)────────────────────
async def test_execution_detail_current_plate(client: AsyncClient) -> None:
    """场景当前 meta.plate → detail.currentPlate;场景删除后 = None。"""
    auth = await _member(client, "alice")
    draft = _draft(vars_map={"qty": 1})
    draft["definition"]["meta"]["plate"] = {"fin": "1.0#2"}
    r = await client.post("/api/scenarios", headers=auth, json=draft)
    assert r.status_code == 201, r.text

    eid = await _insert_execution(
        owner_id=await _alice_id(), scenario_id="sc-test", status="passed",
        plate_pins={"fin": "1.0#1"})

    d = await client.get(f"/api/executions/{eid}", headers=auth)
    assert d.status_code == 200, d.text
    body = d.json()
    assert body["plate_pins"] == {"fin": "1.0#1"}     # 当时修订
    assert body["current_plate"] == {"fin": "1.0#2"}  # 重跑将使用
    assert body["m2_hash"] is None

    # 场景删除 → currentPlate = None(只剩当时修订,无对比列)
    await client.delete("/api/scenarios/sc-test", headers=auth)
    d = await client.get(f"/api/executions/{eid}", headers=auth)
    assert d.status_code == 200, d.text
    assert d.json()["current_plate"] is None


async def test_precheck_alias_base_url_not_unbound(
    client: AsyncClient, plate_mock: PlateMock
) -> None:
    """N1-7:别名表 base_url(③层)不算未落点 —— 与执行期三层链同口径。

    执行物化 _apply_services 是 ②声明>③部署地址;预检此前只判声明层,
    fin.order 无声明时被误报 unbound —— 但执行期③层能补上(预检拦了、
    执行能跑)。S6:③ = 默认环境部署表。
    """
    from app.core import db as db_module

    from .helpers import seed_deployment

    auth = await _member(client, "alice")
    await _setup_scenario(client, auth)      # steps 引用 fin.order,声明 services 缺
    scheme = await _make_scheme(client, auth, "无绑定方案")

    async with db_module.SessionLocal() as db:
        await seed_deployment(db, "fin.order", "http://fin-alias")
        await db.commit()

    r = await client.post("/api/run/precheck", headers=auth, json=[
        {"scenarioId": "sc-test", "schemeId": scheme},
    ])
    assert r.status_code == 200, r.text
    res = {x["schemeId"]: x for x in r.json()}[scheme]
    assert res["unboundServices"] == []      # ③层补上,不再误报


async def test_precheck_empty_declaration_not_resolved(
    client: AsyncClient, plate_mock: PlateMock
) -> None:
    """空声明(键在值空)不算 ② 层落点(评审 2026-11-01):与执行期
    _apply_services 同源判定 —— 无③层别名时预检提示未落点(此前键
    存在即算,预检与执行一起漏报,空值被带进 case 到引擎才炸);
    有③层时算可解析(执行期用别名地址盖掉空值)。"""
    from app.core import db as db_module

    from .helpers import seed_deployment

    auth = await _member(client, "alice")
    await _setup_scenario(client, auth, services={"fin.order": ""})
    scheme = await _make_scheme(client, auth, "空声明方案")

    r = await client.post("/api/run/precheck", headers=auth, json=[
        {"scenarioId": "sc-test", "schemeId": scheme},
    ])
    assert r.status_code == 200, r.text
    res = {x["schemeId"]: x for x in r.json()}[scheme]
    assert res["unboundServices"] == ["fin.order"]     # 空声明 ≠ 落点

    async with db_module.SessionLocal() as db:
        await seed_deployment(db, "fin.order", "http://fin-alias")
        await db.commit()

    r = await client.post("/api/run/precheck", headers=auth, json=[
        {"scenarioId": "sc-test", "schemeId": scheme},
    ])
    assert r.status_code == 200, r.text
    res = {x["schemeId"]: x for x in r.json()}[scheme]
    assert res["unboundServices"] == []               # ③层可补 → 不提示
