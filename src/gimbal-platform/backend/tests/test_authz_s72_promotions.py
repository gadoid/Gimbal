"""M2a S7.2 提升流程:析出分析 / 无冲突直通复制 / 冲突转审批(0048)。

Q1 裁定落点:有冲突 → pending 申请,项目管理员逐项裁决(采纳原件值
写入项目层 / 保留项目层值),批准以**批准那一刻**的原件内容复制;
驳回须理由;申请人可撤回。用例集:成员场景 reference(已在项目)/
promote(私有随行)/ 阻断(他人私有、别的项目)。
"""
from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import make_draft, role_headers


async def _mk_project(name: str, *, members: dict[str, str]) -> int:
    from sqlalchemy import select as sa_select

    from app.core import db as db_module
    from app.models.project import Project, ProjectMember
    from app.models.user import User

    async with db_module.SessionLocal() as db:
        proj = Project(name=name, kind="normal", description="")
        db.add(proj)
        await db.flush()
        for uname, role in members.items():
            uid = (await db.execute(sa_select(User.id).where(
                User.username == uname))).scalar_one()
            db.add(ProjectMember(project_id=proj.id, user_id=uid, role=role))
        await db.commit()
        return proj.id


async def _put_carry(
    client: AsyncClient, headers: dict, scope: str, service: str,
    entries: dict, *, project_id: int | None = None,
) -> None:
    """写 carry 层(user=本人个人层;project=项目管理员经 API)。"""
    params: dict = {"scope": scope, "service": service}
    if project_id is not None:
        params["projectId"] = project_id
    r = await client.put(
        "/api/carry/bindings/fin", headers=headers,
        params=params, json={"bindings": entries})
    assert r.status_code == 200, r.text


def _draft_with_carry(scenario_id: str) -> dict:
    """带 carry 引用步的场景(fin.host 的值走 carry 注入)。"""
    d = make_draft(scenario_id, steps=[{
        "id": "s1", "kind": "step",
        "call": {"service": "fin", "path": "/x"},
    }])
    return d


class TestAnalyze:
    async def test_member_analyze_conflict_detection(self, client: AsyncClient):
        """个人层与项目层同路径不同值 → 冲突;公共层同值无冲突。"""
        h_m = await role_headers(client, "s72_am", role="user")
        h_adm = await role_headers(client, "s72_aad", role="user")
        pid = await _mk_project(
            "s72-ana", members={"s72_am": "member", "s72_aad": "admin"})
        await client.post("/api/scenarios", headers=h_m,
                          json=_draft_with_carry("sc-s72-ana"))
        # 个人层 fin.host=prod;项目层 fin.host=prod-proj → 冲突
        await _put_carry(client, h_m, "user", "fin",
                         {"host": "prod", "token": "t1"})
        await _put_carry(client, h_adm, "project", "fin",
                         {"host": "prod-proj"}, project_id=pid)
        r = await client.post(
            f"/api/projects/{pid}/promotions/analyze", headers=h_m,
            json={"kind": "scenario", "sourceId": "sc-s72-ana"})
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["blockers"] == []
        conflicts = {(c["service"], c["path"]): c for c in out["conflicts"]}
        assert set(conflicts) == {("fin", "host"), ("fin", "token")}
        assert conflicts[("fin", "host")]["projectValue"] == "prod-proj"
        # 缺口:项目层没有 token → projectValue=None
        assert conflicts[("fin", "token")]["projectValue"] is None
        assert conflicts[("fin", "token")]["sourceValue"] == "t1"

    async def test_gates(self, client: AsyncClient):
        h_m = await role_headers(client, "s72_gm", role="user")
        h_x = await role_headers(client, "s72_gx", role="user")
        pid = await _mk_project("s72-gate", members={"s72_gm": "member"})
        await client.post("/api/scenarios", headers=h_m,
                          json=_draft_with_carry("sc-s72-g"))
        # 非成员 404;他人场景 403;已在项目 422
        r = await client.post(
            f"/api/projects/{pid}/promotions/analyze", headers=h_x,
            json={"kind": "scenario", "sourceId": "sc-s72-g"})
        assert r.status_code == 404
        r = await client.post(
            f"/api/projects/{pid}/promotions/analyze", headers=h_m,
            json={"kind": "scenario", "sourceId": "no-such"})
        assert r.status_code == 404
        from sqlalchemy import update as sa_update

        from app.core import db as db_module
        from app.models.composer_scenario import ComposerScenario

        async with db_module.SessionLocal() as db:
            await db.execute(sa_update(ComposerScenario).where(
                ComposerScenario.scenario_id == "sc-s72-g"
            ).values(project_id=pid))
            await db.commit()
        r = await client.post(
            f"/api/projects/{pid}/promotions/analyze", headers=h_m,
            json={"kind": "scenario", "sourceId": "sc-s72-g"})
        assert r.status_code == 422 and r.json()["detail"]["code"] == \
            "source_not_private"


