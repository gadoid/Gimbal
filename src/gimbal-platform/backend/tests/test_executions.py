"""Read-side tests for the executions API (V3 scope).

V3 retired the V1 subprocess chain AND the per-run exec_runs cluster
(detail runs / report / log / SSE / run deletion).  Creation lives at
POST /api/runs via run_dispatcher; observability is the Execution
counters + ``data/runs/<date>.jsonl`` dispatch logs (file-based, not
API).  These tests cover the surviving read surface: list/detail
isolation, execution deletion, and retired endpoints.  Rows are
inserted directly via SQLAlchemy — no subprocess, no loader.
"""
from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select

from .helpers import register_and_login


async def _login_alice(client: AsyncClient) -> dict:
    return await register_and_login(client)


async def _insert_execution(
    *,
    scenario_id: str = "sc_e2e",
    total_runs: int = 1,
    passed: int = 0,
    failed: int = 0,
    status: str = "done",
) -> int:
    """Insert an Execution for alice."""
    from app.core.db import SessionLocal
    from app.models import Execution, User

    async with SessionLocal() as s:
        alice = (
            await s.execute(select(User).where(User.username == "alice"))
        ).scalar_one()
        ex = Execution(
            scenario_id=scenario_id,
            owner_id=alice.id,
            status=status,
            total_runs=total_runs,
            passed=passed,
            failed=failed,
        )
        s.add(ex)
        await s.commit()
        await s.refresh(ex)
        return ex.id


# ── list / detail isolation ────────────────────────────────────
async def test_list_executions_only_returns_owners(client: AsyncClient) -> None:
    a_auth = await _login_alice(client)
    await _insert_execution(scenario_id="sc_a")
    await client.post(
        "/api/auth/register", json={"username": "bob", "password": "bobpass456"}
    )
    b_login = await client.post(
        "/api/auth/login", json={"username": "bob", "password": "bobpass456"}
    )
    b_auth = {"Authorization": f"Bearer {b_login.json()['access_token']}"}
    # Bob has no executions.
    b_list = await client.get("/api/executions", headers=b_auth)
    assert b_list.status_code == 200
    assert b_list.json()["total"] == 0

    a_list = await client.get("/api/executions", headers=a_auth)
    assert a_list.json()["total"] == 1
    assert a_list.json()["items"][0]["scenario_id"] == "sc_a"

    # Cross-owner detail access: bob can't read alice's execution.
    eid = a_list.json()["items"][0]["id"]
    r = await client.get(f"/api/executions/{eid}", headers=b_auth)
    assert r.status_code == 404

    # Detail is the same shape as the list item (no more runs/report/log).
    d = await client.get(f"/api/executions/{eid}", headers=a_auth)
    assert d.status_code == 200
    assert d.json()["scenario_id"] == "sc_a"
    assert "runs" not in d.json()


async def test_unknown_execution_404(client: AsyncClient) -> None:
    auth = await _login_alice(client)
    r = await client.get("/api/executions/9999", headers=auth)
    assert r.status_code == 404


# ── delete execution ───────────────────────────────────────────
async def test_delete_execution_removes_rows(client: AsyncClient) -> None:
    auth = await _login_alice(client)
    eid = await _insert_execution(total_runs=1, passed=1)
    d = await client.delete(f"/api/executions/{eid}", headers=auth)
    assert d.status_code == 204
    g = await client.get(f"/api/executions/{eid}", headers=auth)
    assert g.status_code == 404


# ── V1 creation endpoints retired (P4) ─────────────────────────
async def test_post_execution_and_rerun_are_gone(client: AsyncClient) -> None:
    """POST /api/executions and …/rerun must no longer exist (405/404)."""
    auth = await _login_alice(client)
    eid = await _insert_execution()
    r = await client.post(
        "/api/executions",
        headers=auth,
        json={"scenario_id": "sc_x", "n_runs": 1, "parallel": 1},
    )
    assert r.status_code == 405
    r = await client.post(f"/api/executions/{eid}/runs/1/rerun", headers=auth)
    assert r.status_code in (404, 405)


