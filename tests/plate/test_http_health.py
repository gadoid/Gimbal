"""Health check test for the plate HTTP service."""

from __future__ import annotations

from fastapi.testclient import TestClient

from gimbal_plate.http import create_app


def test_healthz_returns_ok() -> None:
    """b1-9(归一 v1.0 §1.5/D-L):/healthz 附加 git_head(失败/无 git 返 null)
    与 integration_definitions(embedded 模式 lifespan 不计算 → 不出现该键;
    owned 模式恒出现,可能为空 dict)。"""
    app = create_app(registry=__import__("gimbal_plate.registry", fromlist=["PlateRegistry"]).PlateRegistry())
    with TestClient(app) as client:
        resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["git_head"] is None or isinstance(body["git_head"], str)
    assert "m2_pool" not in body  # embedded:未走 owned lifespan
