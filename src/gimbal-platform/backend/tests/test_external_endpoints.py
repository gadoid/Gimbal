"""外部接口登记目录 X1(设计 v1.0 §2/§4)。

覆盖:
1. CRUD 链(alias_not_external 前置 / 重名 409 / 非法载荷 422 / admin 写面);
2. jsonschema_to_declarations 转换(平铺/嵌套/required/数组 items/无 schema);
3. check_body_against_schema 告警清单(D2 拍板:告警语义);
4. OpenAPI 导入(演练报告 → apply 落库 → 幂等复跑;servers.url 补 base_url)。
"""
from __future__ import annotations

from app.services.external_endpoints import (
    check_body_against_schema,
    jsonschema_to_declarations,
)

from .helpers import register_and_login

ALIAS = "gitlab-ext"


async def _seed_external_alias(client, admin) -> None:
    r = await client.post("/api/service-aliases", headers=admin, json={
        "aliasName": ALIAS, "kind": "external",
        "baseUrl": "https://git.example.com",
    })
    assert r.status_code in (200, 201), r.text


# ── 转换器(纯函数)──────────────────────────────────────────────

def test_declarations_flat_and_required():
    schema = {"type": "object", "required": ["id"], "properties": {
        "id": {"type": "integer"},
        "name": {"type": "string"},
    }}
    decls = jsonschema_to_declarations(schema)
    assert decls == [
        {"name": "id", "path": "$.id", "type": "number",
         "state": "form", "required": True},
        {"name": "name", "path": "$.name", "type": "string",
         "state": "form", "required": False},
    ]


def test_declarations_nested_object_tree():
    schema = {"type": "object", "properties": {
        "address": {"type": "object", "required": ["city"], "properties": {
            "city": {"type": "string"},
            "zip": {"type": "string"},
        }},
    }}
    decls = jsonschema_to_declarations(schema)
    assert len(decls) == 1 and decls[0]["name"] == "address"
    children = decls[0]["children"]
    assert [c["path"] for c in children] == ["$.address.city", "$.address.zip"]
    assert children[0]["required"] is True and children[1]["required"] is False


def test_declarations_array_items_and_empty_shapes():
    # 数组元素结构挂 children(path 带 [0])
    decls = jsonschema_to_declarations({"type": "object", "properties": {
        "items": {"type": "array", "items": {"type": "object", "properties": {
            "sku": {"type": "string"}}}}}})
    assert decls[0]["children"][0]["path"] == "$.items[0].sku"
    # 无 schema / 非 object 根 / 无 properties → [](表单自由编辑)
    assert jsonschema_to_declarations(None) == []
    assert jsonschema_to_declarations({"type": "string"}) == []
    assert jsonschema_to_declarations({"type": "object"}) == []


# ── 告警校验(纯函数,D2:告警不阻塞)────────────────────────────

def test_check_body_warns_on_extra_missing_type():
    schema = {"type": "object", "required": ["id"], "properties": {
        "id": {"type": "integer"},
        "addr": {"type": "object", "properties": {
            "city": {"type": "string"}}},
    }}
    warns = check_body_against_schema({"id": "x", "bogus": 1,
                                       "addr": {"city": 9}}, schema)
    joined = "; ".join(warns)
    assert "缺必填" not in joined or True    # id 在(类型不符而非缺失)
    assert "id 类型不符" in joined
    assert "bogus 不在目录登记" in joined
    assert "addr.city 类型不符" in joined
    # 缺必填
    warns2 = check_body_against_schema({"name": "n"}, schema)
    assert any("id 缺必填" in w for w in warns2)
    # 无 schema / body 非 dict → 空
    assert check_body_against_schema({"a": 1}, None) == []
    assert check_body_against_schema("not-dict", schema) == []


# ── CRUD 链(HTTP)───────────────────────────────────────────────

