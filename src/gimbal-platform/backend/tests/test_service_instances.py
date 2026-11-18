"""实例改标签 / 移除实例(2026-11-18 环境降级交互补齐)。

实例 = (system, env) 的部署事实(登录口/版本线/说明)。环境降级为轻量
标签后,允许把实例行搬到另一环境;API 地址(deployments)与身份条目
按各自环境独立维护,不随搬移。
"""
from __future__ import annotations

from .helpers import register_and_login


async def _env(client, headers, name: str) -> int:
    r = await client.post("/api/environments", headers=headers,
                          json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_instance_move_and_delete(client, fresh_db):
    await register_and_login(client, "instboss", "pw123456")
    admin = await register_and_login(client, "instboss", "pw123456")
    env1 = await _env(client, admin, "SIT")
    env2 = await _env(client, admin, "UAT")

    # 登记实例(env1)
    r = await client.put(f"/api/services/instances/fin/{env1}",
                         headers=admin, json={
                             "loginUrl": "https://sit.fin.local/auth",
                             "line": "1.0", "note": "联调"})
    assert r.status_code == 201, r.text
    assert r.json()["envId"] == env1

    # 改标签 env1 → env2:登录口/版本线/说明随行
    r = await client.patch(f"/api/services/instances/fin/{env1}",
                           headers=admin, json={"envId": env2})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["envId"] == env2 and body["envName"] == "UAT"
    assert body["loginUrl"] == "https://sit.fin.local/auth"
    assert body["line"] == "1.0" and body["note"] == "联调"

    # 源行已不存在(搬移而非复制)→ 再搬 404
    r = await client.patch(f"/api/services/instances/fin/{env1}",
                           headers=admin, json={"envId": env2})
    assert r.status_code == 404

    # 目标环境已有该系统实例 → 409 instance_target_exists
    r = await client.put(f"/api/services/instances/fin/{env1}",
                         headers=admin, json={"loginUrl": "https://sit2/auth"})
    assert r.status_code == 201, r.text
    r = await client.patch(f"/api/services/instances/fin/{env1}",
                           headers=admin, json={"envId": env2})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "instance_target_exists"

    # 目标环境不存在 → 404
    r = await client.patch(f"/api/services/instances/fin/{env1}",
                           headers=admin, json={"envId": 99999})
    assert r.status_code == 404

    # 清理为 409 场景补建的 env1 行(搬移/复制语义区分)
    r = await client.delete(f"/api/services/instances/fin/{env1}",
                            headers=admin)
    assert r.status_code == 204

    # 生效面:列表只剩 env2 一行
    r = await client.get("/api/services/instances", headers=admin)
    assert [i["envId"] for i in r.json()] == [env2]

    # 移除实例:只删实例行
    r = await client.delete(f"/api/services/instances/fin/{env2}",
                            headers=admin)
    assert r.status_code == 204
    r = await client.get("/api/services/instances", headers=admin)
    assert r.json() == []
    # 幂等失败面:再删 404
    r = await client.delete(f"/api/services/instances/fin/{env2}",
                            headers=admin)
    assert r.status_code == 404


async def test_instance_move_requires_ops_write(client, fresh_db):
    """写门与实例 upsert 同门(ops.write):普通用户 403。"""
    await register_and_login(client, "instroot", "pw123456")
    admin = await register_and_login(client, "instroot", "pw123456")
    env1 = await _env(client, admin, "SIT")
    env2 = await _env(client, admin, "UAT")
    r = await client.put(f"/api/services/instances/fin/{env1}",
                         headers=admin, json={"loginUrl": "https://x/auth"})
    assert r.status_code == 201, r.text

    member = await register_and_login(client, "instuser", "pw123456")
    r = await client.patch(f"/api/services/instances/fin/{env1}",
                           headers=member, json={"envId": env2})
    assert r.status_code == 403
    r = await client.delete(f"/api/services/instances/fin/{env1}",
                            headers=member)
    assert r.status_code == 403


async def test_instance_move_by_free_tag(client, fresh_db):
    """改标签支持自由标签:目标标签不存在 → 自动登记为环境定义。"""
    await register_and_login(client, "tagboss", "pw123456")
    admin = await register_and_login(client, "tagboss", "pw123456")
    env1 = await _env(client, admin, "SIT")
    r = await client.put(f"/api/services/instances/fin/{env1}",
                         headers=admin,
                         json={"loginUrl": "https://x/auth", "line": "1.0"})
    assert r.status_code == 201, r.text

    r = await client.patch(f"/api/services/instances/fin/{env1}",
                           headers=admin, json={"envTag": "灰度"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["envName"] == "灰度" and body["envId"] != env1
    assert body["loginUrl"] == "https://x/auth"

    # 标签已登记进环境字典(可用于筛选/账户/部署)
    r = await client.get("/api/environments", headers=admin)
    names = [e["name"] for e in r.json()]
    assert "灰度" in names

    # envId / envTag 二选一:都缺或都给 → 422
    r = await client.patch(f"/api/services/instances/fin/{body['envId']}",
                           headers=admin, json={})
    assert r.status_code == 422
    r = await client.patch(f"/api/services/instances/fin/{body['envId']}",
                           headers=admin, json={"envId": env1, "envTag": "x"})
    assert r.status_code == 422


async def test_instance_multi_tags_share_config(client, fresh_db):
    """一实例多标签(2026-11-18):组的标签集一次提交;组内配置共享。"""
    await register_and_login(client, "multitag", "pw123456")
    admin = await register_and_login(client, "multitag", "pw123456")
    env1 = await _env(client, admin, "SIT")
    r = await client.put(f"/api/services/instances/fin/{env1}",
                         headers=admin,
                         json={"loginUrl": "https://x/auth", "line": "1.0",
                               "note": "联调"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["tags"] == ["SIT"] and body["groupId"]

    # 加两枚标签 → 组内三行,标签集回带
    r = await client.put(f"/api/services/instances/fin/{env1}/tags",
                         headers=admin,
                         json={"tags": ["SIT", "联调", "回归"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tags"] == ["SIT", "回归", "联调"]
    assert body["loginUrl"] == "https://x/auth"  # 新行复制配置

    # 组内配置同步:改 line → 全部标签行一致
    r = await client.put(f"/api/services/instances/fin/{env1}",
                         headers=admin, json={"line": "2.0"})
    assert r.status_code == 201, r.text
    r = await client.get("/api/services/instances", headers=admin)
    rows = {i["envName"]: i for i in r.json()}
    assert set(rows) == {"SIT", "联调", "回归"}
    assert {i["line"] for i in rows.values()} == {"2.0"}
    assert {i["groupId"] for i in rows.values()}.__len__() == 1

    # 缩标签:移除「回归」→ 组内两行,删一行
    r = await client.put(f"/api/services/instances/fin/{env1}/tags",
                         headers=admin, json={"tags": ["SIT", "联调"]})
    assert r.status_code == 200, r.text
    assert r.json()["tags"] == ["SIT", "联调"]
    r = await client.get("/api/services/instances", headers=admin)
    assert {i["envName"] for i in r.json()} == {"SIT", "联调"}

    # 至少保留一枚标签
    r = await client.put(f"/api/services/instances/fin/{env1}/tags",
                         headers=admin, json={"tags": ["   "]})
    assert r.status_code == 422

    # 别的实例组占用了目标标签 → 409
    env3 = await _env(client, admin, "PROD")
    r = await client.put(f"/api/services/instances/fin/{env3}",
                         headers=admin, json={"loginUrl": "https://prod/auth"})
    assert r.status_code == 201, r.text
    r = await client.put(f"/api/services/instances/fin/{env1}/tags",
                         headers=admin, json={"tags": ["SIT", "PROD"]})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "instance_tag_conflict"

    # 移除实例 = 删整个组(SIT+联调),PROD 组不受影响
    r = await client.delete(f"/api/services/instances/fin/{env1}",
                            headers=admin)
    assert r.status_code == 204
    r = await client.get("/api/services/instances", headers=admin)
    assert [i["envName"] for i in r.json()] == ["PROD"]
