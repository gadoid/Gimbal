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
    def test_register_creates_declared_system(self, http_client: TestClient) -> None:
        resp = http_client.post(
            "/api/system/action/register",
            json={"id": "logi", "name": "物流", "description": "物流系统"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        # 注册后系统列表可见(0 endpoint,纯声明)
        listing = http_client.get("/api/system").json()["data"]["items"]
        ids = [s["id"] for s in listing]
        assert "logi" in ids
        logi = next(s for s in listing if s["id"] == "logi")
        assert logi["endpoint_count"] == 0

    def test_register_is_idempotent(self, http_client: TestClient) -> None:
        payload = {"id": "logi"}
        r1 = http_client.post("/api/system/action/register", json=payload)
        r2 = http_client.post("/api/system/action/register", json=payload)
        assert r1.status_code == 200 and r2.status_code == 200
        ids = [s["id"] for s in http_client.get("/api/system").json()["data"]["items"]]
        assert ids.count("logi") == 1

    def test_register_missing_id_returns_400(self, http_client: TestClient) -> None:
        resp = http_client.post("/api/system/action/register", json={"name": "x"})
        assert resp.status_code == 400


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
