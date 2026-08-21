"""D12 基线执行:dataSetIds=[] → 一个隐式空覆盖行,纯基线跑一次。"""
from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import (
    gimbal_ok as _ok,
    make_draft,
    register_and_login,
    test_env,
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

    calls: list[dict] = []

    async def _capture(scenario, *, halt_at=None):
        calls.append(dict(scenario))
        return _ok()

    async def _fake_convert(scenario):
        return {"consumer": "platform", "converted": dict(scenario)}

    from app.services import gimbal_client as gc, plate_client as pc
    monkeypatch.setattr(gc, "run", _capture)
    monkeypatch.setattr(pc, "convert", _fake_convert)

    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-base", "dataSetIds": [], "env": test_env(),
    })
    assert r.status_code == 201, r.text

    # wait_until 既有模式(test_run_m1_capabilities):同步谓词轮询。
    # (brief 草稿的 ``lambda: False or _exec_done(s)`` 返回协程对象恒真,
    # 从不真正等待 — 按 brief 注记改用既有同步谓词写法。)
    await wait_until(lambda: len(calls) >= 1)
    assert len(calls) == 1                      # 一个隐式空行 × nRuns=1
    assert calls[0]["config"]["vars"]["customer_id"] == "261"  # 基线 vars 生效

    import sqlalchemy as sa

    from app.core import db as db_module
    from app.models.execution import Execution

    async with db_module.SessionLocal() as s:
        row = (
            await s.execute(
                sa.select(Execution).order_by(Execution.id.desc()).limit(1)
            )
        ).scalar_one_or_none()
        assert row is not None
        assert row.total_runs == 1  # 空数据集回退行(1 行)× nRuns=1