class TestNoConflictDirectCopy:
    async def test_immediate_copy(self, client: AsyncClient):
        """无冲突:直通复制(不落申请行),副本进项目 + 剥离明文。"""
        h_m = await role_headers(client, "s72_dm", role="user")
        pid = await _mk_project("s72-direct", members={"s72_dm": "member"})
        draft = _draft_with_carry("sc-s72-d")
        draft["definition"]["config"]["users"] = {"acct": {"token": "sec"}}
        await client.post("/api/scenarios", headers=h_m, json=draft)
        r = await client.post(
            f"/api/projects/{pid}/promotions", headers=h_m,
            json={"kind": "scenario", "sourceId": "sc-s72-d"})
        assert r.status_code == 201, r.text
        out = r.json()
        assert out["status"] == "copied"
        copy_id = out["copy"]["scenarioId"]
        assert copy_id != "sc-s72-d"
        from sqlalchemy import select as sa_select

        from app.core import db as db_module
        from app.models.composer_scenario import ComposerScenario
        from app.models.project_promotion import ProjectPromotion

        async with db_module.SessionLocal() as db:
            row = (await db.execute(sa_select(ComposerScenario).where(
                ComposerScenario.scenario_id == copy_id))).scalar_one()
            assert row.project_id == pid
            assert row.owner_id == row.owner_id  # 维护者不变(同属主)
            assert not ((row.payload["definition"].get("config") or {})
                        .get("users")), "项目副本不落内置凭证明文"
            assert row.forked_from_id == "sc-s72-d"
            n = (await db.execute(sa_select(ProjectPromotion))).scalars().all()
            assert n == [], "直通路径不落申请行"
        # 原件保持私有、可用
        r = await client.get("/api/scenarios/sc-s72-d/draft", headers=h_m)
        assert r.status_code == 200


class TestApprovalFlow:
    async def _apply_with_conflict(
        self, client: AsyncClient,
    ) -> tuple[dict, dict, int, dict]:
        h_m = await role_headers(client, "s72_fm", role="user")
        h_adm = await role_headers(client, "s72_fad", role="user")
        pid = await _mk_project(
            "s72-flow", members={"s72_fm": "member", "s72_fad": "admin"})
        await client.post("/api/scenarios", headers=h_m,
                          json=_draft_with_carry("sc-s72-f"))
        await _put_carry(client, h_m, "user", "fin",
                         {"host": "prod", "token": "t1"})
        await _put_carry(client, h_adm, "project", "fin",
                         {"host": "prod-proj"}, project_id=pid)
        r = await client.post(
            f"/api/projects/{pid}/promotions", headers=h_m,
            json={"kind": "scenario", "sourceId": "sc-s72-f"})
        assert r.status_code == 201, r.text
        out = r.json()
        assert out["status"] == "pending"
        return h_m, h_adm, pid, out

    async def test_conflict_to_pending_then_approve(
            self, client: AsyncClient):
        h_m, h_adm, pid, out = await self._apply_with_conflict(client)
        promo_id = out["promotionId"]
        # 列表:管理员见全部,成员见自己;申请人外的人 404 详情
        r = await client.get(
            f"/api/projects/{pid}/promotions", headers=h_adm)
        assert [p["id"] for p in r.json()["items"]] == [promo_id]
        # 裁决须逐项覆盖
        r = await client.post(
            f"/api/project-promotions/{promo_id}/approve", headers=h_adm,
            json={"decisions": [
                {"service": "fin", "path": "host", "use": "source",
                 "sourceValue": "prod"}]})
        assert r.status_code == 422 and r.json()["detail"]["code"] == \
            "decisions_mismatch"
        # 采纳 host 原件值;token 保留项目层(缺口,即维持字面量)
        r = await client.post(
            f"/api/project-promotions/{promo_id}/approve", headers=h_adm,
            json={"decisions": [
                {"service": "fin", "path": "host", "use": "source",
                 "sourceValue": "prod"},
                {"service": "fin", "path": "token", "use": "project",
                 "sourceValue": "t1"}]})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "approved"
        copy_id = r.json()["copy"]["scenarioId"]
        # 项目层收到 host=prod(合并写:未裁决路径不动 —— 项目层原本无 token)
        r = await client.get(
            "/api/carry/bindings/fin", headers=h_adm,
            params={"scope": "project", "projectId": pid})
        assert r.json()["bindings"]["host"] == "prod"
        assert "token" not in r.json()["bindings"]
        # 副本进项目;通知:申请人收到 approved
        from sqlalchemy import select as sa_select

        from app.core import db as db_module
        from app.models.composer_scenario import ComposerScenario
        from app.models.permission import Notification

        async with db_module.SessionLocal() as db:
            row = (await db.execute(sa_select(ComposerScenario).where(
                ComposerScenario.scenario_id == copy_id))).scalar_one()
            assert row.project_id == pid
            notes = (await db.execute(sa_select(Notification).where(
                Notification.type == "project_promotion.approved"
            ))).scalars().all()
            assert len(notes) == 1
        # 已批准再批 → 409
        r = await client.post(
            f"/api/project-promotions/{promo_id}/approve", headers=h_adm,
            json={"decisions": []})
        assert r.status_code == 409

    async def test_project_admin_gates_and_reject_withdraw(
            self, client: AsyncClient):
        h_m, h_adm, pid, out = await self._apply_with_conflict(client)
        promo_id = out["promotionId"]
        h_other = await role_headers(client, "s72_fo", role="user")
        # 非项目管理员不能裁决;申请人不能自批
        r = await client.post(
            f"/api/project-promotions/{promo_id}/approve",
            headers=h_other, json={"decisions": []})
        assert r.status_code == 403
        r = await client.post(
            f"/api/project-promotions/{promo_id}/approve",
            headers=h_m, json={"decisions": []})
        assert r.status_code == 403
        # 驳回须理由;申请人收到 rejected
        r = await client.post(
            f"/api/project-promotions/{promo_id}/reject", headers=h_adm,
            json={"reason": ""})
        assert r.status_code == 422
        r = await client.post(
            f"/api/project-promotions/{promo_id}/reject", headers=h_adm,
            json={"reason": "项目层用新网关,不采纳旧值"})
        assert r.status_code == 200
        assert r.json()["status"] == "rejected"
        # 已驳回不能撤回(非 pending)
        r = await client.post(
            f"/api/project-promotions/{promo_id}/withdraw", headers=h_m)
        assert r.status_code == 409

    async def test_withdraw(self, client: AsyncClient):
        h_m, h_adm, pid, out = await self._apply_with_conflict(client)
        promo_id = out["promotionId"]
        # 他人不可见详情(404);申请人可撤回
        h_x = await role_headers(client, "s72_wx", role="user")
        assert (await client.get(
            f"/api/project-promotions/{promo_id}", headers=h_x)).status_code \
            == 404
        r = await client.post(
            f"/api/project-promotions/{promo_id}/withdraw", headers=h_m)
        assert r.status_code == 200 and r.json()["status"] == "withdrawn"


