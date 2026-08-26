"""Constants-pool API 面单测 —— per-user 常量条目 CRUD。

设计: src/gimbal-platform/docs/superpowers/specs/2026-08-26-constant-pool-design.md §后端
覆盖: owner 隔离(B1/B2)、互斥校验(B3/B4)、name 规则(B5)、
409 字典 detail(B6)、PATCH 不可变 entry_kind/按行校验(B7)、
删除(B8)、字面量四类型往返(B9)。
"""
from __future__ import annotations

from httpx import AsyncClient
from tests.helpers import register_and_login


async def _auth(client: AsyncClient, username: str = "alice") -> dict[str, str]:
    return await register_and_login(client, username, "secret-123")


async def test_b1_create_and_list_owned_entries(client: AsyncClient) -> None:
    headers = await _auth(client)
    lit = {
        "name": "bank_id",
        "description": "联行号",
        "entry_kind": "literal",
        "value": "319666690256273408",
    }
    gen = {
        "name": "bl_no",
        "description": "业务单号",
        "entry_kind": "generator",
        "spec": {"kind": "random_decorated", "length": 6, "head": "GIMBAL728"},
    }
    for payload in (lit, gen):
        r = await client.post("/api/constants", json=payload, headers=headers)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["name"] == payload["name"]
        assert body["id"] > 0
    assert body["value"] is None  # generator 行 value=null

    r = await client.get("/api/constants", headers=headers)
    assert r.status_code == 200
    items = r.json()
    assert [it["name"] for it in items] == ["bank_id", "bl_no"]  # name 升序


async def test_b2_owner_isolation_404(client: AsyncClient) -> None:
    alice = await _auth(client, "alice")
    r = await client.post(
        "/api/constants",
        json={"name": "x", "entry_kind": "literal", "value": "1"},
        headers=alice,
    )
    entry_id = r.json()["id"]

    bob = await _auth(client, "bob")
    for method, path in (
        ("get", f"/api/constants/{entry_id}"),
        ("patch", f"/api/constants/{entry_id}"),
        ("delete", f"/api/constants/{entry_id}"),
    ):
        r = await client.request(method, path, headers=bob, json={})
        assert r.status_code == 404, (method, r.text)
    # bob 看不到 alice 的条目
    r = await client.get("/api/constants", headers=bob)
    assert r.json() == []


async def test_b3_literal_requires_primitive_value(client: AsyncClient) -> None:
    headers = await _auth(client)
    r = await client.post(
        "/api/constants",
        json={"name": "bad", "entry_kind": "literal", "value": {"a": 1}},
        headers=headers,
    )
    assert r.status_code == 422
    # literal 携带 spec 也拒
    r = await client.post(
        "/api/constants",
        json={
            "name": "bad2", "entry_kind": "literal", "value": "ok",
            "spec": {"kind": "uuid"},
        },
        headers=headers,
    )
    assert r.status_code == 422


async def test_b4_generator_requires_spec_with_kind(client: AsyncClient) -> None:
    headers = await _auth(client)
    r = await client.post(
        "/api/constants",
        json={"name": "bad", "entry_kind": "generator", "spec": {"length": 6}},
        headers=headers,
    )
    assert r.status_code == 422
    r = await client.post(
        "/api/constants",
        json={"name": "bad2", "entry_kind": "generator", "value": "x"},
        headers=headers,
    )
    assert r.status_code == 422


async def test_b5_name_pattern(client: AsyncClient) -> None:
    headers = await _auth(client)
    for bad in ("with space", "中文", "a" * 65, "x-y", ""):
        r = await client.post(
            "/api/constants",
            json={"name": bad, "entry_kind": "literal", "value": "1"},
            headers=headers,
        )
        assert r.status_code == 422, bad


async def test_b6_duplicate_name_409_dict_detail(client: AsyncClient) -> None:
    headers = await _auth(client)
    payload = {"name": "dup", "entry_kind": "literal", "value": "1"}
    r = await client.post("/api/constants", json=payload, headers=headers)
    assert r.status_code == 201
    r = await client.post("/api/constants", json=payload, headers=headers)
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert isinstance(detail, dict)
    assert detail["code"] == "constant_name_exists"


async def test_b7_patch_rules(client: AsyncClient) -> None:
    headers = await _auth(client)
    r = await client.post(
        "/api/constants",
        json={"name": "g1", "entry_kind": "generator", "spec": {"kind": "seq"}},
        headers=headers,
    )
    gid = r.json()["id"]
    r = await client.post(
        "/api/constants",
        json={"name": "l1", "entry_kind": "literal", "value": "v"},
        headers=headers,
    )
    lid = r.json()["id"]

    # generator 行不接受 value;literal 行不接受 spec
    r = await client.patch(
        f"/api/constants/{gid}", json={"value": "x"}, headers=headers
    )
    assert r.status_code == 422
    r = await client.patch(
        f"/api/constants/{lid}", json={"spec": {"kind": "uuid"}}, headers=headers
    )
    assert r.status_code == 422
    # spec 必须含 kind
    r = await client.patch(
        f"/api/constants/{gid}", json={"spec": {"length": 6}}, headers=headers
    )
    assert r.status_code == 422
    # 正常 patch: generator 换 spec + 描述
    r = await client.patch(
        f"/api/constants/{gid}",
        json={"description": "序号", "spec": {"kind": "seq", "width": 8}},
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["description"] == "序号"
    assert body["spec"] == {"kind": "seq", "width": 8}
    # 正常 patch: literal 换 int 值
    r = await client.patch(
        f"/api/constants/{lid}", json={"value": 42}, headers=headers
    )
    assert r.status_code == 200
    assert r.json()["value"] == 42


async def test_b8_delete(client: AsyncClient) -> None:
    headers = await _auth(client)
    r = await client.post(
        "/api/constants",
        json={"name": "gone", "entry_kind": "literal", "value": "1"},
        headers=headers,
    )
    eid = r.json()["id"]
    r = await client.delete(f"/api/constants/{eid}", headers=headers)
    assert r.status_code == 204
    r = await client.get("/api/constants", headers=headers)
    assert r.json() == []


async def test_b9_literal_primitive_roundtrip(client: AsyncClient) -> None:
    headers = await _auth(client)
    cases = [
        ("s_val", "文本"),
        ("i_val", 42),
        ("f_val", 3.14),
        ("b_val", True),
    ]
    for name, value in cases:
        r = await client.post(
            "/api/constants",
            json={"name": name, "entry_kind": "literal", "value": value},
            headers=headers,
        )
        assert r.status_code == 201, name
        assert r.json()["value"] == value
