"""b2.5 收尾批回归测试(评审 P1-2/P2)。

- merge_resolve_effective:派发链回写分流(PIN 写副本/INTEGRATION 只写
  pins/working 不写)—— v1.0 风险 R5 的防线,此前无直接测试;
- graph_pins_with_identity:图台账 integration 标识补取(只进台账、
  resolver 失败保留裸值且落 warning;真身 plate_client.resolve 直传,
  签名漂移即测试失败);
- environments 拒绝 integration 系统声明版本线(plate 不可达跳过)。
"""
from __future__ import annotations

import json
import logging

import httpx
import pytest

from app.services.run_semantics import (
    INTEGRATION,
    PIN,
    merge_resolve_effective,
    graph_pins_with_identity,
)


class TestMergeResolveEffective:
    def test_pin_writes_both(self):
        meta = {"fin": "1.0#1"}
        pins: dict = {}
        merge_resolve_effective(meta, pins, {
            "fin": {"effective": "1.0#2"}})
        assert pins == {"fin": "1.0#2"}
        assert meta == {"fin": "1.0#2"}, "PIN:执行副本钉到具体修订"

    def test_integration_pins_only(self):
        meta = {"jira": "integration"}
        pins: dict = {}
        merge_resolve_effective(meta, pins, {
            "jira": {"effective": "integration@abc123"}})
        assert pins == {"jira": "integration@abc123"}
        assert meta == {"jira": "integration"}, \
            "INTEGRATION:副本保持声明值(integration@ 是记录值,写副本即 422)"

    def test_working_and_empty_noop(self):
        meta = {"fin": "working", "x": "1.0#1"}
        pins: dict = {}
        merge_resolve_effective(meta, pins, {
            "fin": {"effective": "working"},
            "x": {"effective": ""},           # 空 effective 不写
            "y": {"effective": "1.0#9"},      # 未声明系统:pins 记,副本不动
        })
        assert pins == {"y": "1.0#9"}
        assert meta == {"fin": "working", "x": "1.0#1"}


class TestGraphPinsWithIdentity:
    async def test_integration_backfilled(self):
        async def resolver(meta, endpoints):
            assert meta == {"jira": "integration"}
            assert endpoints == {}
            return {"jira": {"effective": "integration@deadbeef"}}

        out = await graph_pins_with_identity(
            {"fin": "1.0#2", "jira": "integration"}, resolver)
        assert out == {"fin": "1.0#2", "jira": "integration@deadbeef"}

    async def test_resolver_failure_keeps_bare_and_logs(self, caplog):
        async def boom(meta, endpoints):
            raise RuntimeError("plate down")

        with caplog.at_level(logging.WARNING,
                             logger="app.services.run_semantics"):
            out = await graph_pins_with_identity(
                {"jira": "integration"}, boom)
        assert out == {"jira": "integration"}, "台账性质:失败保留裸值不阻断"
        assert any("标识补取失败" in r.message for r in caplog.records), \
            "台账性质失败也不得无痕"

    async def test_no_integration_is_passthrough(self):
        calls = []

        async def resolver(meta, endpoints):
            calls.append(meta)
            return {}

        out = await graph_pins_with_identity({"fin": "1.0#2"}, resolver)
        assert out == {"fin": "1.0#2"} and calls == []

    async def test_real_resolve_signature(self, monkeypatch):
        """真身 plate_client.resolve 直传:resolver 签名漂移会 TypeError
        被吞成裸值台账(b2.5 回归),此用例让漂移直接测试失败。"""
        from app.services import plate_client

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/system/action/resolve"
            body = json.loads(request.content)
            assert body["meta_plate"] == {"jira": "integration"}
            assert body["endpoints"] == {}
            return httpx.Response(200, json={
                "ok": True, "dim": "system",
                "data": {"item": {
                    "jira": {"effective": "integration@deadbeef",
                             "available": True, "changed_endpoints": []}}},
            })

        monkeypatch.setattr(
            plate_client, "get_client",
            lambda: httpx.AsyncClient(
                transport=httpx.MockTransport(handler),
                base_url="http://plate-resolve-mock"))

        out = await graph_pins_with_identity(
            {"fin": "1.0#2", "jira": "integration"}, plate_client.resolve)
        assert out == {"fin": "1.0#2", "jira": "integration@deadbeef"}


