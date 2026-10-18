"""批0 特征化基线(平台侧)—— B1/B2/B4/B6/B7/B8/B9/B10/B11(实施计划 v1.1 §2)。

只钉现状、不改行为;每个测试标注「预期变更点」或「不预期变更」——
对应实现步骤落地时在**同一提交**翻转断言(提交信息注明「基线翻转:<步号>」),
未标注变更点的断言在任何批次都不许静默变化。
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import run_semantics
from app.services.integration_runner import is_scenario_read_only
from app.services.run_materialize import _apply_services
from app.services.scenario_store import _strip_platform_meta

# ── B1|只读闸 ext: 分支现状(预期变更点 b2-11:删 ext: DB 分支) ────────


def _gate_scenario(endpoint: str | None, method: str | None) -> dict:
    call: dict = {"protocol": "http", "service": "svc", "headers": {}}
    if method:
        call["method"] = method
    step = {"kind": "step", "call": call,
            "request": {"kind": "request", "body": {}}, "strategy": []}
    if endpoint:
        step["endpoint"] = endpoint
    return {"definition": {"meta": {"name": "n"}, "steps": [step]}}


async def test_b1_ext_inline_get_passes():
    """ext: 步骤带内联 GET → 放行(现状)。"""
    ok, offenders = await is_scenario_read_only(
        _gate_scenario("ext:jira-x.search", "GET"))
    assert ok and offenders == []


async def test_b1_ext_inline_post_rejected_even_when_directory_marked_safe(client):
    """反转依据①的实证钉:目录条目 query_safe=True **救不了**带内联 POST 的
    ext: 步骤。基线翻转:b2-11 —— ext: DB 分支已删,目录彻底不被读
    (行为等价:内联 method 优先 → POST 未标即拒)。"""
    from app.core import db as db_module
    from app.models.external_endpoint import ExternalEndpoint
    from app.models.service_alias import ServiceAlias

    async with db_module.SessionLocal() as s:
        s.add(ServiceAlias(alias_name="jira-x", base_service="jira",
                           base_url="https://jira", kind="external"))
        await s.flush()
        s.add(ExternalEndpoint(alias_name="jira-x", name="search",
                               title="搜索", method="POST", path="/search",
                               query_safe=True))
        await s.commit()
    ok, offenders = await is_scenario_read_only(
        _gate_scenario("ext:jira-x.search", "POST"))
    assert not ok and offenders, "内联 POST 必拒,目录 query_safe 不生效"


async def test_b1_ext_without_inline_method_fails_closed(client):
    """基线翻转(新增,b2-11 过渡期行为 §3.5):无内联 method 的 ext: 步骤
    落入 plate 分支取不到定义 → fail-closed(未知方法)。"""
    ok, offenders = await is_scenario_read_only(
        _gate_scenario("ext:jira-x.search", None))
    assert not ok and offenders


async def test_b1_plate_unreachable_propagates(monkeypatch):
    """plate 不可达:闸函数本身不吞,fail-closed 收口在 run_instance(现状)。"""
    from app.services import plate_client

    async def boom(eid: str, **kw):
        raise plate_client.PlateUnavailableError("plate_unavailable: test")

    monkeypatch.setattr(plate_client, "get_endpoint_full", boom)
    with pytest.raises(plate_client.PlateUnavailableError):
        await is_scenario_read_only(_gate_scenario("fin.a.a", None))


# ── B2/B6|ref 语义现状:working_preview / anchored_systems(不预期变更) ──


def _payload(plate: dict | None, *endpoints: str) -> dict:
    steps = []
    for ep in endpoints:
        steps.append({"kind": "step", "endpoint": ep,
                      "call": {"kind": "call", "service": "svc"},
                      "request": {"kind": "request", "body": {}},
                      "strategy": []})
    definition: dict = {"meta": {"name": "n"}, "steps": steps}
    if plate is not None:
        definition["meta"]["plate"] = plate
    return {"definition": definition}


def test_b2b6_working_preview_variants():
    p = _payload({"fin": "1.0#1"}, "fin.a.a")
    assert run_semantics.working_preview(p) is False, "全钉定 → 正式执行"
    assert run_semantics.working_preview(
        _payload({"fin": "1.0#1", "platform": "working"}, "fin.a.a",
                 "platform.b.x")) is True, "任一 working → 预览"
    assert run_semantics.working_preview(
        _payload({"fin": "1.0#1"}, "fin.a.a", "platform.b.x")) is True, \
        "锚定了未声明系统 → 预览(undeclared)"
    assert run_semantics.anchored_systems(_payload(None, "fin.a.a")) == {"fin"}


# ── B4|assess_baseline 分桶与异常路径(异常路径预期变更点 b2-6) ────────


async def _classify_stub(monkeypatch, external=None, unknown=None):
    from app.services import service_aliases

    async def stub(db, names):
        return {"external": external or [], "unknown": unknown or []}
    monkeypatch.setattr(service_aliases, "classify_services", stub)


async def test_b4_baseline_buckets(monkeypatch):
    epu = {"fin": ["fin.a.a"]}
    # working 桶(短路最先)
    ok, block, _ = await run_semantics.assess_baseline(
        db=None, meta_plate={"fin": "working"}, endpoints_used=epu,
        unanchored_services=[], review_lookup=None)
    assert (ok, block) == (False, "working")
    # unreviewed 桶(钉定 + 评审缺失)
    async def no_review(sys_, ref):
        return {}
    ok, block, ev = await run_semantics.assess_baseline(
        db=None, meta_plate={"fin": "1.0#1"}, endpoints_used=epu,
        unanchored_services=[], review_lookup=no_review)
    assert (ok, block) == (False, "unreviewed")
    assert ev["unreviewed_endpoints"] == {"fin": ["fin.a.a"]}
    # eligible(钉定 + 全评审)
    async def all_reviewed(sys_, ref):
        return {"fin.a.a": "reviewed"}
    ok, block, ev = await run_semantics.assess_baseline(
        db=None, meta_plate={"fin": "1.0#1"}, endpoints_used=epu,
        unanchored_services=[], review_lookup=all_reviewed)
    assert (ok, block, ev) == (True, None, {})
    # external 桶(未锚定的外部/未知服务)
    await _classify_stub(monkeypatch, external=["jira-x"], unknown=["stub"])
    ok, block, ev = await run_semantics.assess_baseline(
        db=None, meta_plate={"fin": "1.0#1"}, endpoints_used=epu,
        unanchored_services=["jira-x", "stub"], review_lookup=all_reviewed)
    assert (ok, block) == (False, "external")
    assert ev["external_services"] == ["jira-x"] and ev["unknown_services"] == ["stub"]


async def test_b4_integration_short_circuits_to_external_bucket(monkeypatch):
    """基线翻转:b2-6 —— integration 在按修订查评审前短路归 external 桶
    (此前是未捕获的 PlateRejectedError invalid_ref;review_lookup 不被触达)。"""
    called = []

    async def rejecting(sys_, ref):
        called.append((sys_, ref))
        raise AssertionError("integration 不应触达 review_lookup")

    ok, block, ev = await run_semantics.assess_baseline(
        db=None, meta_plate={"fin": "integration"}, endpoints_used={"fin": ["fin.a.a"]},
        unanchored_services=[], review_lookup=rejecting)
    assert (ok, block) == (False, "external")
    assert ev.get("integration_systems") == ["fin"]
    assert called == []


# ── B7|适配 from=working 现状(不预期变更;integration 跳过在 b2-3) ─────


async def test_b7_compare_scenario_uses_working_as_from(monkeypatch, fresh_db):
    """working 声明作为适配起点传给 plate diff(from=working 现有能力)。"""
    from app.core import db as db_module
    from app.models.composer_scenario import ComposerScenario
    from tests.helpers import ensure_fk_users, make_draft

    import uuid
    sid = f"sc-b7-{uuid.uuid4().hex[:8]}"
    draft = make_draft(sid, plate={"fin": "working"})
    async with db_module.SessionLocal() as s:
        await ensure_fk_users(s, 1)
        s.add(ComposerScenario(scenario_id=sid, owner_name="u1",
                               owner_id=1, payload=draft))
        await s.commit()
    captured: dict = {}

    class _Stop(Exception):
        pass

    from app.services import adaptation_service

    async def fake_diff(*args, **kw):
        captured["args"], captured["kw"] = args, kw
        raise _Stop()

    monkeypatch.setattr(adaptation_service, "plate_diff_for_adaptation", fake_diff)
    with pytest.raises(_Stop):
        async with db_module.SessionLocal() as db:
            await adaptation_service.compare_scenario(
                db, scenario_id=sid, target_revision="1.0#2", system="fin")
    assert "working" in captured["args"] or "working" in captured["kw"].values(), \
        captured


# ── B8|服务实例解析优先级(不预期变更;唯一组装点 _apply_services) ─────


def _steps(svc: str) -> list:
    return [{"kind": "step", "call": {"kind": "call", "service": svc}}]


def test_b8_priority_chain():
    # ① 显式绑定 > ② authored > ③ 别名 base_url > ④ 缺口
    cfg = {"services": {}}
    _apply_services(cfg, steps=_steps("svc"),
                    bindings={"svc": {"url": "http://bound"}},
                    alias_base_urls={"svc": "http://alias"})
    assert cfg["services"]["svc"] == "http://bound"

    cfg = {"services": {"svc": "http://authored"}}
    _apply_services(cfg, steps=_steps("svc"), bindings={},
                    alias_base_urls={"svc": "http://alias"})
    assert cfg["services"]["svc"] == "http://authored", "authored 不被别名覆盖"

    cfg = {"services": {}}
    _apply_services(cfg, steps=_steps("svc"), bindings={},
                    alias_base_urls={"svc": "http://alias"})
    assert cfg["services"]["svc"] == "http://alias", "别名仅补缺"

    cfg = {"services": {}}
    _apply_services(cfg, steps=_steps("svc"), bindings={}, alias_base_urls={})
    assert "svc" not in cfg["services"], "缺口留给引擎显式报错"


# ── B9|导出/存储面 meta.plate 保留(不预期变更) ──────────────────────


def test_b9_strip_platform_meta_keeps_plate():
    meta = {"name": "n", "plate": {"fin": "1.0#2"},
            "scenarioId": "sc-x", "updateTime": "t", "owner": "o"}
    out = _strip_platform_meta(meta)
    assert out["plate"] == {"fin": "1.0#2"}
    assert set(out) == {"name", "plate"}


# ── B10|carry 基名解析样本(预期变更点 b2-9:D-M 别名表优先改变次序) ────

_FIXTURE = Path(__file__).parent / "fixtures" / "b0_sut_carry_base.json"


def test_b10_derive_base_samples():
    """现状:运行时 derive_base 单射(无别名表参与);批0 盘点 A5 的
    fin.order/stub 在现行目录下推不出基名(与盘点档一致)。"""
    from app.services.service_names import derive_base

    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    catalog = set(data["catalog"])
    for case in data["cases"]:
        got = derive_base(case["key"], catalog)
        assert got == case["base"], (case, got)


async def test_b10_plate_list_endpoints_reads_global_list(monkeypatch):
    """现状:轻端点清单直读 plate /api/endpoint 全局路由(无过滤)。"""
    from app.services import adaptation_service, plate_client

    item = {"id": "fin.a.a", "service": "fin-service"}

    class FakeResp:
        status_code = 200

        def json(self):
            return {"data": {"items": [item]}}

    class FakeClient:
        async def get(self, url, **kw):
            captured["url"] = url
            return FakeResp()

    captured: dict = {}
    monkeypatch.setattr(plate_client, "get_client", lambda: FakeClient())
    out = await adaptation_service._plate_list_endpoints()
    assert out == [item] and captured["url"] == "/api/endpoint"


# ── B11|/api/catalog/services 行形状(预期变更点 b1-3 + b2-7) ─────────


async def test_b11_catalog_row_shape_carries_kind(monkeypatch):
    """基线翻转:b1-3+b2-7 —— 聚合经 plate_client 唯一访问件(/api/endpoint
    全量行),行带 kind(由端点行带出);三视图共享同一缓存缝隙。"""
    from app.routers import catalog
    from app.services import plate_client

    items = [
        {"id": "fin.a.a", "service": "fin-service", "system": "fin", "kind": "sut"},
        {"id": "fin.a.b", "service": "fin-service", "system": "fin", "kind": "sut"},
        {"id": "jira.x.q", "service": "jira-service", "system": "jira",
         "kind": "integration"},
    ]

    async def fake_rows(**kw):
        return items

    monkeypatch.setattr(plate_client, "_catalog_endpoints", fake_rows)
    out = await catalog._fetch_and_aggregate()
    assert [s.model_dump() for s in out.services] == [
        {"name": "fin-service", "system": "fin", "endpointCount": 2, "kind": "sut"},
        {"name": "jira-service", "system": "jira", "endpointCount": 1,
         "kind": "integration"},
    ], "聚合行带 kind —— b1-3/b2-7 落地后口径"
    # 扁平名视图:带 kind(sut 子集由派生点取)
    entries = await plate_client.catalog_service_entries()
    assert {"name": "jira-service", "kind": "integration"} in entries
