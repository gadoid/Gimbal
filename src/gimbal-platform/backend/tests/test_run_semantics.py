"""run_semantics 单元测试(W5/A-2 预览口径;版本模型 §6)。

预览 = 任一**受管系统** working(显式 "working" 或锚点系统未钉修订);
无锚点步骤(external/手写调用)不参与判定(P1.0 三态接入)。
"""
from __future__ import annotations

from app.services.run_semantics import anchored_systems, working_preview


def _payload(steps: list | None = None, plate: dict | None = None) -> dict:
    meta: dict = {"name": "T", "module": "m", "system": ["fin"]}
    if plate is not None:
        meta["plate"] = plate
    return {"definition": {
        "kind": "scenario", "scenarioId": "sc-sem", "meta": meta,
        "config": {}, "resource": {}, "steps": steps or [],
    }}


_ANCHORED = [{"kind": "step", "endpoint": "fin.orders.get",
              "call": {"service": "fin.order"}, "strategy": []}]
_RAW = [{"kind": "step",
         "call": {"service": "pay-svc", "method": "POST", "path": "/x"},
         "strategy": []}]


def test_anchored_systems_extracts_endpoint_prefix() -> None:
    assert anchored_systems(_payload(
        _ANCHORED + [_RAW])) == {"fin"}
    assert anchored_systems(_payload(_RAW)) == set()
    assert anchored_systems(None) == set()


def test_no_anchored_steps_is_formal() -> None:
    """纯 external/手写调用:无受管系统 → 非预览(A-4 放行的根基)。"""
    assert working_preview(_payload(_RAW, plate={})) is False


def test_undeclared_anchored_system_is_preview() -> None:
    """锚点系统未钉修订(存量 meta.plate={})→ 预览。"""
    assert working_preview(_payload(_ANCHORED, plate={})) is True


def test_explicit_working_is_preview() -> None:
    assert working_preview(_payload(_ANCHORED, plate={"fin": "working"})) is True


def test_pinned_is_formal() -> None:
    assert working_preview(
        _payload(_ANCHORED, plate={"fin": "1.0#1"})) is False


def test_mixed_pinned_plus_raw_external_is_formal() -> None:
    """钉定受管系统 + external 手写步骤共存 → 非预览(external 不触发)。"""
    assert working_preview(
        _payload(_ANCHORED + _RAW, plate={"fin": "1.0#1"})) is False


def test_any_working_system_poisons_the_rest() -> None:
    steps = _ANCHORED + [{"kind": "step", "endpoint": "plat.x",
                          "strategy": []}]
    assert working_preview(
        _payload(steps, plate={"fin": "1.0#1", "plat": "working"})) is True


def test_declaration_for_unused_system_is_ignored() -> None:
    """只声明了未使用系统、锚点系统缺声明 → 仍预览。"""
    assert working_preview(
        _payload(_ANCHORED, plate={"other": "1.0#1"})) is True


# ── 入库标准判定(A-3/W7;版本模型 4.3)───────────────────────────
async def _lookup(review_map: dict) -> object:
    async def _f(system: str, ref: str) -> dict[str, str]:
        return review_map
    return _f


def _mk(review_map: dict):
    async def _lookup(system: str, ref: str) -> dict[str, str]:
        return review_map
    return _lookup


async def test_assess_baseline_eligible(fresh_db) -> None:
    """钉定 + 全评审 + 无 external → 入库。"""
    from app.services.run_semantics import assess_baseline
    from app.core import db as db_module
    async with db_module.SessionLocal() as s:
        out = await assess_baseline(
            s, meta_plate={"fin": "1.0#1"},
            endpoints_used={"fin": ["fin.orders.get", "fin.orders.create"]},
            unanchored_services=[],
            review_lookup=_mk({"fin.orders.get": "reviewed",
                               "fin.orders.create": "reviewed"}))
    assert out == (True, None, {})


async def test_assess_baseline_working_blocks_first(fresh_db) -> None:
    """未钉/working 系统短路(不触 plate),证据记 working_systems。"""
    from app.services.run_semantics import assess_baseline
    from app.core import db as db_module
    called = []

    async def _probe(system: str, ref: str) -> dict[str, str]:
        called.append(system)
        return {}
    async with db_module.SessionLocal() as s:
        out = await assess_baseline(
            s, meta_plate={}, endpoints_used={"fin": ["fin.orders.get"]},
            unanchored_services=[], review_lookup=_probe)
    assert out == (False, "working", {"working_systems": ["fin"]})
    assert called == []          # working 短路,不触 plate


async def test_assess_baseline_unreviewed(fresh_db) -> None:
    from app.services.run_semantics import assess_baseline
    from app.core import db as db_module
    async with db_module.SessionLocal() as s:
        out = await assess_baseline(
            s, meta_plate={"fin": "1.0#1"},
            endpoints_used={"fin": ["fin.orders.get", "fin.orders.create"]},
            unanchored_services=[],
            review_lookup=_mk({"fin.orders.get": "reviewed",
                               "fin.orders.create": "draft"}))
    assert out == (False, "unreviewed",
                   {"unreviewed_endpoints": {"fin": ["fin.orders.create"]}})


async def test_assess_baseline_external_bucket(fresh_db) -> None:
    """external 服务不入基线、按桶单列(已登记 external 别名)。"""
    from app.services.run_semantics import assess_baseline
    from app.core import db as db_module
    from app.models.service_alias import ServiceAlias
    async with db_module.SessionLocal() as s:
        s.add(ServiceAlias(alias_name="pay-service",
                           base_service="pay-service", kind="external"))
        await s.commit()
    async with db_module.SessionLocal() as s:
        out = await assess_baseline(
            s, meta_plate={"fin": "1.0#1"},
            endpoints_used={"fin": ["fin.orders.get"]},
            unanchored_services=["pay-service"],
            review_lookup=_mk({"fin.orders.get": "reviewed"}))
    assert out == (False, "external",
                   {"external_services": ["pay-service"],
                    "unknown_services": []})


async def test_assess_baseline_unknown_counts_as_external(fresh_db) -> None:
    """未登记服务按 external 阻塞(保守:未登记 = 未受管,无契约可验证)。"""
    from app.services.run_semantics import assess_baseline
    from app.core import db as db_module
    async with db_module.SessionLocal() as s:
        out = await assess_baseline(
            s, meta_plate={"fin": "1.0#1"},
            endpoints_used={"fin": ["fin.orders.get"]},
            unanchored_services=["never-registered"],
            review_lookup=_mk({"fin.orders.get": "reviewed"}))
    assert out == (False, "external",
                   {"external_services": [],
                    "unknown_services": ["never-registered"]})
