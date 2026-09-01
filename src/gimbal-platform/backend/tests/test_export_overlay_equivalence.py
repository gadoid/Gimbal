"""导出 overlay + 黄金等价(spec §7.3/§8)。

同一场景、同一 overlay 下:preview-plate(带 overlay)产物 ≡ 基线单行
执行 case.json(逐字段相等)。无数据集 → 行 vars 无差异;stepTo/nRuns
不进 case.json → 无需模掉任何字段(spec §7.3 的「模掉行 vars/halt」
在基线单行下自然退化为零差)。

注入清单钉死并集语义(spec §7.3 矩阵:导出侧 = 执行侧):steps 模板
同时引用 qa1/qa2,overlay 只绑 fin-service→qa1 — 两路清单同为
scan(steps)∪ 绑定 = {qa1, qa2},导出产物 users 同时含两个 alias。

断言形状注:preview-plate 现返回 ``PreviewPlateResponse`` 信封
(``{ok, errors, converted}``),产物断言一律取 ``resp.json()["converted"]``
(brief 授权的「以外层包裹为准对齐」适配)。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core import db as db_module
from app.core.security import fernet_encrypt
from app.models import AuthSession, User
from app.services import carry_store

from .helpers import make_draft as _draft, wait_until as _wait
from .test_run_m1_capabilities import _patch_launch_capture, _run_payload
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401
from .test_scenario_visibility_and_copy import _member

OVERLAY = {
    "serviceBindings": {"fin-service": {"authAlias": "qa1", "url": "https://bound"}},
}
# meta 钉死 owner/createTime:两路 fill_plate_defaults 全 setdefault 无增量;
# vars_map={} 显式带上 config.vars — _compose_scenario 恒定写回 vars(空 dict),
# 缺省 draft 无 vars 键会让两路差一个键。
# 其余 ScenarioMeta 全字段一并显式带上:dispatch 侧 convert 输入取自存储
# definition,scenario_store.create 会把 meta 经 ScenarioMeta.model_dump
# 归一化(补 description/author/tags/version/expire/updateTime 缺省);
# draft 侧显式对齐这些缺省值,两路 convert 输入才逐字段一致(非实质
# 差异的测试侧钉死,不改 dispatch/materialize 语义)。
_META = {
    "owner": "bob",
    "createTime": "2026-08-27T00:00:00Z",
    "description": "",
    "author": "",
    "tags": [],
    "version": "v0.1.0",
    "expire": False,
    "updateTime": None,
}
# 模板同时引用 qa1/qa2(overlay 只绑 qa1)— 锁「扫描 ∪ 绑定」并集语义
_STEP = {"kind": "step",
         "api": {"service": "fin-service", "path": "/x",
                 "headers": {"Authorization": "${auth.qa1.token}",
                             "X-Api-Key": "${auth.qa2.token}"}}}


def _eq_draft() -> dict:
    return _draft(steps=[_STEP], vars_map={}, **_META)


# carry 形态 step(spec §4.3):同 _STEP 的 qa1/qa2 headers 并集锚 +
# view_hints.endpoint_id(carry 面)+ request.body(注入载体)。
def _carry_step() -> dict:
    return {"kind": "step",
            "api": {"service": "fin-service", "path": "/x",
                    "headers": {"Authorization": "${auth.qa1.token}",
                                "X-Api-Key": "${auth.qa2.token}"},
                    "view_hints": {"endpoint_id": "fin.ep1"}},
            "request": {"kind": "request", "body": {"order_id": "o-1"}}}


def _eq_draft_with_carry() -> dict:
    """同 _eq_draft 但 step 换成带 carry 锚点的形态。"""
    return _draft(steps=[_carry_step()], vars_map={}, **_META)


async def _seed(client, headers, draft: dict | None = None) -> None:
    r = await client.post("/api/scenarios", headers=headers,
                          json=draft or _eq_draft())
    assert r.status_code in (200, 201), r.text


async def _seed_owner_auth(alias: str, *, bad: bool = False) -> None:
    """给当前 owner(bob)ORM 直插一条 fernet 加密 AuthSession。

    写法对齐 test_run_auth_resolution._seed_owner(fernet_encrypt +
    db_module.SessionLocal);owner_id 从 User 表按 username 查真实 id,
    不假设自增起点。``bad=True`` 插坏密文(fernet 解不开)。
    """
    async with db_module.SessionLocal() as db:
        owner_id = (await db.execute(
            select(User.id).where(User.username == "bob"))).scalar_one()
        db.add(AuthSession(
            owner_id=owner_id,
            alias=alias,
            url=f"https://{alias}-auth/login",
            username_enc=("gitleaks:not-a-fernet-token" if bad
                          else fernet_encrypt(f"{alias}-user")),
            password_enc=("gitleaks:not-a-fernet-token" if bad
                          else fernet_encrypt(f"{alias}-pass")),
        ))
        await db.commit()


async def test_preview_plate_without_overlay_no_credentials(
        client, plate_mock: PlateMock):
    """默认导出(无 overlay):凭证/服务绑定零注入(向后兼容)。

    carry 物化已无条件化(spec §4.3 勘误)— 凭证与绑定注入仍以
    overlay 为唯一开关,本用例钉住这条边界:无 overlay 时 services
    不落绑定 url、users 不落扫描到的 alias。
    """
    plate_mock.behaviour = "echo"
    bob = await _member(client, "bob")
    await _seed(client, bob)
    resp = await client.post("/api/scenarios/preview-plate", headers=bob,
                             json=_eq_draft())
    assert resp.status_code == 200, resp.text
    converted = resp.json()["converted"]
    services = (converted.get("config") or {}).get("services") or {}
    assert services.get("fin-service") != "https://bound"
    # 凭证零注入:模板引用 qa1/qa2,无 overlay 时 users 不含两 alias
    users = converted["config"].get("users") or {}
    assert "qa1" not in users and "qa2" not in users


async def test_preview_plate_without_overlay_materializes_carry(
        client, plate_mock: PlateMock):
    """默认导出(无 overlay)也走 carry 物化(spec §4.3 勘误)。

    与按方案导出同源:服务绑定 + 全局默认注入 body;凭证仍零注入。
    修复背景(2026-09-01):carry 物化原仅在 overlay 分支,默认导出
    (JSON/YAML/执行页快照)不注入 → 与执行产物系统性漂移。
    """
    plate_mock.behaviour = "echo"
    plate_mock.services = [{"name": "fin-service"}]
    plate_mock.fulls = {"fin.ep1": {"request": {"carry": {
        "$.remark": {"type": "string"},
        "$.appCode": {"type": "string"}}}}}
    async with db_module.SessionLocal() as db:
        await carry_store.put_bindings(
            db, "fin-service", {"$.remark": "压测-张三"}, "bob")
        await carry_store.put_defaults(db, {"$.appCode": "TRACE-V2"}, "bob")
        await db.commit()

    bob = await _member(client, "bob")
    await _seed(client, bob, draft=_eq_draft_with_carry())

    resp = await client.post("/api/scenarios/preview-plate", headers=bob,
                             json=_eq_draft_with_carry())
    assert resp.status_code == 200, resp.text
    converted = resp.json()["converted"]
    body = converted["steps"][0]["request"]["body"]
    assert body["remark"] == "压测-张三"
    assert body["appCode"] == "TRACE-V2"
    # 凭证/服务绑定零注入(carry 无条件,凭证仅 overlay)
    services = (converted.get("config") or {}).get("services") or {}
    assert services.get("fin-service") != "https://bound"
    users = converted["config"].get("users") or {}
    assert "qa1" not in users and "qa2" not in users


async def test_preview_plate_with_overlay_materializes(client, plate_mock: PlateMock):
    plate_mock.behaviour = "echo"
    bob = await _member(client, "bob")
    await _seed(client, bob)
    resp = await client.post("/api/scenarios/preview-plate", headers=bob,
                             json={**_eq_draft(), "overlay": OVERLAY})
    assert resp.status_code == 200, resp.text
    converted = resp.json()["converted"]
    assert converted["config"]["services"]["fin-service"] == "https://bound"
    # qa1/qa2 无凭证池会话 → 告警继续,users 不含两 alias(与 dispatch 同语义)
    users = converted["config"].get("users") or {}
    assert "qa1" not in users and "qa2" not in users


async def test_preview_plate_overlay_auth_resolve_failure_returns_422(
        client, plate_mock: PlateMock):
    """凭证池密文损坏 → 422 auth_resolve_failed(fail-fast,不再 500)。"""
    plate_mock.behaviour = "echo"
    bob = await _member(client, "bob")
    await _seed(client, bob)
    await _seed_owner_auth("qa1", bad=True)  # 绑定 qa1 触发解析

    resp = await client.post("/api/scenarios/preview-plate", headers=bob,
                             json={**_eq_draft(), "overlay": OVERLAY})
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["code"] == "auth_resolve_failed"


async def test_golden_equivalence_export_equals_baseline_case_json(
        client, plate_mock: PlateMock, monkeypatch):
    """黄金等价:导出产物 ≡ 基线单行 case.json,逐字段相等。

    注入清单并集语义:steps 模板引用 qa1+qa2,overlay 只绑 qa1 —
    导出产物 users 须同时含 qa1/qa2(扫描 ∪ 绑定);dispatch 侧扫描
    同源 steps,两路收敛,等价逐字段成立。
    """
    plate_mock.behaviour = "echo"
    bob = await _member(client, "bob")
    await _seed(client, bob)
    await _seed_owner_auth("qa1")
    await _seed_owner_auth("qa2")

    exported = (await client.post(
        "/api/scenarios/preview-plate", headers=bob,
        json={**_eq_draft(), "overlay": OVERLAY})).json()["converted"]

    # 并集:qa1(绑定 + 模板)与 qa2(仅模板)都注入,凭证来自同一凭证池
    assert set(exported["config"]["users"]) == {"qa1", "qa2"}
    assert exported["config"]["users"]["qa2"]["username"] == "qa2-user"

    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    r = await client.post("/api/runs", headers=bob, json=_run_payload(
        dataSetIds=[], serviceBindings=OVERLAY["serviceBindings"]))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)

    assert cases[0] == exported


# ─── carry 黄金等价(spec §4.3)────────────────────────────────────
async def test_golden_equivalence_with_carry(
        client, plate_mock: PlateMock, monkeypatch):
    """carry 物化同源:导出产物 ≡ 基线单行 case.json,含注入后的 carry 值。

    导出链与 dispatch 共用 build_carry_context(快照语义:导出产物 =
    绑定状态的当时快照)— face(锚点)+ 服务绑定 + 全局默认三层,
    两路物化逐字段相等。
    """
    plate_mock.behaviour = "echo"
    plate_mock.services = [{"name": "fin-service"}]
    plate_mock.fulls = {"fin.ep1": {"request": {"carry": {
        "$.remark": {"type": "string"},
        "$.appCode": {"type": "string"}}}}}
    async with db_module.SessionLocal() as db:
        await carry_store.put_bindings(
            db, "fin-service", {"$.remark": "压测-张三"}, "bob")
        await carry_store.put_defaults(db, {"$.appCode": "TRACE-V2"}, "bob")
        await db.commit()

    bob = await _member(client, "bob")
    await _seed(client, bob, draft=_eq_draft_with_carry())
    await _seed_owner_auth("qa1")
    await _seed_owner_auth("qa2")

    exported = (await client.post(
        "/api/scenarios/preview-plate", headers=bob,
        json={**_eq_draft_with_carry(), "overlay": OVERLAY})).json()["converted"]
    body = exported["steps"][0]["request"]["body"]
    assert body["remark"] == "压测-张三"
    assert body["appCode"] == "TRACE-V2"

    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    r = await client.post("/api/runs", headers=bob, json=_run_payload(
        dataSetIds=[], serviceBindings=OVERLAY["serviceBindings"]))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)

    assert cases[0] == exported
