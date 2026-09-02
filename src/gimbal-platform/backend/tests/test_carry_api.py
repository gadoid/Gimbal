"""carry API 面(spec §3.2)— 读写权限分治 + 字段面聚合。"""
from __future__ import annotations

from .test_scenario_visibility_and_copy import _member


async def _admin(client):
    from .helpers import register_and_login
    # 用户名策略 ^[A-Za-z0-9_]+$ 不含连字符 → 用下划线(brief 的
    # "carry-admin" 会被 register 422 拒掉,登录拿不到 token)。
    return await register_and_login(client, "carry_admin", "pw123456")


async def test_defaults_roundtrip_and_null_row(client):
    admin = await _admin(client)
    r = await client.put("/api/carry/defaults", headers=admin,
                         json={"defaults": {"$.appCode": "TRACE-V2",
                                            "$.remark": None}})
    assert r.status_code == 200, r.text
    r = await client.get("/api/carry/defaults", headers=admin)
    assert r.json()["defaults"] == {"$.appCode": "TRACE-V2", "$.remark": None}


async def test_bindings_put_get_per_service(client):
    admin = await _admin(client)
    r = await client.put("/api/carry/bindings/fin-service", headers=admin,
                         json={"bindings": {"$.remark": "压测-张三"}})
    assert r.status_code == 200, r.text
    r = await client.get("/api/carry/bindings/fin-service", headers=admin)
    assert r.json()["bindings"] == {"$.remark": "压测-张三"}
    r = await client.get("/api/carry/bindings", headers=admin)
    assert r.json()["bindings"] == {"fin-service": {"$.remark": "压测-张三"}}


async def test_write_requires_admin(client):
    member = await _member(client, "carry_mem")
    r = await client.put("/api/carry/defaults", headers=member,
                         json={"defaults": {}})
    assert r.status_code == 403


async def test_service_fields_aggregates_carry_face(client, plate):
    """该服务全部接口的 carry 面并集(plate /full 聚合)。

    P1 起读 request.declarations 的 carry 通道条目(spec §7 P1.3);
    binding 条目被过滤(消费面只取 carry 通道)。"""
    plate.items = [{"id": "fin.ep1", "version": "1.0.0", "updated_at": None,
                    "service": "fin-service"}]
    plate.fulls = {"fin.ep1": {"request": {"declarations": [
        {"path": "$.order_id", "channel": "binding", "type": None,
         "description": "业务订单号"},
        {"path": "$.remark", "channel": "carry", "type": "string",
         "description": "备注"},
    ]}}}
    admin = await _admin(client)
    r = await client.get("/api/carry/bindings/fin-service/fields",
                         headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["fields"] == [
        {"path": "$.remark", "type": "string", "description": "备注"}]
    assert r.json()["degraded"] is False


async def test_service_fields_degraded_when_single_full_fails(client, plate):
    """单端点 /full 失败(抛错或 404→None)→ degraded=True:面不完整,
    配置页整表替换保存会删不可见端点的绑定值,前端据此禁存。"""
    plate.items = [
        {"id": "fin.ep1", "version": "1.0.0", "updated_at": None,
         "service": "fin-service"},
        {"id": "fin.ep2", "version": "1.0.0", "updated_at": None,
         "service": "fin-service"},
        {"id": "fin.ep3", "version": "1.0.0", "updated_at": None,
         "service": "fin-service"},
    ]
    plate.fulls = {"fin.ep1": {"request": {"declarations": [
        {"path": "$.remark", "channel": "carry", "type": "string",
         "description": "备注"},
    ]}}}
    # ep2:/full 抛 ConnectError → PlateUnavailableError;
    # ep3:列表有但 fulls 缺席 → 404 → None(端点已下架)。
    plate.full_down = {"fin.ep2"}
    admin = await _admin(client)
    r = await client.get("/api/carry/bindings/fin-service/fields",
                         headers=admin)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["degraded"] is True
    # 可达端点的面照常聚合(部分结果,不是全空)
    assert body["fields"] == [
        {"path": "$.remark", "type": "string", "description": "备注"}]


async def test_service_fields_tolerates_missing_declarations(client, plate):
    """⑨ 缺键容忍:无声明端点(request 缺席、响应 schema-only →
    无 declarations 键)聚合不报错、不产空占位条目。"""
    plate.items = [
        {"id": "fin.ep1", "version": "1.0.0", "updated_at": None,
         "service": "fin-service"},
        {"id": "fin.account", "version": "1.0.0", "updated_at": None,
         "service": "fin-service"},
    ]
    plate.fulls = {
        "fin.ep1": {"request": {"declarations": [
            {"path": "$.remark", "channel": "carry", "type": "string",
             "description": "备注"},
        ]}},
        # account 形态:request 整体缺席(零声明端点)
        "fin.account": {"responses": {"200": {"status": 200}}},
    }
    admin = await _admin(client)
    r = await client.get("/api/carry/bindings/fin-service/fields",
                         headers=admin)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["degraded"] is False
    assert body["fields"] == [
        {"path": "$.remark", "type": "string", "description": "备注"}]


async def test_service_fields_502_when_plate_list_down(client, plate):
    """plate 列表级故障 → 502(_error_mapping._plate_502 同款信封);
    循环内单端点 /full 失败的降级跳过由聚合测试覆盖,此处只提升列表级。"""
    plate.down = True
    admin = await _admin(client)
    r = await client.get("/api/carry/bindings/fin-service/fields",
                         headers=admin)
    assert r.status_code == 502, r.text
    assert r.json()["detail"]["code"] == "plate_unavailable"


async def test_put_defaults_missing_body_is_422(client):
    """缺 body → FastAPI 422(而非 body=None → AttributeError 500)。"""
    admin = await _admin(client)
    r = await client.put("/api/carry/defaults", headers=admin)
    assert r.status_code == 422, r.text


async def test_put_bindings_missing_body_is_422(client):
    admin = await _admin(client)
    r = await client.put("/api/carry/bindings/fin-service", headers=admin)
    assert r.status_code == 422, r.text


async def test_bindings_isolated_across_services(client):
    """跨服务隔离(Task 5 评审裁定):写 B 不得扰动 A 的行。"""
    admin = await _admin(client)
    r = await client.put("/api/carry/bindings/svc-a", headers=admin,
                         json={"bindings": {"$.a1": "A1", "$.shared": "from-a"}})
    assert r.status_code == 200, r.text
    r = await client.put("/api/carry/bindings/svc-b", headers=admin,
                         json={"bindings": {"$.b1": "B1"}})
    assert r.status_code == 200, r.text

    r = await client.get("/api/carry/bindings/svc-a", headers=admin)
    assert r.json()["bindings"] == {"$.a1": "A1", "$.shared": "from-a"}
    r = await client.get("/api/carry/bindings", headers=admin)
    assert r.json()["bindings"] == {
        "svc-a": {"$.a1": "A1", "$.shared": "from-a"},
        "svc-b": {"$.b1": "B1"},
    }
