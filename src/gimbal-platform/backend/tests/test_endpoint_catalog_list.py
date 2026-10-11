"""接口目录 /list 按修订过滤测试(Release 6.1)。

核心断言:
  * 带 system+ref → 走已有 /api/systems/{system}/endpoint(支持 ref),
    结果 ≠ working(只含该修订的接口);
  * 修订不存在 → plate 404 原样透传(不吞成空列表);
  * 不带 ref → 全局 working。
"""
from __future__ import annotations

from .helpers import register_and_login


def _ep(eid: str, system: str, name: str = "") -> dict:
    return {"id": eid, "system": system,
            "service": f"{system}-service", "name": name or eid,
            "method": "GET", "path": f"/{eid}", "shape_hash": f"h-{eid}"}


async def test_list_ref_returns_scoped_subset(client, plate):
    """带 system+ref → 只返回该系统该修订的接口(≠ working 全量)。"""
    await register_and_login(client, "lcboss", "pw123456")
    user = await register_and_login(client, "lcboss", "pw123456")

    # working:两个系统的接口
    plate.items = [_ep("fin.a.old", "fin"), _ep("wms.b.x", "wms")]
    # fin@1.0#1 的修订快照只有一个接口(不含 fin.a.old)
    plate.system_scoped = {("fin", "1.0#1"): [_ep("fin.a.new", "fin")]}

    r = await client.get("/api/endpoint-catalog/list", headers=user,
                         params={"system": "fin", "ref": "1.0#1"})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    ids = [e["id"] for e in items]
    assert "fin.a.new" in ids          # 修订里的接口在列表中
    assert "fin.a.old" not in ids      # working-only 接口被过滤
    assert "wms.b.x" not in ids        # 其他系统不在 fin 的结果里


async def test_list_revision_not_found_passes_through_404(client, plate):
    """修订不存在 → plate 404 透传(不吞成空列表)。"""
    await register_and_login(client, "lcboss2", "pw123456")
    user = await register_and_login(client, "lcboss2", "pw123456")
    plate.items = [_ep("fin.a.old", "fin")]
    # 不配置 fin@9.9#9 的快照 → plate 返回 404

    r = await client.get("/api/endpoint-catalog/list", headers=user,
                         params={"system": "fin", "ref": "9.9#9"})
    assert r.status_code == 404, r.text
    assert "release_not_found" in r.text or "not_found" in r.text


async def test_list_no_ref_returns_working(client, plate):
    """不带 ref → 全局路由(working,全部系统)。"""
    await register_and_login(client, "lcg", "pw123456")
    user = await register_and_login(client, "lcg", "pw123456")
    plate.items = [_ep("fin.a.old", "fin"), _ep("wms.b.x", "wms")]

    r = await client.get("/api/endpoint-catalog/list", headers=user)
    assert r.status_code == 200, r.text
    systems = {e["system"] for e in r.json()["items"]}
    assert "fin" in systems and "wms" in systems
