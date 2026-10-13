"""C-1/C-2(2026-10-13):保存端 meta.plate 强制与引用校验。

契约(对齐 R19 导入口径):
* 锚定(endpoint 首段,``ext:`` 前缀豁免)系统必须声明 —— 未声明 =
  绕开 plate 按陈旧存储 binding 执行的过渡形态,rs3 全量回填后由
  保存闸关闭该入口;
* 声明引用须有效:``<line>#<n>`` 形状、线存在、修订在线内;working
  豁免;PUT 声明未变跳过引用校验;
* plate 不可达 → 引用校验跳过(保存不因目录故障阻断;执行期门仍在)。
"""
from __future__ import annotations

from tests.helpers import make_draft, register_and_login
from tests.test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401


async def _poll(client, h, eid, *, field: str, timeout_s: float = 30.0):
    """async 轮询执行详情字段。"""
    import asyncio as _a
    deadline = _a.get_event_loop().time() + timeout_s
    d: dict = {}
    while _a.get_event_loop().time() < deadline:
        d = (await client.get(f"/api/executions/{eid}", headers=h)).json()
        if d.get(field) is not None:
            return d
        await _a.sleep(0.1)
    return d


def _steps(endpoint="fin.orders.get"):
    return [{
        "kind": "step", "endpoint": endpoint,
        "call": {"service": "fin-service", "method": "GET", "path": "/o"},
        "request": {"kind": "request", "body": {}}, "strategy": [],
    }]


async def test_missing_declaration_rejected(client, plate_mock: PlateMock):
    """锚定系统未声明 → 422 meta_plate_missing_system(make_draft 的
    plate=False 哨兵显式构造未声明形态)。"""
    h = await register_and_login(client, "c2gate1", "pw123456")
    draft = make_draft("sc-c2-1", steps=_steps(), plate=False)
    r = await client.post("/api/scenarios", headers=h, json=draft)
    assert r.status_code == 422
    assert r.json()["detail"].startswith("meta_plate_missing_system")
    assert "fin" in r.json()["detail"]


async def test_invalid_refs_rejected(client, plate_mock: PlateMock):
    """"1.0"(只有线)/"1.0#9"(修订不存在)/"2.0#1"(线不存在)→ 422。"""
    h = await register_and_login(client, "c2gate2", "pw123456")
    for i, bad in enumerate(["1.0", "1.0#9", "2.0#1", "bogus"]):
        draft = make_draft(f"sc-c2-bad{i}", steps=_steps(),
                           plate={"fin": bad})
        r = await client.post("/api/scenarios", headers=h, json=draft)
        assert r.status_code == 422, (bad, r.text)
        assert r.json()["detail"].startswith("meta_plate_invalid_ref"), bad


async def test_valid_ref_and_working_pass(client, plate_mock: PlateMock):
    """精确修订与 working 声明均放行;ext: 锚点免声明。"""
    h = await register_and_login(client, "c2gate3", "pw123456")
    r = await client.post("/api/scenarios", headers=h, json=make_draft(
        "sc-c2-ok1", steps=_steps(), plate={"fin": "1.0#1"}))
    assert r.status_code == 201, r.text
    r = await client.post("/api/scenarios", headers=h, json=make_draft(
        "sc-c2-ok2", steps=_steps(), plate={"fin": "working"}))
    assert r.status_code == 201, r.text
    # 纯外部锚点:无声明也过(ext: 无版本语义)
    r = await client.post("/api/scenarios", headers=h, json=make_draft(
        "sc-c2-ext", steps=_steps("ext:pay.list"),
        plate=False))
    assert r.status_code == 201, r.text


