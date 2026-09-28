"""P2-06/C9 SSE + P2-07/C10 事件查询 API。

覆盖:组合筛选与聚合读面、SSE 帧序与 Last-Event-ID 续传、终态 done
收口(含无事件存量执行)、越权 404。
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import sqlalchemy as sa

from app.core import db as db_module
from app.models.execution import Execution
from app.services import execution_store
from tests.helpers import register_and_login


def _ev(seq: int, **labels) -> dict:
    d = {
        "event_type": "step.end", "seq": seq,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "step_id": f"step-{seq:03d}", "status": "passed", "duration_ms": 1.0,
    }
    d.update(labels)
    return d


async def _seed_execution(headers_owner=None, *, client=None, status="done") -> int:
    async with db_module.SessionLocal() as s:
        ex = Execution(scenario_id="sc-sse", owner_name="t", status=status,
                       total_runs=1, passed=1)
        s.add(ex)
        await s.commit()
        return ex.id


class TestQueryApi:

    async def test_events_query_filters(self, client):
        headers = await register_and_login(client)
        eid = await _seed_execution()
        # 收归到当前用户(owner 校验)
        from app.models.user import User
        async with db_module.SessionLocal() as s:
            me = (await s.execute(sa.select(User).order_by(User.id.desc())
                                  )).scalars().first()
            ex = await s.get(Execution, eid)
            ex.owner_id = me.id
            await s.commit()

        async with db_module.SessionLocal() as s:
            await execution_store.insert_events(s, eid, [
                _ev(1, module="fin", unit="u-1", status="failed"),
                _ev(2, module="logi", unit="u-2"),
                _ev(3, module="fin", unit="u-2"),
            ])
            await s.commit()

        r = await client.get(f"/api/executions/{eid}/events", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["count"] == 3

        r = await client.get(f"/api/executions/{eid}/events",
                             headers=headers, params={"module": "fin"})
        assert [i["seq"] for i in r.json()["items"]] == [1, 3]

        r = await client.get(f"/api/executions/{eid}/events",
                             headers=headers, params={"unit": "u-1",
                                                      "event_type": "step.end"})
        assert [i["seq"] for i in r.json()["items"]] == [1]

        r = await client.get(f"/api/executions/{eid}/events/counts",
                             headers=headers)
        assert r.status_code == 200 and "byCategory" in r.json()

    async def test_other_users_execution_404(self, client):
        headers = await register_and_login(client)
        eid = await _seed_execution()   # owner_id=None → 不属于任何人
        r = await client.get(f"/api/executions/{eid}/events", headers=headers)
        assert r.status_code == 404
        r = await client.get(f"/api/executions/{eid}/events/stream",
                             headers=headers)
        assert r.status_code == 404


class TestSseStream:

    async def test_stream_delivers_events_then_done(self, client):
        headers = await register_and_login(client)
        eid = await _seed_execution(status="done")
        from app.models.user import User
        async with db_module.SessionLocal() as s:
            me = (await s.execute(sa.select(User).order_by(User.id.desc())
                                  )).scalars().first()
            (await s.get(Execution, eid)).owner_id = me.id
            await execution_store.insert_events(s, eid, [
                _ev(1), _ev(2),
                {"event_type": "run.finished", "seq": 3, "exit_code": 0,
                 "total": 1, "passed": 1, "attempts": 1,
                 "timestamp": datetime.now(timezone.utc).isoformat()},
            ])
            await s.commit()

        lines: list[str] = []
        async with client.stream("GET",
                                 f"/api/executions/{eid}/events/stream",
                                 headers=headers) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            async for chunk in resp.aiter_text():
                lines.append(chunk)
                if "event: done" in "".join(lines):
                    break
        text = "".join(lines)
        assert "id: 1" in text and "id: 2" in text and "id: 3" in text
        assert '"event_type": "step.end"' in text
        assert "event: done" in text

    async def test_last_event_id_resume(self, client):
        """Last-Event-ID=2 → 只推 seq>2 的事件(断线续传不重复)。"""
        headers = await register_and_login(client)
        eid = await _seed_execution(status="done")
        from app.models.user import User
        async with db_module.SessionLocal() as s:
            me = (await s.execute(sa.select(User).order_by(User.id.desc())
                                  )).scalars().first()
            (await s.get(Execution, eid)).owner_id = me.id
            await execution_store.insert_events(s, eid, [
                _ev(1), _ev(2), _ev(3),
                {"event_type": "run.finished", "seq": 4, "exit_code": 0,
                 "total": 1, "passed": 1, "attempts": 1,
                 "timestamp": datetime.now(timezone.utc).isoformat()},
            ])
            await s.commit()

        lines: list[str] = []
        async with client.stream(
                "GET", f"/api/executions/{eid}/events/stream",
                headers={**headers, "Last-Event-ID": "2"}) as resp:
            async for chunk in resp.aiter_text():
                lines.append(chunk)
                if "event: done" in "".join(lines):
                    break
        text = "".join(lines)
        assert "id: 1" not in text and "id: 2" not in text
        assert "id: 3" in text and "id: 4" in text

    async def test_legacy_execution_without_events_closes_done(self, client):
        """终态但无事件流的存量执行:首轮空轮即 done,不悬挂。"""
        headers = await register_and_login(client)
        eid = await _seed_execution(status="done")
        from app.models.user import User
        async with db_module.SessionLocal() as s:
            me = (await s.execute(sa.select(User).order_by(User.id.desc())
                                  )).scalars().first()
            (await s.get(Execution, eid)).owner_id = me.id
            await s.commit()

        lines: list[str] = []
        async with client.stream("GET",
                                 f"/api/executions/{eid}/events/stream",
                                 headers=headers) as resp:
            async for chunk in resp.aiter_text():
                lines.append(chunk)
                if "event: done" in "".join(lines):
                    break
        assert "event: done" in "".join(lines)
