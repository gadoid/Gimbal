"""B2-②:working 快照显式重载(POST /api/admin/reload)。

语义(plate-design §S1.5「原子重载」收尾):
* admin token 门(fail-closed):``PLATE_ADMIN_TOKEN`` 未配置 → 403
  reload_disabled(端点不可用);配置后要求 ``X-Admin-Token`` 常量时
  匹配,不匹配 → 403;
* owned 模式 reload = 新 registry 独立构建,**构建成功才换入**;
* 构建失败 → 503 reload_failed,旧快照原样继续服务(换入前抛出);
* 嵌入模式(create_app(registry=...))→ 409 invalid_action(caller
  控制自身 registry 状态);
* 快照标识(G5)带 HEAD 短 sha:working@<sha7>,非仓回退裸 working。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from gimbal_plate.http import app as app_module
from gimbal_plate.http.app import create_app
from gimbal_plate.registry import PlateRegistry

_TOKEN = "test-admin-token"
_AUTH = {"X-Admin-Token": _TOKEN}


@pytest.fixture()
def owned_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("PLATE_ADMIN_TOKEN", _TOKEN)
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as c:
        c.app.state.snapshot_generation = 0  # 显式从 0 起计代际
        yield c


def test_reload_disabled_without_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fail-closed:未配置 PLATE_ADMIN_TOKEN → 端点整体不可用。"""
    monkeypatch.delenv("PLATE_ADMIN_TOKEN", raising=False)
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.post("/api/admin/reload", headers=_AUTH)
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "reload_disabled"
        assert "PLATE_ADMIN_TOKEN" in resp.json()["error"]["message"]


def test_reload_wrong_token_rejected(
    owned_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PLATE_ADMIN_TOKEN", "另一个")
    resp = owned_client.post("/api/admin/reload", headers=_AUTH)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "reload_disabled"
    resp = owned_client.post("/api/admin/reload")  # 缺头
    assert resp.status_code == 403


def test_reload_ok_and_generation_bumps(owned_client: TestClient) -> None:
    resp = owned_client.post("/api/admin/reload", headers=_AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["generation"] == 1
    assert data["systems"]  # 缺省 systems 树非空
    assert data["endpoints"] > 0
    # 快照标识:working 或 working@<sha7>(测试 checkout 无 .git 时回退)
    assert data["snapshot"] == "working" or data["snapshot"].startswith(
        "working@")
    # 换入后读面照常(新 registry 即时生效)
    assert owned_client.get("/healthz").json()["status"] == "ok"


def test_reload_failure_keeps_old_snapshot(
    owned_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    old_registry = owned_client.app.state.registry
    old_label = owned_client.app.state.snapshot_label

    def _boom(app) -> None:
        raise RuntimeError("fenced 块损坏(注入)")

    monkeypatch.setattr(app_module, "_reload_working", _boom)
    resp = owned_client.post("/api/admin/reload", headers=_AUTH)
    assert resp.status_code == 503
    err = resp.json()["error"]
    assert err["code"] == "reload_failed"
    assert "旧快照继续服务" in err["message"]
    # 旧 registry 原样(身份不变),读面照常服务
    assert owned_client.app.state.registry is old_registry
    assert owned_client.app.state.snapshot_label == old_label
    assert owned_client.get("/healthz").json()["status"] == "ok"


def test_reload_embedded_mode_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLATE_ADMIN_TOKEN", _TOKEN)
    app = create_app(registry=PlateRegistry())
    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.post("/api/admin/reload", headers=_AUTH)
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "invalid_action"


def test_snapshot_label_carries_commit_when_repo_present(
    owned_client: TestClient,
) -> None:
    # 真仓检出时 healthz git_head 有值 ⇒ 快照标识应带同一短 sha;
    # 无 .git 的环境(打包/子集 checkout)两处一致回退。
    head = owned_client.get("/healthz").json().get("git_head")
    label = owned_client.app.state.snapshot_label
    if head:
        assert label == f"working@{head[:7]}"
    else:
        assert label == "working"
