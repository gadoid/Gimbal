"""执行链 carry 注入 E2E(spec §4)— dispatch 预解析 + materialize 填充。

锁两条边界:
  1. dispatch 阶段 build_carry_context 预解析(plate carry 面 + 两张值表),
     materialize_run_copy 把服务绑定/全局默认填进 body(填缺失语义);
  2. plate face 拉不到(/full 404)→ 无锚点候选,降级到「绑定 ∪ 全局默认」
     键集仍可注入 — carry 永不阻塞执行。

brief 测试草稿对仓库真实形状的适配(草稿 vs 现行 helper 契约):
  * 场景创建用 ``make_draft(steps=[...])`` — 草稿的裸
    ``{"definition": {"steps": ...}, "orchestration": {}}`` 缺 meta 必填
    (name/module/system...),scenario_store.create 的 ScenarioMeta 校验会 422;
  * run payload 用 ``_run_payload(dataSetIds=[])`` — 草稿未建数据集而
    ``_run_payload()`` 默认引用 ds-001 → 404;空列表 = D12 基线单行
    (与 test_export_overlay_equivalence 的 run E2E 同款写法);
  * ``wait_until`` 顶部统一导入(草稿在函数内 from .helpers import)。
"""
from __future__ import annotations

from httpx import AsyncClient
from pytest import MonkeyPatch

from app.core import db as db_module
from app.services import carry_store

from .helpers import make_draft as _draft, wait_until as _wait
from .test_run_m1_capabilities import _patch_launch_capture, _run_payload
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401
from .test_scenario_visibility_and_copy import _member


def _carry_step() -> dict:
    return {"kind": "step",
            "api": {"service": "fin-service", "path": "/x",
                    "view_hints": {"endpoint_id": "fin.settlement.create_order"}},
            "request": {"kind": "request", "body": {"order_id": "o-1"}}}


async def _seed_values() -> None:
    """ORM 直插两张值表(updated_by 只是审计串,读侧无 owner 过滤)。"""
    async with db_module.SessionLocal() as db:
        await carry_store.put_bindings(
            db, "fin-service", {"$.remark": "压测-张三"}, "alice")
        await carry_store.put_defaults(db, {"$.appCode": "TRACE-V2"}, "alice")
        await db.commit()


async def _create_scenario(client: AsyncClient, bob: dict) -> None:
    r = await client.post(
        "/api/scenarios", headers=bob, json=_draft(steps=[_carry_step()]))
    assert r.status_code in (200, 201), r.text


async def test_run_injects_carry_into_case_body(
    client: AsyncClient, plate_mock: PlateMock, monkeypatch: MonkeyPatch
) -> None:
    """锚点 face + 服务绑定 + 全局默认 → body 三层合入(body 原值不动)。"""
    plate_mock.behaviour = "echo"
    plate_mock.services = [{"name": "fin-service"}]
    plate_mock.fulls = {
        "fin.settlement.create_order": {"request": {"carry": {
            "$.remark": {"type": "string"},
            "$.appCode": {"type": "string"}}}},
    }
    await _seed_values()
    bob = await _member(client, "bob")
    await _create_scenario(client, bob)

    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    r = await client.post("/api/runs", headers=bob,
                          json=_run_payload(dataSetIds=[]))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)

    body = cases[0]["steps"][0]["request"]["body"]
    assert body["remark"] == "压测-张三"   # 服务绑定
    assert body["appCode"] == "TRACE-V2"   # 全局默认
    assert body["order_id"] == "o-1"       # body 原值不动


async def test_run_carry_degrades_when_plate_face_unavailable(
    client: AsyncClient, plate_mock: PlateMock, monkeypatch: MonkeyPatch
) -> None:
    """face 拉不到 → 无锚点候选(绑定∪默认),仍可注入;不阻塞执行。"""
    plate_mock.behaviour = "echo"
    plate_mock.services = [{"name": "fin-service"}]  # 无 fulls → face 空
    await _seed_values()
    bob = await _member(client, "bob")
    await _create_scenario(client, bob)

    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    r = await client.post("/api/runs", headers=bob,
                          json=_run_payload(dataSetIds=[]))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)

    body = cases[0]["steps"][0]["request"]["body"]
    assert body["remark"] == "压测-张三"


async def test_run_carry_skips_step_when_service_not_in_catalog(
        client: AsyncClient, plate_mock: PlateMock, monkeypatch: MonkeyPatch
) -> None:
    """裸声明:服务不在 plate 目录 → derive_base 失败 → 该 step 跳过
    carry 填充(无注入、无报错),run 正常完成(T9 评审补的边界)。"""
    plate_mock.behaviour = "echo"
    plate_mock.services = []  # 空目录 → fin-service 是裸声明
    plate_mock.fulls = {  # face 有锚点也无效:服务解析失败先短路
        "fin.settlement.create_order": {"request": {"carry": {
            "$.remark": {"type": "string"},
            "$.appCode": {"type": "string"}}}},
    }
    await _seed_values()
    bob = await _member(client, "bob")
    await _create_scenario(client, bob)

    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    r = await client.post("/api/runs", headers=bob,
                          json=_run_payload(dataSetIds=[]))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)

    # step 被整步跳过:body 只有原值,无任何 carry 注入痕迹
    assert cases[0]["steps"][0]["request"]["body"] == {"order_id": "o-1"}


async def test_run_completes_when_carry_context_build_fails(
        client: AsyncClient, plate_mock: PlateMock, monkeypatch: MonkeyPatch
) -> None:
    """build_carry_context 在 dispatcher 层抛异常 → 降级 carry_ctx=None,
    run 仍完成、case 正常产出(无注入)— carry 是增强不是前置条件
    (T9 评审补的边界)。"""
    plate_mock.behaviour = "echo"
    plate_mock.services = [{"name": "fin-service"}]
    plate_mock.fulls = {
        "fin.settlement.create_order": {"request": {"carry": {
            "$.remark": {"type": "string"},
            "$.appCode": {"type": "string"}}}},
    }
    await _seed_values()

    async def _boom(db, definition):
        raise RuntimeError("carry boom")

    # _fanout 内是函数级 import(from .carry_injection import ...)—
    # 打模块属性,调用时才解析,monkeypatch 生效。
    monkeypatch.setattr(
        "app.services.carry_injection.build_carry_context", _boom)

    bob = await _member(client, "bob")
    await _create_scenario(client, bob)

    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    r = await client.post("/api/runs", headers=bob,
                          json=_run_payload(dataSetIds=[]))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)

    # 无 carry 注入,body 原值;case 已产出(执行链未受影响)
    assert cases[0]["steps"][0]["request"]["body"] == {"order_id": "o-1"}
