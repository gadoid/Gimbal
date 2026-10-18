"""外部接口登记批 X2:ext: 锚点化(设计 v1.0 §3/§4)。

覆盖:
1. 代理 /full 的 ext: 分支 —— 契约视图与 plate /full 同形(前端零改动
   消费:declarations 树 / binding 投影 / declared_surface);
2. plate_client.convert 统一剥 ext: 锚点(plate 零感知);
3. run/precheck 的 externalWarnings(D2 拍板:告警不阻塞 scheme_valid)。
"""
from __future__ import annotations

import httpx
import pytest

from app.services import plate_client
from app.services.plate_client import _strip_ext_anchors

from .helpers import make_draft, register_and_login

ALIAS = "gitlab-ext"
EP = f"ext:{ALIAS}.mr-create"

SCHEMA = {"type": "object", "required": ["title"], "properties": {
    "title": {"type": "string"},
    "force": {"type": "boolean"},
}}


async def _seed(client, admin) -> None:
    # b2-8 起 external 创建需显式 base_service;本文件随 ext 锚点在批3
    # 退役(C6/C10)—— 种子改直插绕过校验
    from app.core import db as db_module
    from app.models.service_alias import ServiceAlias

    async with db_module.SessionLocal() as s:
        s.add(ServiceAlias(alias_name=ALIAS, base_service=ALIAS,
                           base_url="https://git.example.com", kind="external"))
        await s.commit()
    r = await client.post("/api/external-endpoints", headers=admin, json={
        "aliasName": ALIAS, "name": "mr-create", "title": "建 MR",
        "method": "POST", "path": "/projects/{id}/merge_requests",
        "requestSchema": SCHEMA, "auth": "bearer"})
    assert r.status_code == 201, r.text


def _ext_step(body: dict) -> dict:
    return {
        "kind": "step", "endpoint": EP,
        "call": {"protocol": "http", "service": ALIAS, "headers": {}},
        "request": {"kind": "request", "body": body},
        "strategy": [],
    }


# ── 1. 代理 ext: 分支(契约视图同形)─────────────────────────────

async def test_catalog_full_ext_branch_isomorphic(client):
    admin = await register_and_login(client, "x2_admin", "pw123456")
    await _seed(client, admin)

    r = await client.get(f"/api/endpoint-catalog/{EP}/full", headers=admin)
    assert r.status_code == 200, r.text
    item = r.json()
    assert item["id"] == EP
    assert item["system"] == f"ext:{ALIAS}" and item["service"] == ALIAS
    assert item["name"] == "mr-create" and item["description"] == "建 MR"
    assert item["binding"]["method"] == "POST"
    assert item["binding"]["path"] == "/projects/{id}/merge_requests"
    assert item["binding"]["auth"] == "bearer"
    decls = item["request"]["declarations"]
    assert decls[0] == {"name": "title", "path": "$.title",
                        "type": "string", "state": "form", "required": True}
    assert "declared_surface" in item

    # 未知条目 404;坏锚点语法 404
    r = await client.get(
        "/api/endpoint-catalog/ext:gitlab-ext.no-such/full", headers=admin)
    assert r.status_code == 404
    r = await client.get("/api/endpoint-catalog/ext:bad-shape/full",
                         headers=admin)
    assert r.status_code == 404


# ── 2. convert 剥离(plate 零感知)───────────────────────────────

