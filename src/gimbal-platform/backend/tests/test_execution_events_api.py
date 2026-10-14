"""P2-06/C9 SSE + P2-07/C10 事件查询 API。

覆盖:组合筛选与聚合读面、SSE 帧序与 Last-Event-ID 续传、终态 done
收口(含无事件存量执行)、越权 404。
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

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


async def _own_execution(eid: int) -> None:
    """把执行收归当前注册用户(OwnedExecution 鉴权前提)。"""
    from app.models.user import User
    async with db_module.SessionLocal() as s:
        me = (await s.execute(sa.select(User).order_by(User.id.desc())
                              )).scalars().first()
        (await s.get(Execution, eid)).owner_id = me.id
        await s.commit()


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
    """SSE 帧结构断言(AD6:按帧解析 id/event/data 字段,禁子串匹配——
    字面量 \\n 缺陷正是靠子串断言逃过 CI 的)。"""

    @staticmethod
    def _parse_frames(text: str) -> list[dict]:
        """按 SSE 线协议切帧:真 \\n\\n 分帧 → 解析 id/event/data 字段。"""
        frames = []
        for block in text.split("\n\n"):
            frame: dict = {}
            for line in block.split("\n"):
                if line.startswith("id:"):
                    frame["id"] = line[3:].strip()
                elif line.startswith("event:"):
                    frame["event"] = line[6:].strip()
                elif line.startswith("data:"):
                    frame["data"] = json.loads(line[5:].strip())
            if frame:
                frames.append(frame)
        return frames

    @classmethod
    async def _collect(cls, client, url: str, headers: dict) -> list[dict]:
        chunks: list[str] = []
        async with client.stream("GET", url, headers=headers) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            async for chunk in resp.aiter_text():
                chunks.append(chunk)
                if "event: done" in chunk:
                    break
        return cls._parse_frames("".join(chunks))

    async def test_stream_delivers_events_then_done(self, client):
        headers = await register_and_login(client)
        eid = await _seed_execution(status="done")
        await _own_execution(eid)
        async with db_module.SessionLocal() as s:
            await execution_store.insert_events(s, eid, [
                _ev(1), _ev(2),
                {"event_type": "run.finished", "seq": 3, "exit_code": 0,
                 "total": 1, "passed": 1, "attempts": 1,
                 "timestamp": datetime.now(timezone.utc).isoformat()},
            ])
            # 夹带一条日志行(负数 seq):事件流显式 kind=event,不得混入
            await execution_store.insert_logs(s, eid, [
                {"timestamp": datetime.now(timezone.utc).isoformat(),
                 "level": "INFO", "message": "log-row", "category": "core"},
            ], seq_base=0)
            await s.commit()

        frames = await self._collect(
            client, f"/api/executions/{eid}/events/stream", headers)
        ev_frames = [f for f in frames if f.get("event") == "ev"]
        done = [f for f in frames if f.get("event") == "done"]

        # 帧结构:两事件帧 + run.finished + 终态 done;id 递增;data 合法 JSON
        assert [f["id"] for f in ev_frames] == ["1", "2", "3"]
        for f in ev_frames[:2]:
            assert f["data"]["kind"] == "event"
            assert f["data"]["event_type"] == "step.end"
        assert ev_frames[2]["data"]["event_type"] == "run.finished"
        assert len(done) == 1
        assert done[0]["data"]["status"] == "done"
        # 日志行(kind=log)不出现在事件流(AD5 显式 kind=event)
        assert all(f["data"].get("message") != "log-row" for f in ev_frames)

    async def test_last_event_id_resume(self, client):
        """Last-Event-ID=2 → 只推 seq>2 的事件(断线续传不重复)。"""
        headers = await register_and_login(client)
        eid = await _seed_execution(status="done")
        await _own_execution(eid)
        async with db_module.SessionLocal() as s:
            await execution_store.insert_events(s, eid, [
                _ev(1), _ev(2), _ev(3),
                {"event_type": "run.finished", "seq": 4, "exit_code": 0,
                 "total": 1, "passed": 1, "attempts": 1,
                 "timestamp": datetime.now(timezone.utc).isoformat()},
            ])
            await s.commit()

        frames = await self._collect(
            client, f"/api/executions/{eid}/events/stream",
            {**headers, "Last-Event-ID": "2"})
        ids = [f["id"] for f in frames if f.get("event") == "ev"]
        assert ids == ["3", "4"], f"续传不得重复/丢失: {ids}"

    async def test_legacy_execution_without_events_closes_done(self, client):
        """终态但无事件流的存量执行:首轮空轮即 done,不悬挂。"""
        headers = await register_and_login(client)
        eid = await _seed_execution(status="done")
        await _own_execution(eid)
        frames = await self._collect(
            client, f"/api/executions/{eid}/events/stream", headers)
        assert any(f.get("event") == "done" for f in frames)
        assert [f for f in frames if f.get("event") == "ev"] == []


class TestLogsStream:
    """日志流(批 2/AD5):tail 游标=入库 id,backfill 仅首连,服务端筛选,
    终态 done;「先 ts 后入库不缺行」回归闸。"""

    @staticmethod
    async def _seed_logs(eid: int, rows: list[tuple[str, str, str]]) -> None:
        """rows: (ts_offset_sec, level, message) 按入库顺序(=id 顺序)。

        必须单批插入:insert_logs 的 seq 按 seq_base-len+i 分配,逐行
        单批会每批都拿到同一 seq 撞 (execution_id, seq) 唯一约束被
        on_conflict_do_nothing 静默吞掉(只活一行)。
        """
        base = datetime(2026, 10, 14, 2, 0, 0, tzinfo=timezone.utc)
        async with db_module.SessionLocal() as s:
            await execution_store.insert_logs(s, eid, [
                {"timestamp": (base + timedelta(seconds=off)).isoformat(),
                 "level": lv, "message": msg, "category": "core"}
                for off, lv, msg in rows
            ], seq_base=0)
            await s.commit()

    async def _read(self, client, url: str, headers: dict,
                    until_frames: int = 100, timeout: float = 10.0):
        """读流直到帧数达标/超时;返回 (frames, closed_by_server)。"""
        import asyncio
        chunks: list[str] = []

        async def _do() -> bool:
            async with client.stream("GET", url, headers=headers) as resp:
                assert resp.status_code == 200
                async for chunk in resp.aiter_text():
                    chunks.append(chunk)
                    if len([c for c in "".join(chunks).split("\n\n")
                            if c.strip()]) >= until_frames:
                        return False   # 足够,主动断开
                return True            # 服务端关流(done 收口)
        closed = await asyncio.wait_for(_do(), timeout)
        frames = TestSseStream._parse_frames("".join(chunks))
        return frames, closed

    async def test_backfill_then_done_on_terminal(self, client):
        headers = await register_and_login(client)
        eid = await _seed_execution(status="done")
        await _own_execution(eid)
        await self._seed_logs(eid, [(i, "INFO", f"m-{i}") for i in range(5)])

        frames, closed = await self._read(
            client, f"/api/executions/{eid}/logs/stream", headers,
            until_frames=10)   # 高于 5+done:让服务端关流判定 closed
        logs = [f for f in frames if f.get("event") == "log"]
        done = [f for f in frames if f.get("event") == "done"]
        # backfill 全量 5 行,id 升序 + 终态 done
        assert [f["data"]["message"] for f in logs] == [f"m-{i}" for i in range(5)]
        assert len(done) == 1 and done[0]["data"]["status"] == "done"
        assert closed

    async def test_last_event_id_exact_resume_no_backfill(self, client):
        headers = await register_and_login(client)
        eid = await _seed_execution(status="done")
        await _own_execution(eid)
        await self._seed_logs(eid, [(i, "INFO", f"m-{i}") for i in range(4)])
        # 找 m-1 的行 id(静态查询,ts 序返回)
        r = await client.get(f"/api/executions/{eid}/events",
                             headers=headers, params={"kind": "log"})
        ids = {it["message"]: it["id"] for it in r.json()["items"]}
        anchor = ids["m-1"]

        frames, _ = await self._read(
            client, f"/api/executions/{eid}/logs/stream",
            {**headers, "Last-Event-ID": str(anchor)}, until_frames=3)
        msgs = [f["data"]["message"] for f in frames if f.get("event") == "log"]
        # 精确续传:只推 anchor 之后,不重放不回看
        assert msgs == ["m-2", "m-3"], msgs

    async def test_server_side_filter_level_min(self, client):
        headers = await register_and_login(client)
        eid = await _seed_execution(status="done")
        await _own_execution(eid)
        await self._seed_logs(eid, [
            (1, "INFO", "info-row"), (2, "WARNING", "warn-row"),
            (3, "INFO", "info-row-2"), (4, "ERROR", "err-row")])

        frames, _ = await self._read(
            client, f"/api/executions/{eid}/logs/stream?level_min=WARNING",
            headers, until_frames=3)
        msgs = [f["data"]["message"] for f in frames if f.get("event") == "log"]
        assert msgs == ["warn-row", "err-row"], msgs

    async def test_tail_by_id_no_missing_rows_on_ts_disorder(self, client):
        """回归闸(评审二轮):ts 与入库序完全倒置时,流仍一行不缺。

        ts cursor 版会漏:发出 id=1(ts=T3)后 cursor=T3,晚入库但 ts 更早
        的 id=2/3 永远落在 cursor 之下。id tail 三行全达。
        """
        headers = await register_and_login(client)
        eid = await _seed_execution(status="done")
        await _own_execution(eid)
        await self._seed_logs(eid, [
            (30, "INFO", "id1-ts30"),    # 先入库,ts 最晚
            (10, "INFO", "id2-ts10"),    # 后入库,ts 最早
            (20, "INFO", "id3-ts20"),
        ])

        frames, _ = await self._read(
            client, f"/api/executions/{eid}/logs/stream", headers,
            until_frames=4)
        logs = [f for f in frames if f.get("event") == "log"]
        # tail 按 id(入库序)送达全部三行
        assert [f["data"]["message"] for f in logs] == ["id1-ts30", "id2-ts10", "id3-ts20"]
        # 对照:静态查询(AD4)按 ts 序 —— 两轴分工的显式证明
        r = await client.get(f"/api/executions/{eid}/events",
                             headers=headers, params={"kind": "log"})
        assert [it["message"] for it in r.json()["items"]] == [
            "id2-ts10", "id3-ts20", "id1-ts30"]

    async def test_running_execution_streams_without_done(self, client):
        """running 执行:日志帧送达但不发 done(流不收口)。

        httpx 0.28 的 ASGITransport 会跑完整个 app 才返回响应(无限流在
        传输层死等),故直调端点函数迭代生成器,绕开传输层。
        """
        import asyncio

        from app.routers.executions import stream_execution_logs

        class _FakeRequest:
            async def is_disconnected(self) -> bool:
                return False

        # 直调端点(传 ex 行)绕过 OwnedExecution 依赖,无需属主/登录
        eid = await _seed_execution(status="running")
        await self._seed_logs(eid, [(i, "INFO", f"r-{i}") for i in range(3)])
        async with db_module.SessionLocal() as s:
            ex = await s.get(Execution, eid)

            resp = await stream_execution_logs(ex=ex, request=_FakeRequest())
            chunks: list[str] = []

            async def _collect() -> None:
                async for chunk in resp.body_iterator:
                    chunks.append(chunk)
                    if len([c for c in "".join(chunks).split("\n\n")
                            if c.strip()]) >= 3:
                        return          # 3 帧已足,主动停读(客户端断开语义)
            await asyncio.wait_for(_collect(), timeout=8.0)

        frames = TestSseStream._parse_frames("".join(chunks))
        logs = [f for f in frames if f.get("event") == "log"]
        assert [f["data"]["message"] for f in logs] == ["r-0", "r-1", "r-2"]
        assert not any(f.get("event") == "done" for f in frames), (
            "running 执行不得发 done —— §7 四步协议:done 只在终态且排空后")


class TestOrderingAxes:
    """排序轴(AD4):事件=seq 语义序;日志/混合=(ts,id) 统一时间轴。"""

    @staticmethod
    async def _seed_mixed(eid: int) -> None:
        base = datetime(2026, 10, 14, 1, 0, 0, tzinfo=timezone.utc)
        async with db_module.SessionLocal() as s:
            # 事件:seq 1..3(ts 乱序制造 —— seq 才是事件语义序)
            await execution_store.insert_events(s, eid, [
                _ev(1, timestamp=(base + timedelta(seconds=30)).isoformat()),
                _ev(2, timestamp=(base + timedelta(seconds=10)).isoformat()),
                _ev(3, timestamp=(base + timedelta(seconds=20)).isoformat()),
            ])
            # 日志两批:先入库的批 ts 晚、后入库的批 ts 早 —— 按 seq 是
            # 跨批倒序的(负数轴),按 (ts,id) 应为正序
            await execution_store.insert_logs(s, eid, [
                {"timestamp": (base + timedelta(seconds=50)).isoformat(),
                 "level": "INFO", "message": "late-batch"},
            ], seq_base=0)
            await execution_store.insert_logs(s, eid, [
                {"timestamp": (base + timedelta(seconds=5)).isoformat(),
                 "level": "INFO", "message": "early-batch"},
            ], seq_base=-10)
            await s.commit()

    async def test_event_axis_is_seq(self, client):
        headers = await register_and_login(client)
        eid = await _seed_execution()
        await _own_execution(eid)
        await self._seed_mixed(eid)
        r = await client.get(f"/api/executions/{eid}/events",
                             headers=headers, params={"kind": "event"})
        assert [i["seq"] for i in r.json()["items"]] == [1, 2, 3]

    async def test_log_axis_is_ts(self, client):
        headers = await register_and_login(client)
        eid = await _seed_execution()
        await _own_execution(eid)
        await self._seed_mixed(eid)
        r = await client.get(f"/api/executions/{eid}/events",
                             headers=headers, params={"kind": "log"})
        msgs = [i["message"] for i in r.json()["items"]]
        # ts 升序:early(05s) 在前,late(50s) 在后 —— 与入库/seq 顺序相反
        assert msgs == ["early-batch", "late-batch"], msgs

    async def test_mixed_axis_is_ts(self, client):
        headers = await register_and_login(client)
        eid = await _seed_execution()
        await _own_execution(eid)
        await self._seed_mixed(eid)
        r = await client.get(f"/api/executions/{eid}/events", headers=headers)
        ts_list = [i["ts"] for i in r.json()["items"]]
        assert ts_list == sorted(ts_list), "混合时间轴必须 ts 单调"
