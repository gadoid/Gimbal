"""集成线 v2 / I4 验收(方案 §5 I4 行):平台模式只读口径补全
query_safe(兑现 P1 立下的欠条)。

- plate 锚点:``metadata.query_safe=true`` 的 POST 查询可进平台模式
  (R-E:/full 投影带 metadata,桩直接给同形 item);
- ext: 锚点:外部目录条目 ``query_safe=true`` 同款;撤销后未标记的
  POST 拒绝并列判定依据「步骤 i(POST,未标 query_safe)」;
- admin 开关路由:非 admin 403;标记/撤销写审计
  (external_endpoint.query_safe,detail 带接口名与别名);
- OpenAPI 导入不自动标记(条目 query_safe=false);
- 手写原始调用仍只认 method(fail-closed)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import select

from app.core import db as db_module
from app.models import AuditLog
from app.models.external_endpoint import ExternalEndpoint
from app.models.service_alias import ServiceAlias
from app.services.integration_runner import is_scenario_read_only
from tests.helpers import register_and_login


def _anchored(endpoint: str, *, method: str | None = None) -> dict:
    call: dict = {"protocol": "http", "service": "svc", "headers": {}}
    if method:
        call["method"] = method
    step = {"kind": "step", "call": call,
            "request": {"kind": "request", "body": {}}, "strategy": []}
    if endpoint:
        step["endpoint"] = endpoint
    return {"definition": {"meta": {"name": "n"}, "steps": [step]}}


# ── plate 锚点:metadata.query_safe ────────────────────────────────

async def test_plate_query_safe_post_passes_gate(monkeypatch):
    """Jira POST /search 一类:契约标了 query_safe → 只读闸放行。"""
    from app.services import plate_client

    async def fake_full(eid: str, **kw):
        return SimpleNamespace(item={
            "binding": {"method": "POST"},
            "metadata": {"query_safe": True},
        })

    monkeypatch.setattr(plate_client, "get_endpoint_full", fake_full)
    ok, offenders = await is_scenario_read_only(
        _anchored("fin.orders.search"))
    assert ok and offenders == []

    # 未标记 → 拒,判定依据带「未标 query_safe」
    async def fake_full_unmarked(eid: str, **kw):
        return SimpleNamespace(item={
            "binding": {"method": "POST"},
            "metadata": {"query_safe": False},
        })

    monkeypatch.setattr(plate_client, "get_endpoint_full", fake_full_unmarked)
    ok, offenders = await is_scenario_read_only(
        _anchored("fin.orders.search"))
    assert not ok
    assert "POST" in offenders[0] and "未标 query_safe" in offenders[0]

    # 契约不可得 → fail-closed(无标记提示,只有未知方法)
    async def none_full(eid: str, **kw):
        return SimpleNamespace(item=None)

    monkeypatch.setattr(plate_client, "get_endpoint_full", none_full)
    ok, offenders = await is_scenario_read_only(
        _anchored("fin.orders.search"))
    assert not ok and "未知方法" in offenders[0]


# ── ext: 锚点:目录条目 query_safe ─────────────────────────────────

async def _seed_ext_dir() -> None:
    async with db_module.SessionLocal() as s:
        s.add(ServiceAlias(alias_name="jira-x", base_service="jira",
                           base_url="https://jira", kind="external"))
        await s.flush()
        s.add(ExternalEndpoint(alias_name="jira-x", name="search",
                               title="搜索", method="POST", path="/search"))
        await s.commit()


async def test_ext_query_safe_gate_and_toggle_route(client, monkeypatch):
    await _seed_ext_dir()
    h = await register_and_login(client, "qs_admin", "pw123456")
    # 提权 admin
    from app.models.user import User
    async with db_module.SessionLocal() as s:
        u = (await s.execute(select(User).where(
            User.username == "qs_admin"))).scalar()
        u.role = "admin"
        await s.commit()

    # b2-11 过渡期口径:ext: 目录不再喂闸 —— 无内联 method 即 fail-closed
    ok, offenders = await is_scenario_read_only(
        _anchored("ext:jira-x.search"))
    assert not ok and offenders

    # 非 admin 开关 → 403
    h2 = await register_and_login(client, "qs_user", "pw123456")
    r = await client.post("/api/external-endpoints/jira-x/search/query-safe",
                          headers=h2, json={"on": True})
    assert r.status_code == 403

    # admin 标记 → 200 + 审计行 + 闸放行 + 撤销即再拒(执行前二次检查
    # 由 run_instance 的同款闸兜口,分类 channel、前缀「只读检查未通过:」)
    r = await client.post("/api/external-endpoints/jira-x/search/query-safe",
                          headers=h, json={"on": True})
    assert r.status_code == 200, r.text
    assert r.json()["querySafe"] is True
    async with db_module.SessionLocal() as s:
        audits = (await s.execute(select(AuditLog).where(
            AuditLog.action == "external_endpoint.query_safe"))).scalars().all()
        assert audits, "标记未写审计"
        d = audits[-1].detail
        assert d.get("aliasName") == "jira-x" and d.get("name") == "search"
        assert d.get("querySafe") is True

    # 目录标记不再影响闸(b2-11);下方仅钉路由/审计行为本身(批3 C4 退役)

    # 撤销 → 拒 + 审计
    r = await client.post("/api/external-endpoints/jira-x/search/query-safe",
                          headers=h, json={"on": False})
    assert r.status_code == 200
    ok, offenders = await is_scenario_read_only(
        _anchored("ext:jira-x.search"))
    assert not ok
    async with db_module.SessionLocal() as s:
        n = len((await s.execute(select(AuditLog).where(
            AuditLog.action == "external_endpoint.query_safe"))).scalars().all())
        assert n == 2   # 标记 + 撤销各一条


# ── OpenAPI 导入不自动标记 ─────────────────────────────────────────

async def test_openapi_import_does_not_mark_query_safe(client):
    h = await register_and_login(client, "qs_imp", "pw123456")
    from app.models.user import User
    async with db_module.SessionLocal() as s:
        u = (await s.execute(select(User).where(
            User.username == "qs_imp"))).scalar()
        u.role = "admin"
        await s.commit()
        s.add(ServiceAlias(alias_name="ms-x", base_service="ms",
                           base_url="https://ms", kind="external"))
        await s.commit()

    doc = {"paths": {"/list": {"post": {"summary": "列表",
                                        "requestBody": None}}},
           "servers": []}
    r = await client.post("/api/external-endpoints/import-openapi?apply=true",
                          headers=h, json={"aliasName": "ms-x",
                                           "document": doc})
    assert r.status_code == 200, r.text
    async with db_module.SessionLocal() as s:
        rows = (await s.execute(select(ExternalEndpoint).where(
            ExternalEndpoint.alias_name == "ms-x"))).scalars().all()
        assert rows and all(not r_.query_safe for r_ in rows)


# ── 手写原始调用:只认 method(fail-closed 不变)──────────────────

async def test_handwritten_call_still_method_only():
    ok, _ = await is_scenario_read_only(
        _anchored("", method="GET"))
    assert ok
    ok, offenders = await is_scenario_read_only(
        _anchored("", method="POST"))
    assert not ok and "未标 query_safe" not in offenders[0].split("(")[1]
