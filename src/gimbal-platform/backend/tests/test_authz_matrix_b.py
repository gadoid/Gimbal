"""表 B 矩阵(authz W3 起,M2a S1.1 扩项目维度):对象 × 动词 × 主体 × 区。

三层:
1. 快照对拍 —— TABLE_B 与 authz_expected.yaml 的 table_b 段逐格
   一致(表改了没改快照即红;与 matrix_a 的 R7 门同构)。
2. 谓词矩阵 —— can_pure() 在主体(属主 / 路人 / admin / super_admin /
   项目成员 / 项目管理员 / 移出项目的创建人)× 区(私有 / 普通项目 /
   公共项目)上的结果由快照谓词推导,不是由实现反推(自证循环防线)。
   data_set/run_scheme 的读谓词随父场景(行上无 project_id),
   只矩阵化 write 面。
3. 端点验收(impl W3 / S1.1)—— admin/super_admin 操作他人私有对象
   一律 404 且无通知;Admin+ 唯一越属主动词 = 下架公共项目对象
   (public_admin,R6:无发布权;报告定义下架同口径)。
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from httpx import AsyncClient

_EXPECTED = yaml.safe_load(
    Path(__file__).with_name("authz_expected.yaml").read_text(encoding="utf-8"))

# 谓词缩写(快照)→ 语义(S1.1 项目维度)
_ABBR = {
    "o": "owner", "ref": "ref", "mem": "member", "pad": "padmin",
    "mnt": "maintainer", "pr": "public_reader", "pa": "public_admin",
}


def test_table_b_matches_reviewed_snapshot():
    """表 B 与人工快照对拍(独立于求值器,防改表漏改快照)。"""
    from app.routers._ownership import TABLE_B

    snap = _EXPECTED["table_b"]
    assert set(TABLE_B) == set(snap), "对象类型集漂移"
    for obj_type, verbs in snap.items():
        assert set(TABLE_B[obj_type]) == set(verbs), obj_type
        for verb, abbrs in verbs.items():
            assert TABLE_B[obj_type][verb] == frozenset(
                _ABBR[a] for a in abbrs), f"{obj_type}.{verb}"


# ── 谓词矩阵(期望从快照推导;ref 谓词不在 can_pure 面,矩阵恒 False)──
_CAPS = {  # 表 A 的快照(能力面只取矩阵需要的一个)
    "user": set(), "admin": {"ops.write"},
    "super_admin": {"ops.write", "users.manage"},
}

# 区常量:普通项目 P=500(成员 uid 3/4),公共项目 PUBLIC=900
_P, _PUBLIC = 500, 900

# 主体:(role, uid, memberships) —— memberships: {project_id: 角色}
# 「移出项目的创建人」= uid 1(普通项目对象 owner_id=1)∧ memberships
# 空 —— D1 的关键回归形态:创建人身份在项目里不给任何谓词
_SUBJECTS = [
    ("user", 1, {}, "owner(私有属主/项目创建人)"),
    ("user", 2, {}, "other-user(路人)"),
    ("admin", 2, {}, "admin"),
    ("super_admin", 2, {}, "super_admin"),
    ("user", 3, {_P: "member"}, "member(项目成员)"),
    ("user", 4, {_P: "admin"}, "padmin(项目管理员)"),
]


def _expected_from_snapshot(preds, *, uid, role, memberships, obj):
    """由快照谓词推导期望(ref 恒 False;区互斥,按对象 project_id 判)。"""
    zone = getattr(obj, "project_id", None)
    for abbr in preds:
        if abbr == "o" and zone is None and uid == obj.owner_id:
            return True
        if abbr == "mem" and zone == _P and _P in memberships:
            return True
        if abbr == "pad" and zone == _P \
                and memberships.get(_P) == "admin":
            return True
        if abbr == "mnt" and zone == _PUBLIC and uid == obj.owner_id:
            return True
        if abbr == "pr" and zone == _PUBLIC:
            return True
        if abbr == "pa" and zone == _PUBLIC \
                and "ops.write" in _CAPS[role]:
            return True
    return False


def _matrix_cases():
    """(obj_type, verb, role, uid, memberships, 对象) 全叉积。"""
    from app.routers._ownership import TABLE_B

    cases = []
    for obj_type, verbs in TABLE_B.items():
        for verb in verbs:
            if obj_type in ("data_set", "run_scheme") and verb != "write":
                continue  # 读/执行随父场景判定(can_read_scenario_row)
            for role, uid, mem, _label in _SUBJECTS:
                if obj_type == "report_definition":
                    states = [  # (对象, 说明)
                        (SimpleNamespace(owner_id=1, project_id=None),
                         "私有"),
                        (SimpleNamespace(owner_id=1, project_id=_P),
                         "普通项目"),
                        (SimpleNamespace(owner_id=1, project_id=_PUBLIC),
                         "公共"),
                        (SimpleNamespace(owner_id=None, project_id=_PUBLIC),
                         "遗留无主公共(0037)"),
                    ]
                else:
                    states = [
                        (SimpleNamespace(owner_id=1, project_id=None),
                         "私有"),
                        (SimpleNamespace(owner_id=1, project_id=_P),
                         "普通项目"),
                        (SimpleNamespace(owner_id=1, project_id=_PUBLIC),
                         "公共"),
                    ]
                for obj, state_label in states:
                    exp = _expected_from_snapshot(
                        _EXPECTED["table_b"][obj_type][verb],
                        uid=uid, role=role, memberships=mem, obj=obj)
                    cases.append(pytest.param(
                        obj_type, verb, role, uid, mem, obj, exp,
                        id=f"{obj_type}.{verb}[{role}:{state_label}]"))
    return cases


@pytest.mark.parametrize(
    "obj_type,verb,role,uid,memberships,obj,expected", _matrix_cases())
def test_can_pure_matrix(obj_type, verb, role, uid, memberships, obj,
                         expected):
    """can_pure 与快照推导逐格对拍(公共项目 id 与项目角色表以上下文
    注入 —— 同 can() 的运行时做法;ref 谓词由端点层覆盖)。"""
    from app.routers._ownership import can_pure

    user = SimpleNamespace(role=role, id=uid)
    assert can_pure(user, obj_type, verb, obj,
                    public_project_id=_PUBLIC,
                    project_roles=memberships) is expected


def test_can_pure_without_zone_context_fails_closed():
    """不注入上下文时公共/项目谓词恒 False(fail-closed,影子期快路径
    的语义:无 project_roles 传入即按「无项目」收口)。"""
    from app.routers._ownership import can_pure

    user = SimpleNamespace(role="admin", id=2)
    pub = SimpleNamespace(owner_id=1, project_id=_PUBLIC)
    assert can_pure(user, "scenario", "read", pub) is False
    proj = SimpleNamespace(owner_id=1, project_id=_P)
    assert can_pure(user, "scenario", "write", proj) is False


def test_can_pure_unknown_object_or_verb_raises():
    """未登记格子是编码错误,即刻暴露(与 roles_with 同口径)。"""
    from app.routers._ownership import can_pure

    with pytest.raises(KeyError):
        can_pure(SimpleNamespace(role="user", id=1),
                 "scenario", "explode", SimpleNamespace(owner_id=1))
    with pytest.raises(KeyError):
        can_pure(SimpleNamespace(role="user", id=1),
                 "spaceship", "read", SimpleNamespace(owner_id=1))


# ── 端点验收(impl W3):私有区一律 404,steward 只剩公共下架 ─────────
async def _mk_scenario(client: AsyncClient, h, sid: str) -> None:
    from tests.helpers import make_draft

    r = await client.post("/api/scenarios", headers=h,
                          json=make_draft(sid))
    assert r.status_code in (200, 201), r.text
    # PUT 校验先于闸(pydantic 422),测闸必须带完整合法 draft
    _mk_scenario.draft = make_draft(sid)


class TestScenarioPrivateNarrowed:
    async def test_admin_and_super_admin_get_404_on_others_private(
            self, client: AsyncClient):
        from tests.helpers import role_headers

        h_owner = await role_headers(client, "mb_own")
        await _mk_scenario(client, h_owner, "sc-mb-1")
        for role in ("admin", "super_admin"):
            h = await role_headers(client, f"mb_{role}", role=role)
            # 读 / 写 / 删 / 发布 / 下架:他人私有对象一律 404
            assert (await client.get(
                "/api/scenarios/sc-mb-1", headers=h)).status_code == 404, role
            assert (await client.put(
                "/api/scenarios/sc-mb-1", headers=h,
                json=_mk_scenario.draft)).status_code == 404, role
            assert (await client.post(
                "/api/scenarios/sc-mb-1/publish",
                headers=h)).status_code == 404, role
            assert (await client.post(
                "/api/scenarios/sc-mb-1/unpublish",
                headers=h)).status_code == 404, role
            assert (await client.delete(
                "/api/scenarios/sc-mb-1", headers=h)).status_code == 404, role

    async def test_admin_cannot_delete_others_private_scenario(
            self, client: AsyncClient):
        from tests.helpers import role_headers

        h_owner = await role_headers(client, "mb_dow")
        await _mk_scenario(client, h_owner, "sc-mb-d")
        h = await role_headers(client, "mb_dadm", role="super_admin")
        r = await client.delete("/api/scenarios/sc-mb-d", headers=h)
        assert r.status_code == 404, r.text
        # 对象还在(属主视角可读)
        assert (await client.get(
            "/api/scenarios/sc-mb-d", headers=h_owner)).status_code == 200


class TestStewardUnpublish:
    async def test_admin_unpublish_others_public_audits_and_notifies(
            self, client: AsyncClient):
        from sqlalchemy import select

        from app.core import db as db_module
        from app.models.permission import AuditLog, Notification
        from app.models.user import User
        from tests.helpers import role_headers

        h_owner = await role_headers(client, "mb_upown")
        await _mk_scenario(client, h_owner, "sc-mb-up")
        assert (await client.post(
            "/api/scenarios/sc-mb-up/publish",
            headers=h_owner)).status_code == 200
        async with db_module.SessionLocal() as db:
            owner_id = (await db.execute(
                select(User.id).where(
                    User.username == "mb_upown"))).scalar_one()

        # S1.3:发布 = 复制 —— Admin+ 的治理下架作用在**公共副本**上
        # (原件恒私有,admin 不可见);回包 = 原件的读形态(private)
        h_admin = await role_headers(client, "mb_upadm", role="admin")
        r = await client.post(
            "/api/scenarios/sc-mb-up-public/unpublish", headers=h_admin)
        assert r.status_code == 200, r.text
        assert r.json()["visibility"] == "private"
        from app.models.composer_scenario import ComposerScenario as _CS

        async with db_module.SessionLocal() as db:
            assert (await db.execute(select(_CS.scenario_id).where(
                _CS.scenario_id == "sc-mb-up-public"))).scalar_one_or_none() \
                is None, "公共副本应已删除"
            assert (await db.execute(select(_CS.scenario_id).where(
                _CS.scenario_id == "sc-mb-up"))).scalar_one() == "sc-mb-up", \
                "原件保留"
        async with db_module.SessionLocal() as db:
            audits = (await db.execute(select(AuditLog).where(
                AuditLog.action == "scenario.admin_unpublish"))).scalars().all()
            assert len(audits) == 1
            notes = (await db.execute(select(Notification).where(
                Notification.user_id == owner_id,
                Notification.type == "scenario_unpublished"))).scalars().all()
            assert len(notes) == 1  # :736 收口:越属主下架 → 属主被通知

    async def test_admin_unpublish_others_private_404_and_no_notification(
            self, client: AsyncClient):
        from sqlalchemy import select

        from app.core import db as db_module
        from app.models.permission import Notification
        from app.models.user import User
        from tests.helpers import role_headers

        h_owner = await role_headers(client, "mb_pvown")
        await _mk_scenario(client, h_owner, "sc-mb-pv")
        async with db_module.SessionLocal() as db:
            owner_id = (await db.execute(
                select(User.id).where(
                    User.username == "mb_pvown"))).scalar_one()
        h_admin = await role_headers(client, "mb_pvadm", role="super_admin")
        for verb in ("publish", "unpublish"):
            r = await client.post(
                f"/api/scenarios/sc-mb-pv/{verb}", headers=h_admin)
            assert r.status_code == 404, (verb, r.text)
        async with db_module.SessionLocal() as db:
            notes = (await db.execute(select(Notification).where(
                Notification.user_id == owner_id))).scalars().all()
        assert not notes  # 钉 :736 收口:私有对象被拒时无任何通知

    async def test_admin_publish_others_public_forbidden(self, client):
        """:736 同闸的另一半(R6):公共对象上 admin 再「发布」可读但
        无权(403),不再是隐式放行的空操作 200。"""
        from tests.helpers import role_headers

        h_owner = await role_headers(client, "mb_puown")
        await _mk_scenario(client, h_owner, "sc-mb-pu")
        assert (await client.post(
            "/api/scenarios/sc-mb-pu/publish", headers=h_owner)).status_code == 200
        # S1.3:发布 = 复制后,原件恒私有 —— admin 对他人私有原件不可见
        # (读闸 404;R6 精神不变:admin 无发布权,不再是隐式空操作)
        h_admin = await role_headers(client, "mb_puadm", role="super_admin")
        r = await client.post("/api/scenarios/sc-mb-pu/publish", headers=h_admin)
        assert r.status_code == 404, r.text


class TestSuiteNarrowed:
    async def _mk_suite(self, client, h_owner) -> int:
        from tests.helpers import make_draft

        await _mk_scenario(client, h_owner, "sc-mb-su")
        r = await client.post("/api/suites", headers=h_owner,
                              json={"name": "mb-suite", "description": ""})
        assert r.status_code == 201, r.text
        sid = r.json()["suiteId"]
        r = await client.post(f"/api/suites/{sid}/members", headers=h_owner,
                              json={"scenarioIds": ["sc-mb-su"],
                                    "publishUnpublished": False})
        assert r.status_code == 200, r.text
        return sid

    async def test_admin_others_private_suite_404_across_verbs(
            self, client: AsyncClient):
        from tests.helpers import role_headers

        h_owner = await role_headers(client, "mb_sown")
        suite_id = await self._mk_suite(client, h_owner)
        h = await role_headers(client, "mb_sadm", role="super_admin")
        assert (await client.get(
            f"/api/suites/{suite_id}", headers=h)).status_code == 404
        assert (await client.patch(
            f"/api/suites/{suite_id}", headers=h,
            json={"name": "x"})).status_code == 404
        assert (await client.post(
            f"/api/suites/{suite_id}/publish", headers=h)).status_code == 404
        assert (await client.delete(
            f"/api/suites/{suite_id}", headers=h)).status_code == 404

    async def test_steward_unpublish_public_suite_notifies_and_audits(
            self, client: AsyncClient):
        from sqlalchemy import select

        from app.core import db as db_module
        from app.models.permission import AuditLog, Notification
        from app.models.user import User
        from tests.helpers import role_headers

        h_owner = await role_headers(client, "mb_supown")
        suite_id = await self._mk_suite(client, h_owner)
        # S1.3:先发布成员场景(套件深拷贝的前置),套件发布回包 = 公共副本
        assert (await client.post(
            "/api/scenarios/sc-mb-su/publish",
            headers=h_owner)).status_code == 200
        r = await client.post(
            f"/api/suites/{suite_id}/publish", headers=h_owner)
        assert r.status_code == 200, r.text
        copy_suite_id = r.json()["suiteId"]
        assert copy_suite_id != suite_id
        async with db_module.SessionLocal() as db:
            owner_id = (await db.execute(
                select(User.id).where(
                    User.username == "mb_supown"))).scalar_one()

        # Admin+ 治理下架作用在公共副本上;回包 = 原件 summary(private)
        h_admin = await role_headers(client, "mb_supadm", role="admin")
        r = await client.delete(
            f"/api/suites/{copy_suite_id}/publish", headers=h_admin)
        assert r.status_code == 200, r.text
        assert r.json()["visibility"] == "private"
        async with db_module.SessionLocal() as db:
            assert len((await db.execute(select(AuditLog).where(
                AuditLog.action == "suite.admin_unpublish")))
                .scalars().all()) == 1
            assert len((await db.execute(select(Notification).where(
                Notification.user_id == owner_id,
                Notification.type == "scenario_unpublished")))
                .scalars().all()) == 1

    async def test_admin_unpublish_private_suite_404(self, client):
        from tests.helpers import role_headers

        h_owner = await role_headers(client, "mb_spvown")
        suite_id = await self._mk_suite(client, h_owner)
        h = await role_headers(client, "mb_spvadm", role="super_admin")
        r = await client.delete(f"/api/suites/{suite_id}/publish", headers=h)
        assert r.status_code == 404, r.text


class TestReportDefinitionMaintain:
    """authz W9-2:公共定义建维护者 —— 编辑 = 维护者单判,Admin+ 仅下架。"""

    async def _mk_definition(self, client, *, public: bool,
                             owner_id: int | None) -> int:
        from app.core import db as db_module
        from app.models.report_definition import ReportDefinitionRow
        from app.services.zone import public_project_id

        async with db_module.SessionLocal() as db:
            row = ReportDefinitionRow(
                name="mb-pub-def", description="",
                definition={"selection": {}, "projection": []},
                owner_id=owner_id,
                # S1.9:公共 = 挂公共项目(visibility 列已删)
                project_id=await public_project_id(db) if public else None)
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return row.id

    async def test_public_definition_owner_is_maintainer(
            self, client: AsyncClient):
        """新建公共定义:owner = 创建者(公共 ≠ 无主),isPublic=True。"""
        from sqlalchemy import select as sa_select

        from app.core import db as db_module
        from app.models.report_definition import ReportDefinitionRow
        from app.services.zone import public_project_id
        from tests.helpers import role_headers

        h = await role_headers(client, "mb_rdown")
        r = await client.post("/api/report-definitions", headers=h, json={
            "name": "mb-new-pub", "description": "",
            "selection": {}, "projection": {}, "public": True})
        assert r.status_code in (200, 201), r.text
        did = r.json()["id"]
        out = r.json()
        assert out["isPublic"] is True and out["ownerId"] is not None
        async with db_module.SessionLocal() as db:
            row = (await db.execute(sa_select(ReportDefinitionRow).where(
                ReportDefinitionRow.id == did))).scalar_one()
            assert row.owner_id is not None      # 公共定义必有维护者
            assert row.project_id == await public_project_id(db)

    async def test_only_maintainer_edits_public_definition(
            self, client: AsyncClient):
        """编辑权 = 维护者:admin 与 super_admin 都不能改他人维护的
        公共定义(W9-2 起编辑 = 维护者单判);维护者本人 200。"""
        from tests.helpers import role_headers

        h_owner = await role_headers(client, "mb_rdmt")
        uid = 1  # 由 role_headers 直插;真实 id 从 roster 取
        from sqlalchemy import select as sa_select

        from app.core import db as db_module
        from app.models.user import User

        async with db_module.SessionLocal() as db:
            uid = (await db.execute(sa_select(User.id).where(
                User.username == "mb_rdmt"))).scalar_one()
        did = await self._mk_definition(
            client, public=True, owner_id=uid)

        for role, name in (("admin", "mb_rdadm"), ("super_admin", "mb_rdsup")):
            h = await role_headers(client, name, role=role)
            r = await client.put(f"/api/report-definitions/{did}", headers=h,
                                 json={"name": "stolen"})
            assert r.status_code == 404, (role, r.text)

        r = await client.put(f"/api/report-definitions/{did}", headers=h_owner,
                             json={"name": "maintainer-ok"})
        assert r.status_code == 200, r.text

        # 下架(steward = ops.write ∧ 公共,与场景/suite 同口径):
        # 普通用户 404;admin 204
        h = await role_headers(client, "mb_rdusr2", role="user")
        r = await client.delete(f"/api/report-definitions/{did}", headers=h)
        assert r.status_code == 404, r.text
        h2 = await role_headers(client, "mb_rdadm2", role="admin")
        r = await client.delete(f"/api/report-definitions/{did}", headers=h2)
        assert r.status_code == 204, r.text

    async def test_legacy_ownerless_public_rows(
            self, client: AsyncClient):
        """遗留无主公共行(0037 回填 visibility=public,owner 保持 NULL):
        全员可读、编辑面冻结(无人是维护者)、Admin+ 可下架。"""
        from tests.helpers import role_headers

        did = await self._mk_definition(
            client, public=True, owner_id=None)
        h = await role_headers(client, "mb_rdtype", role="user")
        r = await client.get(f"/api/report-definitions/{did}", headers=h)
        assert r.status_code == 200, r.text

        h2 = await role_headers(client, "mb_rdsup3", role="super_admin")
        r = await client.put(f"/api/report-definitions/{did}", headers=h2,
                             json={"name": "frozen"})
        assert r.status_code == 404, r.text     # 编辑冻结(写 = owner 单判)
        r = await client.delete(f"/api/report-definitions/{did}", headers=h2)
        assert r.status_code == 204, r.text     # 下架面(steward)
