"""权限域二期 P1:suite 成员层 CRUD/成员管理/反查测试。

《Suite成员层、引用分享与浏览镜头-设计方案》§6.3/§9(P1 子集)。
核心断言面:
- 组合外键安全边界(§6.3 唯一安全设计点):suite 只放属主自己的
  场景,他人场景 → 404,admin 也无豁免;绕过应用层直写也被库约束拒;
- 级联:场景删除 → 成员行自收;suite 删除 → 成员行消失、场景不动;
- 可见性:P1 恒 private,读 = 属主 ∨ admin,非属主 404;
- 上限与命名冲突的 409。
"""
from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select

from app.core import db as db_module
from app.models.suite import Suite, SuiteMember
from tests.helpers import make_draft, register_and_login


async def _mk_scenario(client: AsyncClient, headers: dict, sid: str) -> None:
    r = await client.post("/api/scenarios", headers=headers, json=make_draft(sid))
    assert r.status_code in (200, 201), r.text


async def _mk_suite(client: AsyncClient, headers: dict, name: str) -> int:
    r = await client.post("/api/suites", headers=headers,
                          json={"name": name, "description": ""})
    assert r.status_code == 201, r.text
    return r.json()["suiteId"]


async def test_suite_crud_lifecycle(client: AsyncClient) -> None:
    admin = await register_and_login(client, "su_admin", "su_admin_pass123")
    bob = await register_and_login(client, "su_bob", "su_bob_pass123")

    sid = await _mk_suite(client, bob, "回归集")
    await _mk_scenario(client, bob, "sc-su-a")
    await _mk_scenario(client, bob, "sc-su-b")

    # 批量加入(自己的场景)
    r = await client.post(f"/api/suites/{sid}/members", headers=bob,
                          json={"scenarioIds": ["sc-su-a", "sc-su-b"]})
    assert r.status_code == 200, r.text
    assert r.json()["memberCount"] == 2
    assert [m["scenarioId"] for m in r.json()["members"]] == ["sc-su-a", "sc-su-b"]

    # 详情:属主可读;非属主 404(不泄露);admin 可读(治理)
    r = await client.get(f"/api/suites/{sid}", headers=bob)
    assert r.status_code == 200 and r.json()["name"] == "回归集"
    r = await client.get(f"/api/suites/{sid}", headers=admin)
    assert r.status_code == 200
    carol = await register_and_login(client, "su_carol", "su_carol_pass123")
    assert (await client.get(f"/api/suites/{sid}", headers=carol)
            ).status_code == 404

    # 重命名冲突 → 409;改名成功
    await _mk_suite(client, bob, "冒烟集")
    r = await client.patch(f"/api/suites/{sid}", headers=bob,
                           json={"name": "冒烟集"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "suite_name_conflict"
    r = await client.patch(f"/api/suites/{sid}", headers=bob,
                           json={"name": "回归集-新"})
    assert r.status_code == 200 and r.json()["name"] == "回归集-新"

    # 列表:mine/all;非 admin 的 all ≡ mine(P1 无分享)
    r = await client.get("/api/suites", headers=bob)
    assert {s["name"] for s in r.json()["items"]} == {"回归集-新", "冒烟集"}
    r = await client.get("/api/suites", headers=carol)
    assert r.json()["total"] == 0
    r = await client.get("/api/suites", headers=admin)
    assert r.json()["total"] == 2  # admin all = 全量

    # 排序:整表重排
    r = await client.patch(f"/api/suites/{sid}/members/order", headers=bob,
                           json={"scenarioIds": ["sc-su-b", "sc-su-a"]})
    assert r.status_code == 200
    assert [m["scenarioId"] for m in r.json()["members"]] == ["sc-su-b", "sc-su-a"]
    # 排序清单不全 → 422
    r = await client.patch(f"/api/suites/{sid}/members/order", headers=bob,
                           json={"scenarioIds": ["sc-su-a"]})
    assert r.status_code == 422

    # 移除成员;再删 suite → 场景不受影响
    r = await client.delete(f"/api/suites/{sid}/members/sc-su-a", headers=bob)
    assert r.status_code == 204
    r = await client.delete(f"/api/suites/{sid}", headers=bob)
    assert r.status_code == 204
    assert (await client.get("/api/scenarios/sc-su-a", headers=bob)
            ).status_code == 200


async def test_list_visibility_public(client: AsyncClient) -> None:
    """visibility=public(§5.1,场景列表同款):显式传时 scope 不叠加,
    只出公共 Suite —— 公共库页口径(重构方案 D-3 公共 Suite 分区数据源)。"""
    admin = await register_and_login(client, "vp_admin", "vp_admin_pass123")
    owner = await register_and_login(client, "vp_owner", "vp_owner_pass123")
    bob = await register_and_login(client, "vp_bob", "vp_bob_pass123")

    # owner:发布一个公共 suite(成员场景随发布级联公开)
    await _mk_scenario(client, owner, "sc-vp-1")
    pub = await _mk_suite(client, owner, "公共回归集")
    r = await client.post(f"/api/suites/{pub}/members", headers=owner,
                          json={"scenarioIds": ["sc-vp-1"]})
    assert r.status_code == 200, r.text
    r = await client.post(f"/api/suites/{pub}/publish", headers=owner)
    assert r.status_code == 200, r.text

    # bob 名下有私有 suite:visibility=public 时不得因「自己的」混入
    await _mk_suite(client, bob, "bob 私有集")

    r = await client.get("/api/suites?visibility=public", headers=bob)
    assert r.status_code == 200
    assert {s["name"] for s in r.json()["items"]} == {"公共回归集"}

    # scope 不叠加:同传 mine 仍只出公共(§5.1 显式 visibility 优先)
    r = await client.get("/api/suites?visibility=public&scope=mine",
                         headers=bob)
    assert {s["name"] for s in r.json()["items"]} == {"公共回归集"}

    # admin 同口径
    r = await client.get("/api/suites?visibility=public", headers=admin)
    assert {s["name"] for s in r.json()["items"]} == {"公共回归集"}


async def test_member_cap_409(client: AsyncClient, monkeypatch) -> None:
    """§6.3 SUITE_MEMBER_CAP:超上限批量加入 → 409,已加入的不留半批
    (异常分支 rollback)。cap 压到 3 验证边界(不必真造 100 个场景)。"""
    from app.core.config import settings
    from pytest import MonkeyPatch
    with MonkeyPatch.context() as mp:
        mp.setattr(settings, "SUITE_MEMBER_CAP", 3, raising=False)
        bob = await register_and_login(client, "mc_bob", "mc_bob_pass123")
        for i in range(4):
            await _mk_scenario(client, bob, f"sc-mc-{i}")
        sid = await _mk_suite(client, bob, "上限集")
        # 3 个正好达线
        r = await client.post(f"/api/suites/{sid}/members", headers=bob,
                              json={"scenarioIds": ["sc-mc-0", "sc-mc-1", "sc-mc-2"]})
        assert r.status_code == 200 and r.json()["memberCount"] == 3
        # 第 4 个 → 409;前 3 个保持(本批第 4 个未入库,非整批回滚)
        r = await client.post(f"/api/suites/{sid}/members", headers=bob,
                              json={"scenarioIds": ["sc-mc-3"]})
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "suite_member_cap_exceeded"
        r = await client.get(f"/api/suites/{sid}", headers=bob)
        assert r.json()["memberCount"] == 3


async def test_member_boundary_own_scenarios_only(client: AsyncClient) -> None:
    """安全边界(§6.3):他人场景 → 404;admin 也无豁免;幽灵 → 404。"""
    await register_and_login(client, "mb_admin", "mb_admin_pass123")
    bob = await register_and_login(client, "mb_bob", "mb_bob_pass123")
    await _mk_scenario(client, bob, "sc-mb-bob")

    # admin 建组,试图把 bob 的场景拉进自己的组 → 404(洗内容通道不存在)
    admin = await register_and_login(client, "mb_admin2", "mb_admin2_pass123")
    # mb_admin2 非 admin(bootstrap 被 mb_admin 吃掉)——真正用 admin 会话
    # (mb_admin 是首位注册 = admin)
    admin = await register_and_login(client, "mb_admin", "mb_admin_pass123")
    sid = await _mk_suite(client, admin, "洗白组")
    r = await client.post(f"/api/suites/{sid}/members", headers=admin,
                          json={"scenarioIds": ["sc-mb-bob"]})
    assert r.status_code == 404, r.text

    # 幽灵场景 → 404
    r = await client.post(f"/api/suites/{sid}/members", headers=admin,
                          json={"scenarioIds": ["sc-mb-ghost"]})
    assert r.status_code == 404

    # bob 往 admin 的组里加(非属主写)→ 403
    r = await client.post(f"/api/suites/{sid}/members", headers=bob,
                          json={"scenarioIds": ["sc-mb-bob"]})
    assert r.status_code == 403

    # 库层兜底:绕过应用层直写他人场景 → 约束拒绝。仅 PG 断言
    #(SQLite 测试库不强制 FK —— 仓内既有口径,与 user_stars 的
    # Python 兜底同理由;dev/生产 PG 上组合外键真实生效)。
    if db_module.engine.dialect.name == "postgresql":
        async with db_module.SessionLocal() as s:
            s.add(SuiteMember(suite_id=sid, scenario_id="sc-mb-bob",
                              owner_id=1, sort=0))
            try:
                await s.commit()
                raised = False
            except Exception:
                raised = True
                await s.rollback()
            assert raised, "组合外键必须拒绝跨属主成员行"


async def test_scenario_delete_cascades_membership(client: AsyncClient) -> None:
    """场景删除 → 成员行随 FK CASCADE 自收,suite 保留。"""
    await register_and_login(client, "cas_admin", "cas_admin_pass123")
    bob = await register_and_login(client, "cas_bob", "cas_bob_pass123")
    await _mk_scenario(client, bob, "sc-cas-1")
    await _mk_scenario(client, bob, "sc-cas-2")
    sid = await _mk_suite(client, bob, "级联组")
    r = await client.post(f"/api/suites/{sid}/members", headers=bob,
                          json={"scenarioIds": ["sc-cas-1", "sc-cas-2"]})
    assert r.status_code == 200

    assert (await client.delete("/api/scenarios/sc-cas-1",
                                headers=bob)).status_code in (200, 204)
    r = await client.get(f"/api/suites/{sid}", headers=bob)
    assert [m["scenarioId"] for m in r.json()["members"]] == ["sc-cas-2"]


async def test_scenario_lookup_suites(client: AsyncClient) -> None:
    """反查:GET /api/scenarios/{id}/suites。"""
    await register_and_login(client, "lk_admin", "lk_admin_pass123")
    bob = await register_and_login(client, "lk_bob", "lk_bob_pass123")
    await _mk_scenario(client, bob, "sc-lk-1")
    s1 = await _mk_suite(client, bob, "回归")
    s2 = await _mk_suite(client, bob, "冒烟")
    for s in (s1, s2):
        r = await client.post(f"/api/suites/{s}/members", headers=bob,
                              json={"scenarioIds": ["sc-lk-1"]})
        assert r.status_code == 200

    r = await client.get("/api/scenarios/sc-lk-1/suites", headers=bob)
    assert r.status_code == 200
    assert {x["name"] for x in r.json()} == {"回归", "冒烟"}

    # 非场景属主反查 → 403;幽灵场景 → 404
    carol = await register_and_login(client, "lk_carol", "lk_carol_pass123")
    assert (await client.get("/api/scenarios/sc-lk-1/suites",
                             headers=carol)).status_code == 403
    assert (await client.get("/api/scenarios/sc-lk-ghost/suites",
                             headers=bob)).status_code == 404
