"""P1 证据落盘:每个 case 目录写 result.json(details)。"""
import json

from tests.helpers import make_draft, register_and_login, wait_until


async def test_row_writes_result_json_with_details(client, monkeypatch):
    from app.services import plate_client as pc, run_dispatcher
    from app.services.gimbal_launcher import LaunchResult
    from tests import _fake_engine as fe  # B6③:假引擎缝(legacy 链退役)

    headers = await register_and_login(client)
    await client.post("/api/scenarios", headers=headers,
                      json=make_draft("sc-evidence"))

    async def _fake_convert(scenario):
        return {"consumer": "platform", "converted": dict(scenario)}

    fake = LaunchResult(
        launch_status="ok", exit_code=1, total=2, passed=1, failed=1,
        skipped=0, error="",
        details=[{"step_id": "s1", "status": "failed", "error": "boom"}],
    )

    async def _launch(*a, **k):
        return fake

    monkeypatch.setattr(pc, "convert", _fake_convert)
    monkeypatch.setattr(fe, "launch", _launch)

    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-evidence", "dataSetIds": [],
    })
    assert r.status_code == 201, r.text
    run_id = r.json()["runId"]

    # P9:JSONL 写异步化(to_thread)后 fan-out 有真实挂起点,轮询等
    # result.json 落盘(同 test_run_baseline 的 wait_until 模式)。
    await wait_until(
        lambda: list(run_dispatcher._run_dir(run_id).rglob("result.json"))
    )
    result_files = list(run_dispatcher._run_dir(run_id).rglob("result.json"))
    assert len(result_files) == 1
    payload = json.loads(result_files[0].read_text(encoding="utf-8"))
    assert payload["status"] == "failed"          # exit 1 → failed 行
    assert payload["launchStatus"] == "ok"
    assert payload["details"] == [
        {"step_id": "s1", "status": "failed", "error": "boom"}
    ]
    assert "stdout" not in payload                # 有 details 不带 stdout 兜底


