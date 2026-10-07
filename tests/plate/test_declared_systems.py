"""声明式系统 (declared systems) + C1 注册落地 + common 通用层。

背景:plate 的"系统"原本完全由 endpoint 派生(SystemIndex 遍历
ep.system),没有 endpoint 的系统无法存在。本组测试锁定三层能力:

1. registry 内核 ``declare_system``:声明一个不依赖 endpoint 的系统,
   ``has_system`` / ``list_systems`` 合并 "endpoint 派生 ∪ 声明式"。
2. C1 落地:``POST /api/system/action/register`` 从 501 stub 变为
   真实注册(幂等,缺 id 400)。
3. common 通用层:启动内置声明 + ``common.default`` config/meta seed,
   作为编排页"选系统 → 场景骨架预填"的默认源(meta 用通用定义,
   不放业务系统下)。
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from gimbal_plate.registry import PlateRegistry


class TestDeclareSystemKernel:
    def test_declared_system_visible_without_endpoints(self) -> None:
        reg = PlateRegistry()
        assert not reg.has_system("logi")
        reg.declare_system("logi", name="物流", description="物流系统")
        assert reg.has_system("logi")
        assert "logi" in reg.list_systems()

    def test_declare_system_idempotent(self) -> None:
        reg = PlateRegistry()
        reg.declare_system("logi", description="第一次")
        reg.declare_system("logi", description="第二次")  # 幂等,不抛异常
        assert reg.list_systems().count("logi") == 1

    def test_reset_clears_declared_systems(self) -> None:
        reg = PlateRegistry()
        reg.declare_system("logi")
        reg.reset()
        assert not reg.has_system("logi")


class TestC1RegisterAction:
    """S1-0 B4（2026-10-07）：C1 内存注册已停用（410，与 P1「文件为唯一真源」冲突，
    见 claude/plate-design.md 附录 C X4）。平台侧无调用（已核实）。"""

    def test_register_returns_410_disabled(self, http_client: TestClient) -> None:
        resp = http_client.post(
            "/api/system/action/register",
            json={"id": "logi", "name": "物流", "description": "物流系统"},
        )
        assert resp.status_code == 410
        body = resp.json()
        assert body["ok"] is False
        assert "disabled" in body["error"]["message"]
        # 未注册：系统列表不出现
        ids = [s["id"] for s in http_client.get("/api/system").json()["data"]["items"]]
        assert "logi" not in ids

    def test_register_disabled_regardless_of_body(self, http_client: TestClient) -> None:
        resp = http_client.post("/api/system/action/register", json={"name": "x"})
        assert resp.status_code == 410


class TestCommonBuiltinLayer:
    def test_common_system_listed_alongside_fin(self, http_client: TestClient) -> None:
        ids = [s["id"] for s in http_client.get("/api/system").json()["data"]["items"]]
        assert "fin" in ids and "common" in ids

    def test_common_config_seed_queryable(self, http_client: TestClient) -> None:
        body = http_client.get("/api/systems/common/config").json()
        assert body["ok"] is True
        items = body["data"]["items"]
        assert len(items) == 1
        # common 通用配置 = 最低公共默认(record 计时,空 services)
        assert items[0]["time_policy"]["kind"] == "record"
        assert items[0]["services"] == {}

    def test_common_meta_seed_queryable(self, http_client: TestClient) -> None:
        body = http_client.get("/api/systems/common/meta").json()
        assert body["ok"] is True
        items = body["data"]["items"]
        assert len(items) == 1
        assert items[0]["version"] == "1.0.0"
        assert items[0]["expire"] is False
