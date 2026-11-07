"""表 B 矩阵(authz W3,方案 §2.3):对象 × 动词 × 主体。

三层:
1. 快照对拍 —— TABLE_B 与 authz_expected.yaml 的 table_b 段逐格
   一致(表改了没改快照即红;与 matrix_a 的 R7 门同构)。
2. 谓词矩阵 —— can_pure() 在(owner / 他人 user / admin / super_admin)
   × (private / public)上的结果由快照谓词推导,不是由实现反推
   (自证循环防线)。data_set/run_scheme 的 public 谓词随父场景
   (行上无 visibility),只矩阵化 write 面。
3. 端点验收(impl W3)—— admin/super_admin 操作他人私有对象一律
   404 且无通知;Admin+ 唯一越属主动词 = 下架公共对象(steward,
   R6:无发布权);report_definition 的 maintain 面 = super_admin。
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from httpx import AsyncClient

_EXPECTED = yaml.safe_load(
    Path(__file__).with_name("authz_expected.yaml").read_text(encoding="utf-8"))

# 谓词缩写(快照)→ 语义
_ABBR = {
    "o": "owner", "pub": "public", "ref": "ref",
    "ste": "steward", "mnt": "maintain",
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
_CAPS = {  # 表 A 的快照(能力面只取矩阵需要的两个)
    "user": set(), "admin": {"ops.write"}, "super_admin": {"ops.write", "users.manage"},
}


def _expected_from_snapshot(preds, *, is_owner, is_public, role):
    for abbr in preds:
        if abbr == "o" and is_owner:
            return True
        if abbr == "pub" and is_public:
            return True
        if abbr == "ste" and is_public and "ops.write" in _CAPS[role]:
            return True
        if abbr == "mnt" and is_public and "users.manage" in _CAPS[role]:
            return True
    return False


_OWNER_ID = 1          # 属主固定 uid=1;其余主体 uid=2
_SUBJECTS = [          # (role, uid, 说明)
    ("user", _OWNER_ID, "owner-user"),
    ("user", 2, "other-user"),
    ("admin", 2, "admin"),
    ("super_admin", 2, "super_admin"),
]


def _matrix_cases():
    """(obj_type, verb, role, uid, 对象) 全叉积;期望由快照推导。"""
    from app.routers._ownership import TABLE_B

    cases = []
    for obj_type, verbs in TABLE_B.items():
        for verb in verbs:
            if obj_type in ("data_set", "run_scheme") and verb != "write":
                continue  # 读/执行随父场景判定(can_read_scenario_row)
            for role, uid, _label in _SUBJECTS:
                if obj_type == "report_definition":
                    # authz W9-2:公共态 = visibility(公共定义带维护者);
                    # 遗留无主公共行(owner NULL,0037 回填)另设一态
                    states = [  # (对象, is_public, 说明);owner 谓词按行判
                        (SimpleNamespace(owner_id=_OWNER_ID,
                                         visibility="private"), False, "私有"),
                        (SimpleNamespace(owner_id=_OWNER_ID,
                                         visibility="public"), True, "公共"),
                        (SimpleNamespace(owner_id=None,
                                         visibility="public"), True, "遗留无主公共"),
                    ]
                else:
                    states = [
                        (SimpleNamespace(owner_id=_OWNER_ID,
                                         visibility="private"), False, "私有"),
                        (SimpleNamespace(owner_id=_OWNER_ID,
                                         visibility="public"), True, "公共"),
                    ]
                for obj, is_public, state_label in states:
                    exp = _expected_from_snapshot(
                        _EXPECTED["table_b"][obj_type][verb],
                        is_owner=(obj.owner_id == uid),  # None 永不匹配
                        is_public=is_public, role=role)
                    cases.append(pytest.param(
                        obj_type, verb, role, uid, obj, exp,
                        id=f"{obj_type}.{verb}[{role}:{state_label}]"))
    return cases


@pytest.mark.parametrize(
    "obj_type,verb,role,uid,obj,expected", _matrix_cases())
def test_can_pure_matrix(obj_type, verb, role, uid, obj, expected):
    """can_pure 与快照推导逐格对拍(ref 谓词由端点层覆盖)。"""
    from app.routers._ownership import can_pure

    user = SimpleNamespace(role=role, id=uid)
    assert can_pure(user, obj_type, verb, obj) is expected


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

        h_admin = await role_headers(client, "mb_upadm", role="admin")
        r = await client.post(
            "/api/scenarios/sc-mb-up/unpublish", headers=h_admin)
        assert r.status_code == 200, r.text
        assert r.json()["visibility"] == "private"
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
        h_admin = await role_headers(client, "mb_puadm", role="super_admin")
        r = await client.post("/api/scenarios/sc-mb-pu/publish", headers=h_admin)
        assert r.status_code == 403, r.text


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
        assert (await client.post(
            f"/api/suites/{suite_id}/publish", headers=h_owner)).status_code == 200
        async with db_module.SessionLocal() as db:
            owner_id = (await db.execute(
                select(User.id).where(
                    User.username == "mb_supown"))).scalar_one()

        h_admin = await role_headers(client, "mb_supadm", role="admin")
        r = await client.delete(
            f"/api/suites/{suite_id}/publish", headers=h_admin)
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

        async with db_module.SessionLocal() as db:
            row = ReportDefinitionRow(
                name="mb-pub-def", description="",
                definition={"selection": {}, "projection": []},
                owner_id=owner_id,
                visibility="public" if public else "private")
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
            assert row.visibility == "public"

    async def test_only_maintainer_edits_public_definition(
            self, client: AsyncClient):
        """编辑权 = 维护者:admin 与 super_admin 都不能改他人维护的
        公共定义(W9-2 起删除 maintain 编辑面);维护者本人 200。"""
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

        # 下架(maintain = users.manage ∧ 公共):super_admin 204;
        # admin(无 users.manage)404
        h = await role_headers(client, "mb_rdadm2", role="admin")
        r = await client.delete(f"/api/report-definitions/{did}", headers=h)
        assert r.status_code == 404, r.text
        h2 = await role_headers(client, "mb_rdsup2", role="super_admin")
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
        assert r.status_code == 204, r.text     # 下架面(maintain)
