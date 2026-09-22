"""场景库「筛选分组」(GET/POST/DELETE /api/scenario-filter-groups)回归。

覆盖:存/读回(createdAt 序列化口径)、同名覆盖、分桶与归属隔离、
条数上限、入参校验、未登录。
"""
from __future__ import annotations

from datetime import datetime

from httpx import AsyncClient

from tests.helpers import register_and_login

_F = {"modules": ["支付"], "tags": [], "authors": [], "priorities": [],
      "systems": ["fin"], "updatedWithin": "7d"}


async def _mk(client: AsyncClient, name: str) -> dict:
    return await register_and_login(client, name, f"{name}-pass-123")


async def _save(client: AsyncClient, hdr: dict, name: str, q: str = "",
                bucket: str = "mine", filters: dict | None = None):
    return await client.post("/api/scenario-filter-groups", headers=hdr, json={
        "bucket": bucket, "name": name, "q": q,
        "filters": filters if filters is not None else _F,
    })


async def _list(client: AsyncClient, hdr: dict, bucket: str = "mine"):
    r = await client.get(
        "/api/scenario-filter-groups", headers=hdr, params={"bucket": bucket})
    assert r.status_code == 200
    return r.json()["items"]


async def test_save_then_list_roundtrip_with_camel_case_aware_ts(
    client: AsyncClient,
):
    hdr = await _mk(client, "fg_owner")
    r = await _save(client, hdr, "大促回归", q="订单")
    assert r.status_code == 200
    created = r.json()
    assert created["name"] == "大促回归" and created["q"] == "订单"
    assert created["filters"] == _F
    # 序列化口径 = createdAt(前端契约),且带 offset —— naive 串会被
    # new Date() 按本地时区读,正是审计时间列那个 +8 bug 的形状。
    assert "created_at" not in created
    assert datetime.fromisoformat(created["createdAt"]).utcoffset() is not None

    items = await _list(client, hdr)
    assert [i["name"] for i in items] == ["大促回归"]
    assert items[0]["id"] == created["id"]


async def test_same_name_overwrites_in_place(client: AsyncClient):
    hdr = await _mk(client, "fg_overwrite")
    first = (await _save(client, hdr, "回归", q="a")).json()
    second = (await _save(client, hdr, "回归", q="b")).json()
    assert second["id"] == first["id"]  # 沿用原 id:高亮跟着新条件走
    items = await _list(client, hdr)
    assert len(items) == 1 and items[0]["q"] == "b"


async def test_buckets_are_isolated(client: AsyncClient):
    hdr = await _mk(client, "fg_bucket")
    await _save(client, hdr, "只在我的", bucket="mine")
    assert [i["name"] for i in await _list(client, hdr, "mine")] == ["只在我的"]
    assert await _list(client, hdr, "public") == []


async def test_groups_do_not_leak_across_users(client: AsyncClient):
    owner = await _mk(client, "fg_a")
    other = await _mk(client, "fg_b")
    gid = (await _save(client, owner, "私有条件")).json()["id"]

    assert await _list(client, other) == []
    # 拿别人的 id 也删不动:对 other 而言该 id 不存在
    r = await client.delete(
        f"/api/scenario-filter-groups/mine/{gid}", headers=other)
    assert r.status_code == 404
    assert len(await _list(client, owner)) == 1


async def test_delete_removes_only_the_named_one(client: AsyncClient):
    hdr = await _mk(client, "fg_del")
    keep = (await _save(client, hdr, "留下")).json()["id"]
    gone = (await _save(client, hdr, "删掉")).json()["id"]
    r = await client.delete(
        f"/api/scenario-filter-groups/mine/{gone}", headers=hdr)
    assert r.status_code == 200
    assert [i["id"] for i in await _list(client, hdr)] == [keep]


async def test_group_cap_rejects_the_31st(client: AsyncClient):
    hdr = await _mk(client, "fg_cap")
    for i in range(30):
        assert (await _save(client, hdr, f"g{i}")).status_code == 200
    r = await _save(client, hdr, "溢出")
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "group_limit"
    # 同名覆盖不受上限影响(改条件重存是常态,不该被自己的上限挡住)
    assert (await _save(client, hdr, "g0", q="改过的条件")).status_code == 200


async def test_blank_name_and_unknown_bucket_rejected(client: AsyncClient):
    hdr = await _mk(client, "fg_bad_input")
    assert (await _save(client, hdr, "   ")).status_code == 422
    assert (await _save(client, hdr, "名字", bucket="drafts")).status_code == 422
    r = await client.get(
        "/api/scenario-filter-groups", headers=hdr, params={"bucket": "drafts"})
    assert r.status_code == 422


async def test_requires_auth(client: AsyncClient):
    r = await client.get("/api/scenario-filter-groups")
    assert r.status_code in (401, 403)