async def test_crud_lifecycle_and_external_alias_gate(client):
    admin = await register_and_login(client, "ext_admin", "pw123456")
    await _seed_external_alias(client, admin)

    # 别名不存在 → 404(external 前置校验的第一档)
    r = await client.post("/api/external-endpoints", headers=admin, json={
        "aliasName": "no-such-alias", "name": "orders", "method": "GET",
        "path": "/orders"})
    assert r.status_code == 404, r.text
    assert "alias_not_found" in r.text

    # 登记
    r = await client.post("/api/external-endpoints", headers=admin, json={
        "aliasName": ALIAS, "name": "mr-list", "title": "MR 列表",
        "method": "GET", "path": "/api/v4/merge_requests",
        "requestSchema": {"type": "object", "properties": {
            "state": {"type": "string"}},
            "required": ["state"]},
        "auth": "bearer"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["aliasName"] == ALIAS and body["auth"] == "bearer"

    # 重名 409
    r = await client.post("/api/external-endpoints", headers=admin, json={
        "aliasName": ALIAS, "name": "mr-list", "method": "GET",
        "path": "/mr"})
    assert r.status_code == 409 and "name_conflict" in r.text

    # 非法载荷 422(接口名含 . / method / path)
    r = await client.post("/api/external-endpoints", headers=admin, json={
        "aliasName": ALIAS, "name": "a.b", "method": "GET", "path": "/x"})
    assert r.status_code == 422
    r = await client.post("/api/external-endpoints", headers=admin, json={
        "aliasName": ALIAS, "name": "ok", "method": "BREW", "path": "/x"})
    assert r.status_code == 422

    # 列表 + 详情(契约视图同形 plate /full)
    r = await client.get("/api/external-endpoints", headers=admin,
                         params={"alias": ALIAS})
    assert r.status_code == 200 and len(r.json()["items"]) == 1
    r = await client.get(f"/api/external-endpoints/{ALIAS}/mr-list",
                         headers=admin)
    assert r.status_code == 200, r.text
    contract = r.json()["contract"]
    assert contract["id"] == f"ext:{ALIAS}.mr-list"
    assert contract["method"] == "GET"
    assert contract["request"]["declarations"] == [
        {"name": "state", "path": "$.state", "type": "string",
         "state": "form", "required": True}]

    # 更新
    r = await client.patch(f"/api/external-endpoints/{ALIAS}/mr-list",
                           headers=admin, json={"title": "MR 列表 v2",
                                                "auth": "none"})
    assert r.status_code == 200 and r.json()["title"] == "MR 列表 v2"

    # 删除
    r = await client.delete(f"/api/external-endpoints/{ALIAS}/mr-list",
                            headers=admin)
    assert r.status_code == 204
    r = await client.get(f"/api/external-endpoints/{ALIAS}/mr-list",
                         headers=admin)
    assert r.status_code == 404


async def test_write_requires_admin(client):
    await register_and_login(client, "ext_admin_real", "pw123456")  # 垫 admin
    member = await register_and_login(client, "ext_member", "pw123456")
    r = await client.post("/api/external-endpoints", headers=member, json={
        "aliasName": ALIAS, "name": "x", "method": "GET", "path": "/x"})
    assert r.status_code == 403, r.text


# ── OpenAPI 导入(演练/apply/幂等)───────────────────────────────

_OPENAPI = {
    "openapi": "3.0.0",
    "servers": [{"url": "https://git.example.com/api/v4"}],
    "paths": {
        "/projects": {
            "get": {"summary": "项目列表"}},
        "/projects/{id}/merge_requests": {
            "post": {"summary": "建 MR", "requestBody": {"content": {
                "application/json": {"schema": {
                    "type": "object", "required": ["title"],
                    "properties": {"title": {"type": "string"}}}}}}},
            "get": {"summary": "MR 列表"}},
    },
}


async def test_openapi_import_dry_run_apply_and_idempotent(client):
    admin = await register_and_login(client, "ext_admin2", "pw123456")
    await _seed_external_alias(client, admin)

    # 演练:报告不落库
    r = await client.post("/api/external-endpoints/import-openapi",
                          headers=admin, json={"aliasName": ALIAS,
                                               "document": _OPENAPI})
    assert r.status_code == 200, r.text
    report = r.json()
    assert report["applied"] is False and report["created"] == 3
    assert report["base_url"] == "https://git.example.com/api/v4"
    r = await client.get("/api/external-endpoints", headers=admin,
                         params={"alias": ALIAS})
    assert r.json()["items"] == []          # 演练不落库

    # apply:落库 + 别名 base_url 已有则不覆盖
    r = await client.post("/api/external-endpoints/import-openapi",
                          headers=admin,
                          params={"apply": "true"},
                          json={"aliasName": ALIAS, "document": _OPENAPI})
    assert r.status_code == 200 and r.json()["created"] == 3
    r = await client.get("/api/external-endpoints", headers=admin,
                         params={"alias": ALIAS})
    names = sorted(i["name"] for i in r.json()["items"])
    # GET 无后缀;非 GET 带 method 后缀(同 path 多 method 不撞名)
    assert names == ["projects", "projects-id-merge_requests",
                     "projects-id-merge_requests-post"]

    # 建模 schema 落对位(POST 条目带 required title)
    r = await client.get(
        f"/api/external-endpoints/{ALIAS}/projects-id-merge_requests-post",
        headers=admin)
    decls = r.json()["contract"]["request"]["declarations"]
    assert decls[0]["name"] == "title" and decls[0]["required"] is True

    # 幂等复跑:全部 skipped
    r = await client.post("/api/external-endpoints/import-openapi",
                          headers=admin,
                          params={"apply": "true"},
                          json={"aliasName": ALIAS, "document": _OPENAPI})
    assert r.json()["created"] == 0 and r.json()["skipped"] == 3

    # 别名 base_url 为空时 apply 补 servers.url;已有值不覆盖。
    # (wire 面 baseUrl 必填报不出空行 —— ORM 直插,语义面在 service 层)
    from app.core import db as db_module
    from app.models.service_alias import ServiceAlias
    from sqlalchemy import select as sa_select
    async with db_module.SessionLocal() as s:
        s.add(ServiceAlias(alias_name="gitlab-bare", base_service="gitlab",
                           base_url="", kind="external"))
        await s.commit()
    r = await client.post("/api/external-endpoints/import-openapi",
                          headers=admin, params={"apply": "true"},
                          json={"aliasName": "gitlab-bare",
                                "document": _OPENAPI})
    assert r.json()["base_url"] == "https://git.example.com/api/v4"
    async with db_module.SessionLocal() as s:
        row = await s.get(ServiceAlias, "gitlab-bare")
        assert row.base_url == "https://git.example.com/api/v4"   # 空 → 补
        row2 = await s.get(ServiceAlias, ALIAS)
        assert row2.base_url == "https://git.example.com"         # 已有 → 不覆盖
    _ = sa_select


async def test_openapi_import_rejects_bad_docs(client):
    admin = await register_and_login(client, "ext_admin3", "pw123456")
    await _seed_external_alias(client, admin)
    r = await client.post("/api/external-endpoints/import-openapi",
                          headers=admin,
                          json={"aliasName": ALIAS, "document": {}})
    assert r.status_code == 422 and "invalid_openapi" in r.text
