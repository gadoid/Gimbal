"""M6-1:execution_rows 转正(终态落库 + 分页信封 + JSONL 只读归档)。"""
from __future__ import annotations

from app.core import db as db_module
from app.models.execution import ExecutionRow
from tests.helpers import ensure_fk_users, register_and_login


async def _seed_exec(owner_id: int) -> int:
    from app.models.execution import Execution

    async with db_module.SessionLocal() as s:
        ex = Execution(scenario_id="sc-m6", owner_id=owner_id, status="done",
                       total_runs=3, passed=2, failed=1, config_json={})
        s.add(ex)
        await s.commit()
        return ex.id


async def _seed_rows(exec_id: int, n: int) -> None:
    from datetime import datetime, timedelta, timezone

    base = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
    async with db_module.SessionLocal() as s:
        for i in range(n):
            s.add(ExecutionRow(
                execution_id=exec_id, seq=i, dataset_id=None, injection_id=None,
                row_index=0, rep=i, status="passed" if i % 2 == 0 else "failed",
                case_dir=f"case-{i:03d}", started_at=base,
                finished_at=base + timedelta(seconds=i + 1),
            ))
        await s.commit()


async def test_rows_envelope_pagination(client):
    h = await register_and_login(client, "m6rows", "pw123456")
    eid = await _seed_exec(1)
    await _seed_rows(eid, 5)

    r = await client.get(f"/api/executions/{eid}/rows", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert {"items", "total", "page", "pageSize"} <= set(body)
    assert body["total"] == 5 and len(body["items"]) == 5
    # seq 升序
    assert [it["seq"] for it in body["items"]] == [0, 1, 2, 3, 4]
    # 时间戳 naive-UTC 串(与 registry 口径一致)
    assert body["items"][0]["finishedAt"] == "2026-09-20T12:00:01"

    r2 = await client.get(f"/api/executions/{eid}/rows", headers=h,
                          params={"page": 2, "page_size": 2})
    b2 = r2.json()
    assert b2["total"] == 5 and b2["page"] == 2 and b2["pageSize"] == 2
    assert [it["seq"] for it in b2["items"]] == [2, 3]

    # 超尾页:空页而非 404
    r3 = await client.get(f"/api/executions/{eid}/rows", headers=h,
                          params={"page": 9})
    assert r3.status_code == 200 and r3.json()["items"] == []


async def test_rows_legacy_execution_falls_back_empty(client, monkeypatch, tmp_path):
    """无 DB 行的存量单(M6 前):JSONL 兜底(tmp DATA_DIR 无归档 → 空集)。"""
    from app.core.config import settings

    (tmp_path / "runs").mkdir()
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    h = await register_and_login(client, "m6rows2", "pw123456")
    eid = await _seed_exec(1)
    r = await client.get(f"/api/executions/{eid}/rows", headers=h)
    assert r.status_code == 200
    assert r.json() == {"items": [], "total": 0, "page": 1, "pageSize": 200}


async def test_persist_row_terminal_writes_db(client):
    """终态即落库(直调 helper):崩溃窗口不丢已终态行。"""
    from app.services.run_dispatcher import RowState, _persist_row_terminal

    h = await register_and_login(client, "m6rows3", "pw123456")
    eid = await _seed_exec(1)
    state = RowState(
        seq=0, dataset_id="ds-1", row_index=0, rep=0, status="passed",
        case_dir="case-000", started_at="2026-09-20T12:00:00Z",
        finished_at="2026-09-20T12:00:05Z", injection_id=None,
    )
    await _persist_row_terminal(db_module.SessionLocal, eid, state)

    from sqlalchemy import select

    async with db_module.SessionLocal() as s:
        row = (await s.execute(
            select(ExecutionRow).where(ExecutionRow.execution_id == eid)
        )).scalar_one()
    assert row.status == "passed" and row.seq == 0 and row.case_dir == "case-000"

    # 读侧回读:naive-UTC ISO 串
    r = await client.get(f"/api/executions/{eid}/rows", headers=h)
    it = r.json()["items"][0]
    assert it["finishedAt"] == "2026-09-20T12:00:05"
