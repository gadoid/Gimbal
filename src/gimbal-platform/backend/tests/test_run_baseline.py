"""D12 基线执行:dataSetIds=[] → 一个隐式空覆盖行,纯基线跑一次。

V3.2 执行链:launch mock 从内存 dict 改为读落盘的 case.json ——
顺带断言"数据驱动用例快照真的写了盘、内容是合成后的 scenario"。
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from httpx import AsyncClient

from tests.helpers import (
    launch_ok as _ok,
    make_draft,
    register_and_login,
    wait_until,
)

STEPS = [{
    "api": {"view_hints": {"endpoint_id": "fin.order.add"}},
    "request": {"body": {"customer_id": "${var.customer_id}"}},
}]


async def test_baseline_run_without_datasets(
    client: AsyncClient, monkeypatch
) -> None:
    headers = await register_and_login(client)
    draft = make_draft("sc-base", steps=STEPS)
    draft["definition"]["config"] = {
        "timePolicy": {"kind": "record"},
        "vars": {"customer_id": "261"},
    }
    await client.post("/api/scenarios", headers=headers, json=draft)

    cases: list[dict] = []
    case_paths: list[Path] = []

    async def _capture(case_path, *, step_to=None, report_dir=None,
                       cwd=None, timeout=None, engine_log_path=None):
        path = Path(case_path)
        case_paths.append(path)
        cases.append(json.loads(path.read_text(encoding="utf-8")))
        return _ok()

    async def _fake_convert(scenario):
        return {"consumer": "platform", "converted": dict(scenario)}

    from app.services import gimbal_launcher as gl, plate_client as pc
    monkeypatch.setattr(gl, "launch", _capture)
    monkeypatch.setattr(pc, "convert", _fake_convert)

    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-base", "dataSetIds": [],
    })
    assert r.status_code == 201, r.text

    # wait_until 既有模式(test_run_m1_capabilities):同步谓词轮询。
    await wait_until(lambda: len(cases) >= 1)
    assert len(cases) == 1                      # 一个隐式空行 × nRuns=1
    assert cases[0]["config"]["vars"]["customer_id"] == "261"  # 基线 vars 生效
    # case 文件落在 run 目录下(DATA_DIR/runs/cases/<runId>/...),是
    # gimbal run launch 的唯一输入快照。
    assert "case.json" in str(case_paths[0])
    assert "runs" in case_paths[0].parts

    import sqlalchemy as sa

    from app.core import db as db_module
    from app.models.execution import Execution

    # capture mock 触发先于 _fanout 落库 → 轮询等 Execution 到达终态,
    # 不能在 wait_until(cases) 后立刻读库(与计数更新竞态)。
    row = None
    for _ in range(100):
        async with db_module.SessionLocal() as s:
            row = (
                await s.execute(
                    sa.select(Execution).order_by(Execution.id.desc()).limit(1)
                )
            ).scalar_one_or_none()
        if row is not None and row.status == "done":
            break
        await asyncio.sleep(0.05)
    assert row is not None
    assert row.total_runs == 1  # 空数据集回退行(1 行)× nRuns=1
    assert row.passed == 1 and row.status == "done"


async def test_selected_dataset_with_zero_rows_runs_baseline_once(
    client: AsyncClient, monkeypatch
) -> None:
    """选中"0 行数据集"(新编辑器:行 0 基线虚行不落库,只有基线时
    rows=[])→ 仍按 D12 语义跑一次基线,而不是 0/0/0 秒完结。

    回归自线上:用户选了只有基线的数据集执行,Execution 显示
    total/passed/failed 全 0(started→finished 相差 5µs)。
    """
    headers = await register_and_login(client)
    draft = make_draft("sc-empty-ds", steps=STEPS)
    draft["definition"]["config"] = {
        "timePolicy": {"kind": "record"},
        "vars": {"customer_id": "261"},
    }
    await client.post("/api/scenarios", headers=headers, json=draft)
    r = await client.post(
        "/api/scenarios/sc-empty-ds/data-sets",
        headers=headers,
        json={"name": "ds-empty", "rows": []},
    )
    assert r.status_code == 201, r.text
    dataset_id = r.json()["datasetId"]

    cases: list[dict] = []

    async def _capture(case_path, *, step_to=None, report_dir=None,
                       cwd=None, timeout=None, engine_log_path=None):
        cases.append(json.loads(Path(case_path).read_text(encoding="utf-8")))
        return _ok()

    async def _fake_convert(scenario):
        return {"consumer": "platform", "converted": dict(scenario)}

    from app.services import gimbal_launcher as gl, plate_client as pc
    monkeypatch.setattr(gl, "launch", _capture)
    monkeypatch.setattr(pc, "convert", _fake_convert)

    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-empty-ds", "dataSetIds": [dataset_id],
    })
    assert r.status_code == 201, r.text

    await wait_until(lambda: len(cases) >= 1)
    assert len(cases) == 1                      # 隐式基线行 × nRuns=1
    assert cases[0]["config"]["vars"]["customer_id"] == "261"

    import sqlalchemy as sa

    from app.core import db as db_module
    from app.models.execution import Execution

    row = None
    for _ in range(100):
        async with db_module.SessionLocal() as s:
            row = (
                await s.execute(
                    sa.select(Execution).order_by(Execution.id.desc()).limit(1)
                )
            ).scalar_one_or_none()
        if row is not None and row.status == "done":
            break
        await asyncio.sleep(0.05)
    assert row is not None
    assert row.total_runs == 1
    assert row.passed == 1 and row.status == "done"


async def test_dataset_row_string_values_coerced_to_baseline_types(
    client: AsyncClient, monkeypatch
) -> None:
    """新数据集编辑器(转置表格/CSV)把所有行值字符串化(``String(v)``);
    合入 config.vars 时按基线类型还原 — int/bool/float 断言不被字符串化
    破坏,基线是 str 的原样保留。
    """
    headers = await register_and_login(client)
    draft = make_draft(
        "sc-coerce",
        steps=STEPS,
        vars_map={"qty": 1, "ok": True, "ratio": 1.5, "note": "x"},
    )
    await client.post("/api/scenarios", headers=headers, json=draft)
    r = await client.post(
        "/api/scenarios/sc-coerce/data-sets",
        headers=headers,
        json={"name": "ds", "rows": [{
            "qty": "2", "ok": "false", "ratio": "2.5", "note": "y",
        }]},
    )
    assert r.status_code == 201, r.text
    dataset_id = r.json()["datasetId"]

    cases: list[dict] = []

    async def _capture(case_path, *, step_to=None, report_dir=None,
                       cwd=None, timeout=None, engine_log_path=None):
        cases.append(json.loads(Path(case_path).read_text(encoding="utf-8")))
        return _ok()

    async def _fake_convert(scenario):
        return {"consumer": "platform", "converted": dict(scenario)}

    from app.services import gimbal_launcher as gl, plate_client as pc
    monkeypatch.setattr(gl, "launch", _capture)
    monkeypatch.setattr(pc, "convert", _fake_convert)

    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-coerce", "dataSetIds": [dataset_id],
    })
    assert r.status_code == 201, r.text

    await wait_until(lambda: len(cases) >= 1)
    vars_out = cases[0]["config"]["vars"]
    assert vars_out["qty"] == 2          # int,而非 "2"("2" == 2 为 False)
    assert vars_out["ok"] is False       # bool,而非 "false"
    assert vars_out["ratio"] == 2.5
    assert vars_out["note"] == "y"


async def test_run_fills_plate_required_meta_defaults(
    client: AsyncClient, monkeypatch
) -> None:
    """存量场景 meta 缺 plate 必填字段(UI 不采集 requirementRef 等)→
    compose 阶段补默认,发往 plate /convert 的 payload 完整。

    回归自线上(sc-test-5nhvaloj6,2026-08-24):preview/export 路由
    一直在发送前补 ``fill_plate_defaults``,run 执行链漏做 → 4 行
    全部 plate_rejected ``meta.requirementRef Field required``。
    make_draft 的 meta 本就不带 requirementRef/createTime,正是
    存量场景的形状。
    """
    headers = await register_and_login(client)
    await client.post(
        "/api/scenarios", headers=headers, json=make_draft("sc-meta-def", steps=STEPS)
    )

    sent: list[dict] = []

    async def _capture(case_path, *, step_to=None, report_dir=None,
                       cwd=None, timeout=None, engine_log_path=None):
        return _ok()

    async def _record_convert(scenario):
        sent.append(scenario)
        return {"consumer": "platform", "converted": dict(scenario)}

    from app.services import gimbal_launcher as gl, plate_client as pc
    monkeypatch.setattr(gl, "launch", _capture)
    monkeypatch.setattr(pc, "convert", _record_convert)

    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-meta-def", "dataSetIds": [],
    })
    assert r.status_code == 201, r.text

    await wait_until(lambda: len(sent) >= 1)
    meta = sent[0]["meta"]
    assert meta["requirementRef"] == []      # plate 必填,compose 补默认
    assert meta["createTime"]                # plate 必填,缺失取当前时刻
    assert sent[0]["kind"] == "scenario"
    # 已有值不被覆盖(setdefault 语义)
    assert meta["scenarioId"] == "sc-meta-def"


async def test_stale_env_key_silently_ignored(client, monkeypatch):
    """D2:RunRequest 删 env 后,旧客户端仍发 env 键 → 静默忽略不 422,
    config_json 不再留痕 envId。"""
    from app.services import gimbal_launcher as gl, plate_client as pc, run_dispatcher

    async def _fake_launch(case_path, *, step_to=None, report_dir=None,
                           cwd=None, timeout=None, engine_log_path=None):
        return _ok()

    async def _fake_convert(scenario):
        return {"consumer": "platform", "converted": dict(scenario)}

    headers = await register_and_login(client)
    await client.post(
        "/api/scenarios", headers=headers, json=make_draft("sc-stale-env")
    )
    monkeypatch.setattr(gl, "launch", _fake_launch)
    monkeypatch.setattr(pc, "convert", _fake_convert)
    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-stale-env", "dataSetIds": [],
        "env": {"envId": "dev-local", "name": "dev-local", "baseUrl": "http://x"},
    })
    assert r.status_code == 201, r.text
    run_id = r.json()["runId"]
    await wait_until(
        lambda: list(run_dispatcher._run_dir(run_id).rglob("case.json"))
    )
    # config_json 不再留痕 envId
    exec_row = (await client.get("/api/executions", headers=headers)).json()
    assert all("envId" not in (e.get("config") or {}) for e in exec_row.get("items", []))