async def test_put_unchanged_declaration_skips_ref_check(
        client, plate_mock: PlateMock):
    """PUT 声明未变 → 跳过引用校验(防抖自动保存不放大 plate 调用):
    把线表改成不含声明线,未变声明的 PUT 照常通过;一改声明即 422。"""
    h = await register_and_login(client, "c2gate4", "pw123456")
    r = await client.post("/api/scenarios", headers=h, json=make_draft(
        "sc-c2-put", steps=_steps(), plate={"fin": "1.0#1"}))
    assert r.status_code == 201, r.text

    plate_mock.lines = {"fin": [{"line": "9.9", "revisions": 1,
                                 "latest": "9.9#1"}]}
    # 声明未变 → 通过(引用校验被跳过)
    draft = make_draft("sc-c2-put", steps=_steps(), plate={"fin": "1.0#1"})
    draft["definition"]["meta"]["name"] = "改名不断链"
    r = await client.put("/api/scenarios/sc-c2-put", headers=h, json=draft)
    assert r.status_code == 200, r.text
    # 声明换成不存在线 → 422
    draft2 = make_draft("sc-c2-put", steps=_steps(), plate={"fin": "2.0#1"})
    r = await client.put("/api/scenarios/sc-c2-put", headers=h, json=draft2)
    assert r.status_code == 422
    assert r.json()["detail"].startswith("meta_plate_invalid_ref")


async def test_plate_unavailable_skips_ref_check(
        client, plate_mock: PlateMock, monkeypatch):
    """plate 不可达 → 引用校验跳过,保存照常(执行期门仍在)。"""
    from app.services import plate_client

    async def _down(_sysname):
        raise plate_client.PlateUnavailableError("plate down")
    monkeypatch.setattr(plate_client, "list_lines", _down)

    h = await register_and_login(client, "c2gate5", "pw123456")
    r = await client.post("/api/scenarios", headers=h, json=make_draft(
        "sc-c2-down", steps=_steps(), plate={"fin": "9.9#9"}))
    assert r.status_code == 201, r.text


async def test_store_level_gate_covers_bypass_writes(client, plate_mock: PlateMock):
    """⑥(2026-10-13):闸在 scenario_store 唯一写入口 —— 绕过路由直调
    store.create(导入/适配提交同走此面)的未声明载荷同样被拒。"""
    import pytest as _pytest
    from app.core import db as db_module
    from app.schemas.scenario_composer import ScenarioDraft
    from app.services import scenario_store
    from tests.helpers import make_draft

    await register_and_login(client, "c2sink", "pw123456")
    draft = make_draft("sc-c2-sink", steps=_steps(), plate=False)
    async with db_module.SessionLocal() as s:
        with _pytest.raises(ValueError, match="meta_plate_missing_system"):
            await scenario_store.create(
                s, ScenarioDraft.model_validate(draft),
                owner="c2sink", owner_id=1)


async def test_dispatcher_labels_rejected_not_unavailable(
        client, plate_mock: PlateMock, monkeypatch):
    """⑥:plate 拒绝(4xx 裁决)→ dispatcherError=plate_rejected,不再
    冒充 plate_unavailable。"""
    from app.services import plate_client

    async def _rejected(meta_plate, endpoints, **kw):
        raise plate_client.PlateRejectedError(
            code="revision_not_found", message="no such revision")
    monkeypatch.setattr(plate_client, "resolve", _rejected)

    h = await register_and_login(client, "c2rej", "pw123456")
    # 用保存闸可过的引用("1.0#1");拒绝发生在派发期(monkeypatch resolve)
    r = await client.post("/api/scenarios", headers=h, json=make_draft(
        "sc-c2-rej", steps=_steps(), plate={"fin": "1.0#1"}))
    assert r.status_code == 201, r.text      # 保存闸:不可达跳过(ref 校验)
    r = await client.post("/api/runs", headers=h,
                          json={"scenarioId": "sc-c2-rej", "dataSetIds": []})
    assert r.status_code == 201, r.text
    eid = r.json()["executionId"]
    # 终态化在 worker 兜底(finalize_execution_if_stuck),轮询到终态后
    # 再给一次落库窗口
    import asyncio as _a
    async def _has_err():
        d = (await client.get(f"/api/executions/{eid}", headers=h)).json()
        return bool((d.get("config") or {}).get("dispatcherError"))
    deadline = _a.get_event_loop().time() + 30.0
    while _a.get_event_loop().time() < deadline and not await _has_err():
        await _a.sleep(0.1)
    d = (await client.get(f"/api/executions/{eid}", headers=h)).json()
    cfg = d.get("config") or {}
    err = cfg.get("dispatcherError") or ""
    assert "plate_rejected" in err, err
    assert "plate_unavailable" not in err, err
