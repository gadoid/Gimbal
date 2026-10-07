"""C2 sync 动作（S1-0 B4，2026-10-07 已停用）。

原为 501 占位 stub；停用后返回 410 + 明确「已停用」说明
（与 P1「文件为唯一真源」冲突，见 claude/plate-design.md 附录 C X4）。
C1 register 的停用测试见 ``test_declared_systems.py::TestC1RegisterAction``。
"""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_sync_system_returns_410_disabled(http_client: TestClient) -> None:
    resp = http_client.post("/api/systems/fin/system/action/sync")
    assert resp.status_code == 410
    err = resp.json()["error"]
    assert err["code"] == "admin_not_implemented"
    assert "disabled" in err["message"]