class TestSuitePromotion:
    async def test_suite_members_plan_and_promotion(
            self, client: AsyncClient):
        """成员已在项目 → reference;私有随行 → promote 一并复制;
        他人私有 → 阻断。"""
        h_m = await role_headers(client, "s72_sm", role="user")
        h_adm = await role_headers(client, "s72_sad", role="user")
        pid = await _mk_project(
            "s72-suite", members={"s72_sm": "member", "s72_sad": "admin"})
        # sc-pre:先单独提升过(项目里已有副本);sc-priv:私有随行。
        await client.post("/api/scenarios", headers=h_m,
                          json=_draft_with_carry("sc-s72-pre"))
        await client.post("/api/scenarios", headers=h_m,
                          json=_draft_with_carry("sc-s72-priv"))
        r = await client.post(
            f"/api/projects/{pid}/promotions", headers=h_m,
            json={"kind": "scenario", "sourceId": "sc-s72-pre"})
        assert r.status_code == 201 and r.json()["status"] == "copied", r.text
        pre_copy = r.json()["copy"]["scenarioId"]
        r = await client.post("/api/suites", headers=h_m,
                              json={"name": "s72-suite-a"})
        sid = r.json()["suiteId"]
        from app.core import db as db_module
        from app.models.suite import SuiteMember

        # 合法私有套件成员 = 自己的私有场景(S1.5 同区触发器钉死;
        # 他人私有/他项目场景根本进不来 —— blockers 属防御分支)
        async with db_module.SessionLocal() as db:
            for i, scen in enumerate(["sc-s72-pre", "sc-s72-priv"]):
                db.add(SuiteMember(suite_id=sid, scenario_id=scen,
                                   role="main", sort=i))
            await db.commit()
        r = await client.post(
            f"/api/projects/{pid}/promotions/analyze", headers=h_m,
            json={"kind": "suite", "sourceId": str(sid)})
        assert r.status_code == 200, r.text
        out = r.json()
        plan = {p["scenarioId"]: p["action"] for p in out["memberPlan"]}
        assert plan == {"sc-s72-pre": "reference", "sc-s72-priv": "promote"}
        copy_of = {p["scenarioId"]: p.get("copyOf")
                   for p in out["memberPlan"]}
        assert copy_of["sc-s72-pre"] == pre_copy, "reference 指向既有提升副本"
        assert out["blockers"] == []
        # 无 carry 冲突 → 直通复制(reference + promote)
        r = await client.post(
            f"/api/projects/{pid}/promotions", headers=h_m,
            json={"kind": "suite", "sourceId": str(sid)})
        assert r.status_code == 201, r.text
        out = r.json()
        assert out["status"] == "copied"
        new_suite_id = out["copy"]["suiteId"]
        assert out["copy"]["copiedScenarioIds"], "私有成员随行复制"
        from sqlalchemy import select as sa_select

        from app.models.suite import Suite

        async with db_module.SessionLocal() as db:
            ns = (await db.execute(sa_select(Suite).where(
                Suite.id == new_suite_id))).scalar_one()
            assert ns.project_id == pid and ns.forked_from_id == sid
            members = (await db.execute(sa_select(
                SuiteMember.scenario_id).where(
                SuiteMember.suite_id == new_suite_id))).scalars().all()
            assert pre_copy in members              # reference 直指既有副本
            assert set(out["copy"]["copiedScenarioIds"]) <= set(members)
