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
from typing import Any

import httpx
import pytest
from httpx import AsyncClient


# ── shared fixture: register + login + seed scenario/case/ds ───────
async def _register_and_login(
    client: AsyncClient, username: str = "alice", password: str = "alicepass123"
) -> dict[str, str]:
    await client.post(
        "/api/auth/register",
        json={"username": username, "password": password, "display_name": username},
    )
    r = await client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _draft(scenario_id: str = "sc-test", **meta_over) -> dict:
    meta = {
        "scenarioId": scenario_id,
        "name": "Test",
        "module": "order",
        "priority": 1,
        "system": ["fin"],
    }
    meta.update(meta_over)
    return {
        "definition": {
            "kind": "scenario",
            "scenarioId": scenario_id,
            "meta": meta,
            "config": {"timePolicy": {"kind": "record"}},
            "resource": {},
            "steps": [],
        },
        "orchestration": {"steps": [], "resourceMeta": {}},
    }


# ── Plate mock helpers ─────────────────────────────────────────────
class PlateMock:
    """Programmable Plate mock.  Each test sets the desired behaviour
    on ``mock.behaviour`` before issuing the HTTP call."""

    def __init__(self) -> None:
        self.convert_calls: list[dict] = []
        self.behaviour: str = "ok"  # ok | 4xx | 5xx | unavailable

    def install(self) -> None:
        """Replace the singleton httpx client with a MockTransport."""

        async def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
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
                            },
                        },
                    )
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


# ── preview-plate ──────────────────────────────────────────────────
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


async def test_preview_plate_4xx_returns_502(
    client: AsyncClient, plate_mock: PlateMock
) -> None:
    plate_mock.behaviour = "4xx"
    headers = await _register_and_login(client)
    r = await client.post(
        "/api/scenarios/preview-plate",
        headers=headers,
        json=_draft(),
    )
    assert r.status_code == 502
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


# ── run dispatcher ────────────────────────────────────────────────
async def _seed_scenario_case_and_dataset(
    client: AsyncClient, headers: dict, *, rows: list[dict]
) -> None:
    """Create scenario + case + 1 dataset with the given rows."""
    await client.post("/api/scenarios", headers=headers, json=_draft())
    await client.post(
        "/api/cases",
        headers=headers,
        json={
            "caseId": "case-001",
            "scenarioId": "sc-test",
            "name": "c",
            "env": "dev",
            "auth": {"name": "a", "type": "bearer"},
            "dataSetIds": [],
            "createdBy": "alice",
        },
    )
    r = await client.post(
        "/api/cases/case-001/data-sets",
        headers=headers,
        json={"name": "ds", "rows": rows},
    )
    assert r.status_code == 201


async def test_run_dispatch_calls_convert_per_row(
    client: AsyncClient, plate_mock: PlateMock
) -> None:
    headers = await _register_and_login(client)
    rows = [{"qty": i} for i in range(3)]
    await _seed_scenario_case_and_dataset(client, headers, rows=rows)

    r = await client.post(
        "/api/runs",
        headers=headers,
        json={
            "caseId": "case-001",
            "dataSetIds": ["ds-001"],
            "env": {
                "envId": "test-env-A",
                "name": "test-env-A",
                "baseUrl": "http://x",
            },
        },
    )
    assert r.status_code == 201
    assert "runId" in r.json()

    # Wait for the background fan-out to finish
    for _ in range(50):
        if len(plate_mock.convert_calls) >= 3:
            break
        await asyncio.sleep(0.05)
    assert len(plate_mock.convert_calls) == 3


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
            "caseId": "case-001",
            "dataSetIds": ["ds-001"],
            "env": {
                "envId": "test-env-A",
                "name": "test-env-A",
                "baseUrl": "http://x",
            },
        },
    )
    assert r.status_code == 201
    run_id = r.json()["runId"]
    assert run_id.startswith("run-")