# ── V1 per-run cluster retired ─────────────────────────────────
async def test_v1_run_endpoints_are_gone(client: AsyncClient) -> None:
    auth = await _login_alice(client)
    eid = await _insert_execution()
    r = await client.get(f"/api/executions/{eid}/runs/1/log", headers=auth)
    assert r.status_code == 404
    r = await client.get(f"/api/executions/{eid}/runs/1/log/stream", headers=auth)
    assert r.status_code == 404
    r = await client.delete(f"/api/executions/{eid}/runs/1", headers=auth)
    assert r.status_code in (404, 405)  # only /api/executions/{id} DELETE exists


# ── list pagination ─────────────────────────────────────────────
async def test_list_pagination(client: AsyncClient) -> None:
    auth = await _login_alice(client)
    for _ in range(5):
        await _insert_execution(status="done")

    r = await client.get("/api/executions?limit=2&offset=1", headers=auth)
    body = r.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    ids = [it["id"] for it in body["items"]]
    assert ids == sorted(ids, reverse=True)  # id 倒序,offset=1 跳过最新


async def test_list_limit_bounds(client: AsyncClient) -> None:
    auth = await _login_alice(client)
    assert (
        await client.get("/api/executions?limit=0", headers=auth)
    ).status_code == 422
    assert (
        await client.get("/api/executions?limit=501", headers=auth)
    ).status_code == 422



# ── authz W4:执行可见收敛(方案 §9.3)──────────────────────────────
class TestExecutionVisibilityOwnerOnly:
    """执行及其一切子资源只有属主可见;admin/super_admin 同样 404
    (排查走审计)。属主面不受影响。"""

    async def test_admin_sees_nothing_of_others_execution(self, client):
        from tests.helpers import role_headers

        alice = await _login_alice(client)
        eid = await _insert_execution(status="done")
        for role in ("admin", "super_admin"):
            h = await role_headers(client, f"ev_{role}", role=role)
            assert (await client.get(
                f"/api/executions/{eid}", headers=h)).status_code == 404, role
            assert (await client.get(
                f"/api/executions/{eid}/rows", headers=h)).status_code == 404, role
            assert (await client.get(
                f"/api/executions/{eid}/events", headers=h)).status_code == 404, role
            assert (await client.get(
                f"/api/executions/{eid}/events/counts",
                headers=h)).status_code == 404, role
            assert (await client.get(
                f"/api/executions/{eid}/report", headers=h)).status_code == 404, role
            assert (await client.get(
                f"/api/executions/{eid}/scenario-snapshot",
                headers=h)).status_code == 404, role
            assert (await client.post(
                f"/api/executions/{eid}/cancel",
                headers=h)).status_code == 404, role
            assert (await client.get(
                f"/api/executions/{eid}/debug", headers=h)).status_code == 404, role

        # 属主本人照常
        assert (await client.get(
            f"/api/executions/{eid}", headers=alice)).status_code == 200

    async def test_admin_batch_summary_of_others_is_404(self, client):
        from tests.helpers import role_headers

        from app.core.db import SessionLocal

        await _login_alice(client)  # _insert_execution 依赖 alice 在场
        await _insert_execution(status="done")
        async with SessionLocal() as s:  # 挂上 batch_id(alice 的批次)
            from app.models import Execution
            from sqlalchemy import update
            await s.execute(update(Execution).where(
                Execution.batch_id.is_(None)).values(batch_id="b-w4"))
            await s.commit()
        h = await role_headers(client, "ev_bsup", role="super_admin")
        r = await client.get("/api/executions/batch-summary",
                             params={"batchId": "b-w4"}, headers=h)
        assert r.status_code == 404, r.text

    async def test_admin_cannot_query_others_by_token_id(self, client):
        """executions 列表的 tokenId 例外删除:admin 只能按**本人**令牌过滤。"""
        from tests.helpers import role_headers

        await _login_alice(client)  # 占掉首注
        from sqlalchemy import select as _sel

        from app.models import User
        from .inbound_fixtures import mk_token

        # alice 的个人令牌(属主本人可按它过滤;admin 不行)
        from app.core.db import SessionLocal

        async with SessionLocal() as s:
            alice_id = (await s.execute(_sel(User.id).where(
                User.username == "alice"))).scalar_one()
        tid, _plain = await mk_token(user_id=alice_id)
        h_admin = await role_headers(client, "ev_tsadm", role="super_admin")
        r = await client.get("/api/executions",
                             params={"tokenId": tid}, headers=h_admin)
        assert r.status_code == 404, r.text