class TestEnvironmentsRejectIntegration:
    @pytest.fixture
    def plate_kind_mock(self, monkeypatch):
        """GET /api/system/{id} → jira=integration,其余 sut(404→None)。"""
        from app.services import plate_client

        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path.startswith("/api/system/"):
                sid = path.rstrip("/").rsplit("/", 1)[-1]
                if sid == "jira":
                    return httpx.Response(200, json={
                        "ok": True, "dim": "system",
                        "data": {"item": {"id": "jira", "name": "jira",
                                          "service_count": 1,
                                          "endpoint_count": 2,
                                          "kind": "integration"}},
                    })
                return httpx.Response(404, json={"ok": False})
            return httpx.Response(503, json={"ok": False})

        monkeypatch.setattr(
            plate_client, "get_client",
            lambda: httpx.AsyncClient(
                transport=httpx.MockTransport(handler),
                base_url="http://plate-kind-mock"))

    async def _mk_env(self, client, headers):
        r = await client.post("/api/environments", headers=headers,
                              json={"name": "b25-env"})
        assert r.status_code in (200, 201), r.text
        return r.json()["id"]

    async def test_reject_integration_lines(self, client, fresh_db,
                                            plate_kind_mock):
        from tests.helpers import register_and_login

        h = await register_and_login(client, "b25_admin", "pw123456")
        from app.core import db as db_module
        from app.models.user import User
        from sqlalchemy import select

        async with db_module.SessionLocal() as s:
            u = (await s.execute(select(User).where(
                User.username == "b25_admin"))).scalar()
            u.role = "admin"
            await s.commit()
        eid = await self._mk_env(client, h)
        r = await client.put(f"/api/environments/{eid}", headers=h,
                               json={"lines": {"jira": "1.0"}})
        assert r.status_code == 422, r.text
        assert "integration_system_no_lines" in r.text
        assert "jira" in r.text

    async def test_sut_lines_pass(self, client, fresh_db, plate_kind_mock):
        from tests.helpers import register_and_login

        h = await register_and_login(client, "b25_admin2", "pw123456")
        from app.core import db as db_module
        from app.models.user import User
        from sqlalchemy import select

        async with db_module.SessionLocal() as s:
            u = (await s.execute(select(User).where(
                User.username == "b25_admin2"))).scalar()
            u.role = "admin"
            await s.commit()
        eid = await self._mk_env(client, h)
        r = await client.put(f"/api/environments/{eid}", headers=h,
                               json={"lines": {"fin": "1.0"}})
        assert r.status_code == 200, r.text

    async def test_plate_unreachable_skips(self, client, fresh_db,
                                            monkeypatch):
        from tests.helpers import register_and_login

        h = await register_and_login(client, "b25_admin3", "pw123456")
        from app.core import db as db_module
        from app.models.user import User
        from app.services import plate_client
        from sqlalchemy import select

        async with db_module.SessionLocal() as s:
            u = (await s.execute(select(User).where(
                User.username == "b25_admin3"))).scalar()
            u.role = "admin"
            await s.commit()

        def boom():
            raise plate_client.PlateUnavailableError("plate_unavailable: t")

        monkeypatch.setattr(plate_client, "get_client", boom)
        eid = await self._mk_env(client, h)
        r = await client.put(f"/api/environments/{eid}", headers=h,
                               json={"lines": {"jira": "1.0"}})
        assert r.status_code == 200, "不可达跳过(配置面;执行期门仍在): " + r.text