async def test_convert_strips_ext_anchors(client, monkeypatch):
    sent: list[dict] = []

    def _install():
        async def handler(request: httpx.Request) -> httpx.Response:
            sent.append(__import__("json").loads(request.content))
            return httpx.Response(200, json={
                "ok": True, "data": {"consumer": "gimbal",
                                     "converted": {"kind": "scenario"},
                                     "m2": {"hash": "h", "generation": 1}}})
        plate_client.set_client_for_tests(httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://plate-test"))

    _install()
    scenario = {"definition": {"meta": {"name": "n"}, "steps": [
        _ext_step({"title": "t"}),
        {"kind": "step", "endpoint": "fin.a.b",
         "call": {"protocol": "http", "service": "fin-service"},
         "request": {"kind": "request", "body": {}}, "strategy": []},
    ]}}
    await plate_client.convert(scenario)

    assert len(sent) == 1
    sent_steps = sent[0]["scenario"]["definition"]["steps"]
    # ext 锚点被剥;plate 锚点原样
    assert "endpoint" not in sent_steps[0]
    assert sent_steps[0]["request"]["body"] == {"title": "t"}  # 场景自有字段不动
    assert sent_steps[1]["endpoint"] == "fin.a.b"
    # 入参对象不被就地修改
    assert scenario["definition"]["steps"][0]["endpoint"] == EP


def test_strip_ext_anchors_pure_and_noop():
    # 无 ext 锚点 → 原对象返回(零拷贝)
    plain = {"definition": {"steps": [{"endpoint": "fin.a.b"}]}}
    assert _strip_ext_anchors(plain) is plain
    # 非 dict steps / 无 definition 原样
    assert _strip_ext_anchors({}) == {}
    assert _strip_ext_anchors({"definition": {}}) == {"definition": {}}


# ── 3. precheck externalWarnings(告警不阻塞)────────────────────

async def test_precheck_external_warnings_warn_not_block(client):
    admin = await register_and_login(client, "x2_pc", "pw123456")
    await _seed(client, admin)

    # 场景:ext 步骤 body 违 schema(缺必填 + 多余字段 + 类型不符)
    draft = make_draft("sc-x2", steps=[
        _ext_step({"bogus": 1, "force": "yes"})])   # 缺 title;多余 bogus;force 非布尔
    r = await client.post("/api/scenarios", headers=admin, json=draft)
    assert r.status_code in (200, 201), r.text

    # 建默认方案(确保 precheck 有方案面)
    r = await client.get("/api/scenarios/sc-x2/run-schemes", headers=admin)
    scheme_id = next(s["schemeId"] for s in r.json() if s["isDefault"])

    r = await client.post("/api/run/precheck", headers=admin, json=[
        {"scenarioId": "sc-x2", "schemeId": scheme_id}])
    assert r.status_code == 200, r.text
    out = r.json()[0]
    joined = "; ".join(out["externalWarnings"])
    assert "title 缺必填" in joined
    assert "bogus 不在目录登记" in joined
    assert "force 类型不符" in joined
    # D2:告警不阻塞
    assert out["schemeValid"] is True

    # body 合规 → 无告警
    draft2 = make_draft("sc-x2b", steps=[_ext_step({"title": "t",
                                                    "force": True})])
    r = await client.post("/api/scenarios", headers=admin, json=draft2)
    assert r.status_code in (200, 201), r.text
    r = await client.get("/api/scenarios/sc-x2b/run-schemes", headers=admin)
    scheme_id2 = next(s["schemeId"] for s in r.json() if s["isDefault"])
    r = await client.post("/api/run/precheck", headers=admin, json=[
        {"scenarioId": "sc-x2b", "schemeId": scheme_id2}])
    assert r.json()[0]["externalWarnings"] == []

    # 条目已删(目录无此条)→ 不出告警(回到自由编辑)
    draft3 = make_draft("sc-x2c", steps=[{
        "kind": "step", "endpoint": "ext:gitlab-ext.gone",
        "call": {"protocol": "http", "service": ALIAS, "headers": {}},
        "request": {"kind": "request", "body": {"x": 1}}, "strategy": []}])
    r = await client.post("/api/scenarios", headers=admin, json=draft3)
    assert r.status_code in (200, 201), r.text
    r = await client.get("/api/scenarios/sc-x2c/run-schemes", headers=admin)
    scheme_id3 = next(s["schemeId"] for s in r.json() if s["isDefault"])
    r = await client.post("/api/run/precheck", headers=admin, json=[
        {"scenarioId": "sc-x2c", "schemeId": scheme_id3}])
    assert r.json()[0]["externalWarnings"] == []
