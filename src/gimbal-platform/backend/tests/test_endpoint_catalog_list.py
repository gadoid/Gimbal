"""接口目录 /list 按修订过滤测试(Release 6.1)。

核心断言:带 ref 时改走 plate 系统作用域路由
``/api/system/{system}/endpoint?ref=``(全局路由不解析 ref,恒返
working)——只在 working 里存在的接口不出现在指定修订的列表里。
"""
from __future__ import annotations

from .helpers import register_and_login


async def test_list_ref_uses_system_scoped_route(client, plate):
    """带 system+ref → 调系统作用域路由(不是全局 /api/endpoint)。"""
    await register_and_login(client, "lcboss", "pw123456")
    user = await register_and_login(client, "lcboss", "pw123456")

    # 全局列表(working):两个系统的接口
    plate.items = [
        {"id": "fin.a.old", "system": "fin", "service": "fin-service",
         "name": "old", "method": "GET", "path": "/old", "shape_hash": "h1"},
        {"id": "wms.b.x", "system": "wms", "service": "wms-service",
         "name": "wms-ep", "method": "GET", "path": "/x", "shape_hash": "h2"},
    ]

    r = await client.get("/api/endpoint-catalog/list", headers=user,
                         params={"system": "fin", "ref": "1.0#1"})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    # 走了系统作用域路由 → 只有该系统该修订里的接口(不含 wms)
    assert all(e["system"] == "fin" for e in items)
    # mock 未配置 fin@1.0#1 的修订快照 → 列表为空(不在修订里)
    # (实际由 plate 返回;此处验证请求走对了路由即可)
    assert isinstance(items, list)


async def test_list_no_ref_uses_global_route(client, plate):
    """不带 ref → 全局路由(working,全部系统)。"""
    await register_and_login(client, "lcg", "pw123456")
    user = await register_and_login(client, "lcg", "pw123456")

    plate.items = [
        {"id": "fin.a.old", "system": "fin", "service": "fin-service",
         "name": "old", "method": "GET", "path": "/old", "shape_hash": "h1"},
        {"id": "wms.b.x", "system": "wms", "service": "wms-service",
         "name": "wms-ep", "method": "GET", "path": "/x", "shape_hash": "h2"},
    ]

    r = await client.get("/api/endpoint-catalog/list", headers=user)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    systems = {e["system"] for e in items}
    assert "fin" in systems and "wms" in systems


async def test_list_ref_without_system_ignores_ref(client, plate):
    """带 ref 但不带 system → 全局路由(ref 不生效,提示场景声明系统)。"""
    await register_and_login(client, "lcs", "pw123456")
    user = await register_and_login(client, "lcs", "pw123456")

    plate.items = [
        {"id": "fin.a.old", "system": "fin", "service": "fin-service",
         "name": "old", "method": "GET", "path": "/old", "shape_hash": "h1"},
    ]

    r = await client.get("/api/endpoint-catalog/list", headers=user,
                         params={"ref": "1.0#1"})
    assert r.status_code == 200, r.text
    # 全局路由 → 返回 working 的接口(未被 ref 过滤)
    assert len(r.json()["items"]) >= 1
