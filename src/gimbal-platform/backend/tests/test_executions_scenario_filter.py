"""list executions 的 scenario_id 过滤(「上次运行」数据源,spec §3.1)。"""
from __future__ import annotations

from .helpers import make_draft as _draft, wait_until as _wait
from .test_run_m1_capabilities import _patch_launch_capture, _run_payload
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401
from .test_scenario_visibility_and_copy import _member


async def test_list_filters_by_scenario(client, plate_mock: PlateMock, monkeypatch):
    bob = await _member(client, "bob")
    for sid in ("sc-a", "sc-b"):
        r = await client.post("/api/scenarios", headers=bob,
                              json=_draft(scenario_id=sid))
        assert r.status_code in (200, 201), r.text
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    for sid in ("sc-a", "sc-b"):
        r = await client.post("/api/runs", headers=bob,
                              json=_run_payload(scenarioId=sid, dataSetIds=[]))
        assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 2)

    resp = await client.get("/api/executions", headers=bob,
                            params={"scenario_id": "sc-a"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["scenario_id"] == "sc-a"
