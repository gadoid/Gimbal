"""authz W6:公共内容不带作者凭证(dev-plan W6 测试项①–⑤)。

主规则(评审 R3):``run_prepare.built_in_users`` 只在执行人 == 场景
属主时生效 —— 一条规则覆盖 share_ref 引用执行 / 订阅执行 / 平台身份
/ 存量公开场景,不需要数据迁移。
原件不动(修订):发布不再剥离 —— 作者自己执行照常带内置凭证与敏感
列,下架无损。凡交到非属主手里的形态各自脱敏:读(详情/draft/数据集,
含引用闭包)、跨属主拷贝(copy_scenario 单点;同属主另存为保留)、
执行(属主规则 + 非属主数据集剥敏感列 + 快照/任务参数去 config.users)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from tests.helpers import make_draft, register_and_login, role_headers

_GET_STEP = {
    "kind": "step", "description": "查单",
    "call": {"protocol": "http", "service": "svc",
             "method": "GET", "path": "/x", "headers": {}},
    "request": {"kind": "request", "body": {}}, "strategy": [],
}
_USERS = {"gitlab": {"username": "u", "password": "p", "token": "t"}}


def _draft_with_users(sid: str, *, users: dict | None = None) -> dict:
    draft = make_draft(sid, steps=[_GET_STEP])
    draft["definition"]["config"]["users"] = users if users is not None else dict(_USERS)
    return draft


def _draft_with_vars(sid: str) -> dict:
    """内置凭证 + 声明 amount/password 两个变量(数据集行列须已声明)。"""
    draft = _draft_with_users(sid)
    draft["definition"]["config"]["vars"] = {"amount": 1, "password": ""}
    return draft


# ── ① 主规则:谓词矩阵(built_in_users / prepare_exec 两层)────────
@pytest.mark.parametrize("executor,owner,project,expect_kept", [
    (1, 1, None, True),     # 私有区 + 执行人 = 属主 → 生效
    (2, 1, None, False),    # 引用执行 / 订阅执行 / 非属主导出 → 当空
    (None, 1, None, False),  # fail-closed:执行人未知 → 当空(此前放行)
    (1, None, None, False),  # fail-closed:孤儿场景(属主已删)→ 当空
    (None, None, None, False),
    (1, 1, 7, False),       # 原 5(S6):项目/公共区 → 属主本人也当空
])
def test_built_in_users_main_rule(executor, owner, project, expect_kept):
    from app.services.run_prepare import built_in_users

    payload = {"definition": {"config": {"users": dict(_USERS)}}}
    out = built_in_users(payload, executor_id=executor,
                         scenario_owner_id=owner, project_id=project)
    assert bool(out) is expect_kept
    if expect_kept:
        assert out == _USERS


async def test_prepare_exec_main_rule_wired():
    """prepare_exec 透传主规则(dispatcher/graph/runner/export 四链的
    共同装配点;executor ≠ owner ⇒ prep.built_in_users 当空)。"""
    from app.core import db as db_module
    from app.services import run_prepare

    payload = {"definition": {"config": {"users": dict(_USERS)}}}
    prep = await run_prepare.prepare_exec(
        db_module.SessionLocal, payload, owner_id=2,
        scenario_owner_id=1, with_auth=False)
    assert prep.built_in_users == {}
    prep_own = await run_prepare.prepare_exec(
        db_module.SessionLocal, payload, owner_id=1,
        scenario_owner_id=1, with_auth=False)
    assert prep_own.built_in_users == _USERS


# ── ② 附加清理:公开与拷贝入口后 payload 无 config.users ────────────
class TestStripping:
    async def test_publish_keeps_original_readers_desensitized(
            self, client: AsyncClient):
        """发布不改原件(作者自己照常用凭证与敏感列,下架无损);非属主
        读面(详情 / draft / 数据集详情 / 数据集列表预览)各自脱敏。"""
        from sqlalchemy import select as sa_select

        from app.core import db as db_module
        from app.models.composer_data_set import ComposerDataSet
        from app.models.composer_scenario import ComposerScenario

        draft = _draft_with_users("sc-w6-pub")
        draft["definition"]["config"]["vars"] = {
            "amount": 1, "api_key": "k", "userToken": "t", "note": "n"}
        h = await role_headers(client, "sc_own")
        await client.post("/api/scenarios", headers=h, json=draft)
        r = await client.post(
            "/api/scenarios/sc-w6-pub/data-sets", headers=h,
            json={"name": "ds", "rows": [
                {"amount": 1, "api_key": "k", "userToken": "t", "note": "n"}]})
        ds_id = r.json()["datasetId"]
        r = await client.post("/api/scenarios/sc-w6-pub/publish", headers=h)
        assert r.status_code == 200
        # S1.3 发布 = 复制:回包是公共副本,凭证/敏感列**落库即无**
        assert r.json()["meta"]["scenarioId"] == "sc-w6-pub-public"
        assert not r.json()["config"].get("users")

        # 原件不动
        async with db_module.SessionLocal() as s:
            row = (await s.execute(sa_select(ComposerScenario).where(
                ComposerScenario.scenario_id == "sc-w6-pub"))).scalar_one()
            assert row.payload["definition"]["config"]["users"] == _USERS
            ds = (await s.execute(sa_select(ComposerDataSet).where(
                ComposerDataSet.scenario_id == "sc-w6-pub"))).scalar_one()
            assert set(ds.rows[0]) == {"amount", "api_key", "userToken", "note"}

        # 属主读:原样
        r = await client.get("/api/scenarios/sc-w6-pub", headers=h)
        assert r.json()["config"]["users"] == _USERS
        r = await client.get(f"/api/data-sets/{ds_id}", headers=h)
        assert set(r.json()["rows"][0]) == {"amount", "api_key", "userToken", "note"}

        # 非属主读**公共副本**:落库即无凭证、数据集敏感列剥
        h_o = await role_headers(client, "sc_rdr", role="user")
        copy_sid = "sc-w6-pub-public"
        r = await client.get(f"/api/scenarios/{copy_sid}", headers=h_o)
        assert r.status_code == 200 and not r.json()["config"].get("users")
        r = await client.get(f"/api/scenarios/{copy_sid}/draft", headers=h_o)
        assert not r.json()["definition"]["config"].get("users")
        from sqlalchemy import select as _sel

        from app.models.composer_data_set import ComposerDataSet as _DS
        async with db_module.SessionLocal() as s2:
            copy_ds = (await s2.execute(_sel(_DS.dataset_id).where(
                _DS.scenario_id == copy_sid))).scalar_one()
        r = await client.get(f"/api/data-sets/{copy_ds}", headers=h_o)
        assert r.status_code == 200
        assert r.json()["rows"] == [{"amount": 1, "note": "n"}]

        # 下架后属主数据完好(此前发布即删列,下架恢复不了)
        await client.post("/api/scenarios/sc-w6-pub/unpublish", headers=h)
        r = await client.get(f"/api/data-sets/{ds_id}", headers=h)
        assert set(r.json()["rows"][0]) == {"amount", "api_key", "userToken", "note"}

    async def test_ref_reader_dataset_list_preview_redacted(
            self, client: AsyncClient):
        """引用闭包读者的数据集列表预览剥敏感列(属主原样)。"""
        h_owner = await role_headers(client, "sc_lpo")
        await client.post("/api/scenarios", headers=h_owner,
                          json=_draft_with_vars("sc-w6-lp"))
        await client.post(
            "/api/scenarios/sc-w6-lp/data-sets", headers=h_owner,
            json={"name": "ds", "rows": [{"amount": 1, "password": "pw"}]})
        await role_headers(client, "sc_lpr", role="user")
        roster = (await client.get(
            "/api/users/roster", headers=h_owner)).json()["items"]
        rid = next(u["id"] for u in roster if u["username"] == "sc_lpr")
        r = await client.post("/api/shares", headers=h_owner, json={
            "resourceType": "scenario", "resourceId": "sc-w6-lp",
            "granteeUserId": rid, "mode": "ref"})
        assert r.status_code == 201, r.text
        h_r = await role_headers(client, "sc_lpr", role="user")
        r = await client.get("/api/data-sets?scenarioId=sc-w6-lp", headers=h_r)
        assert r.json()[0]["preview"] == [{"amount": 1}]
        r = await client.get("/api/data-sets?scenarioId=sc-w6-lp",
                             headers=h_owner)
        assert r.json()[0]["preview"] == [{"amount": 1, "password": "pw"}]

    async def test_copy_strips_users(self, client: AsyncClient):
        """「复制到我的」剥离(引用转副本/分享拷贝/suite fork 全走
        copy_scenario 同一单点)。"""
        h_owner = await role_headers(client, "sc_cpo")
        await client.post("/api/scenarios", headers=h_owner,
                          json=_draft_with_users("sc-w6-cp"))
        h_other = await role_headers(client, "sc_cpc", role="user")
        # 私有场景 + 引用分享 → 被分享人「转为副本」(跨属主拷贝,
        # 源头凭证在场 —— 拷贝剥离正是为这条路径)
        roster = (await client.get(
            "/api/users/roster", headers=h_owner)).json()["items"]
        other_id = next(u["id"] for u in roster
                        if u["username"] == "sc_cpc")
        r = await client.post("/api/shares", headers=h_owner, json={
            "resourceType": "scenario", "resourceId": "sc-w6-cp",
            "granteeUserId": other_id, "mode": "ref"})
        assert r.status_code == 201, r.text
        share_id = r.json()["id"]
        r = await client.post(f"/api/shares/{share_id}/fork", headers=h_other)
        assert r.status_code == 201, r.text
        new_sid = r.json()["scenarioId"]
        from sqlalchemy import select as sa_select

        from app.core import db as db_module
        from app.models.composer_scenario import ComposerScenario

        async with db_module.SessionLocal() as s:
            row = (await s.execute(sa_select(ComposerScenario).where(
                ComposerScenario.scenario_id == new_sid))).scalar_one()
            cfg = (row.payload or {}).get("definition", {}).get("config", {})
            assert not cfg.get("users")

    async def test_self_save_as_keeps_credentials(self, client: AsyncClient):
        """作者给自己「另存为」(同属主拷贝)保留内置凭证与数据集敏感列
        —— 凭证本就是自己的;剥离只发生在跨属主拷贝。"""
        from sqlalchemy import select as sa_select

        from app.core import db as db_module
        from app.models.composer_data_set import ComposerDataSet
        from app.models.composer_scenario import ComposerScenario

        h = await role_headers(client, "sc_sav")
        await client.post("/api/scenarios", headers=h,
                          json=_draft_with_vars("sc-w6-sav"))
        await client.post(
            "/api/scenarios/sc-w6-sav/data-sets", headers=h,
            json={"name": "ds", "rows": [{"amount": 1, "password": "pw"}]})
        r = await client.post("/api/scenarios/sc-w6-sav/copy", headers=h,
                              json={"name": "my copy"})
        assert r.status_code == 201, r.text
        new_sid = r.json()["meta"]["scenarioId"]

        async with db_module.SessionLocal() as s:
            row = (await s.execute(sa_select(ComposerScenario).where(
                ComposerScenario.scenario_id == new_sid))).scalar_one()
            cfg = (row.payload or {}).get("definition", {}).get("config", {})
            assert cfg.get("users") == _USERS
            ds = (await s.execute(sa_select(ComposerDataSet).where(
                ComposerDataSet.scenario_id == new_sid))).scalar_one()
            assert ds.rows == [{"amount": 1, "password": "pw"}]

    async def test_cross_owner_copy_strips_dataset_columns(
            self, client: AsyncClient):
        """跨属主拷贝(引用转副本)数据集敏感列剥、非敏感列保留。"""
        from sqlalchemy import select as sa_select

        from app.core import db as db_module
        from app.models.composer_data_set import ComposerDataSet

        h_owner = await role_headers(client, "sc_cdo")
        await client.post("/api/scenarios", headers=h_owner,
                          json=_draft_with_vars("sc-w6-cd"))
        await client.post(
            "/api/scenarios/sc-w6-cd/data-sets", headers=h_owner,
            json={"name": "ds", "rows": [{"amount": 1, "password": "pw"}]})
        await role_headers(client, "sc_cdc", role="user")
        roster = (await client.get(
            "/api/users/roster", headers=h_owner)).json()["items"]
        other_id = next(u["id"] for u in roster if u["username"] == "sc_cdc")
        r = await client.post("/api/shares", headers=h_owner, json={
            "resourceType": "scenario", "resourceId": "sc-w6-cd",
            "granteeUserId": other_id, "mode": "ref"})
        share_id = r.json()["id"]
        h_other = await role_headers(client, "sc_cdc", role="user")
        r = await client.post(f"/api/shares/{share_id}/fork", headers=h_other)
        assert r.status_code == 201, r.text
        new_sid = r.json()["scenarioId"]
        async with db_module.SessionLocal() as s:
            ds = (await s.execute(sa_select(ComposerDataSet).where(
                ComposerDataSet.scenario_id == new_sid))).scalar_one()
            assert ds.rows == [{"amount": 1}]

    async def test_suite_fork_members_stripped(self, client: AsyncClient):
        """suite fork(deep_copy_suite 三入口之一)成员副本剥离。"""
        h_owner = await role_headers(client, "sc_spo")
        await client.post("/api/scenarios", headers=h_owner,
                          json=_draft_with_users("sc-w6-su"))
        r = await client.post("/api/suites", headers=h_owner,
                              json={"name": "w6-suite", "description": ""})
        sid = r.json()["suiteId"]
        await client.post(f"/api/suites/{sid}/members", headers=h_owner,
                          json={"scenarioIds": ["sc-w6-su"],
                                "publishUnpublished": False})
        h_other = await role_headers(client, "sc_spc", role="user")
        # 私有 suite + 引用分享 → 被分享人深拷贝(三入口之一;
        # 公共路径的成员在级联发布时已剥,这里钉私有源头不外带)
        roster = (await client.get(
            "/api/users/roster", headers=h_owner)).json()["items"]
        other_id = next(u["id"] for u in roster
                        if u["username"] == "sc_spc")
        r = await client.post("/api/shares", headers=h_owner, json={
            "resourceType": "suite", "resourceId": str(sid),
            "granteeUserId": other_id, "mode": "ref"})
        assert r.status_code == 201, r.text
        share_id = r.json()["id"]
        r = await client.post(f"/api/shares/{share_id}/fork", headers=h_other)
        assert r.status_code == 201, r.text
        from sqlalchemy import select as sa_select

        from app.core import db as db_module
        from app.models.composer_scenario import ComposerScenario

        async with db_module.SessionLocal() as s:
            rows = (await s.execute(sa_select(ComposerScenario).where(
                ComposerScenario.scenario_id.like("sc-w6-su-copy-%"))
            )).scalars().all()
            assert rows, "副本成员应在"
            for row in rows:
                cfg = (row.payload or {}).get(
                    "definition", {}).get("config", {})
                assert not cfg.get("users")

    async def test_import_strips_users_regression(self):
        """④ 导入路径既有剥离(P2:config.users 不落库)的回归钉。"""
        from app.services import scenario_import, scenario_store
        from app.services.scenario_store import strip_builtin_credentials

        # 敏感启发单源钉(W6 review):导入的敏感路径正则与数据集
        # 敏感列正则是同一对象,防两张表漂移
        assert (scenario_import._SENSITIVE_RE
                is scenario_store.SENSITIVE_COLUMN_RE)

        payload = {"definition": {"config": {
            "users": dict(_USERS), "timePolicy": {}}}}
        out = strip_builtin_credentials(payload)
        assert not out["definition"]["config"].get("users")
        # 幂等 + 无 users 时不动
        assert strip_builtin_credentials(out) is out
        assert strip_builtin_credentials(
            {"definition": {"config": {}}})["definition"]["config"] == {}


# ── ⑤ 预检三条件告警(钉「不吵」)──────────────────────────────────
class TestPrecheckAlarm:
    async def _mk_private_with_users(self, client, owner_h) -> None:
        await client.post("/api/scenarios", headers=owner_h,
                          json=_draft_with_users("sc-w6-al"))

    async def _precheck(self, client, h, sid: str) -> dict:
        r = await client.post("/api/run/precheck", headers=h,
                              json=[{"scenarioId": sid, "schemeId": "default"}])
        assert r.status_code == 200, r.text
        return r.json()[0]

    async def test_all_three_conditions_alarm(self, client: AsyncClient):
        """① 执行人≠属主 + ② 场景有内置凭证 + ③ 执行人自己解析不到
        → builtinAuthShadowed 列出别名。"""
        h_owner = await role_headers(client, "al_own")
        await self._mk_private_with_users(client, h_owner)
        # 引用给 bob(bob ≠ 属主,可读)
        await role_headers(client, "al_bob", role="user")
        roster = (await client.get(
            "/api/users/roster", headers=h_owner)).json()["items"]
        bob_id = next(u["id"] for u in roster if u["username"] == "al_bob")
        r = await client.post("/api/shares", headers=h_owner, json={
            "resourceType": "scenario", "resourceId": "sc-w6-al",
            "granteeUserId": bob_id, "mode": "ref"})
        assert r.status_code == 201, r.text
        h_bob = await role_headers(client, "al_bob", role="user")
        out = await self._precheck(client, h_bob, "sc-w6-al")
        assert out["builtinAuthShadowed"] == ["gitlab"]

    async def test_no_alarm_when_owner_self(self, client: AsyncClient):
        """条件①不满足(属主自查):场景有凭证、别名也缺 → 仍不告警
        (属主执行内置凭证生效,不构成「会被当空」的预警)。"""
        h_owner = await role_headers(client, "al_ow2")
        await self._mk_private_with_users(client, h_owner)
        out = await self._precheck(client, h_owner, "sc-w6-al")
        assert out["builtinAuthShadowed"] == []

    async def test_no_alarm_when_no_builtin_users(self, client: AsyncClient):
        """条件②不满足(场景无内置凭证)。"""
        h_owner = await role_headers(client, "al_ow3")
        await client.post("/api/scenarios", headers=h_owner,
                          json=make_draft("sc-w6-al", steps=[_GET_STEP]))
        h_other = await register_and_login(client, "al_o3", "alpass12345")
        # 公共场景保证 other 可读
        from tests.inbound_fixtures import publish_scenario

        await publish_scenario("sc-w6-al")
        out = await self._precheck(client, h_other, "sc-w6-al")
        assert out["builtinAuthShadowed"] == []

    async def test_no_alarm_when_executor_has_own_credentials(
            self, client: AsyncClient):
        """条件③不满足(执行人自己的认证会话里有同名别名)。"""
        h_owner = await role_headers(client, "al_ow4")
        await self._mk_private_with_users(client, h_owner)
        h_exec = await role_headers(client, "al_ex4", role="user")
        # 执行人自建同名别名 gitlab
        r = await client.post("/api/auths", headers=h_exec, json={
            "alias": "gitlab", "url": "https://git", "username": "u",
            "password": "p", "token_type": "Bearer"})
        assert r.status_code in (200, 201), r.text
        roster = (await client.get(
            "/api/users/roster", headers=h_owner)).json()["items"]
        exec_id = next(u["id"] for u in roster
                       if u["username"] == "al_ex4")
        r = await client.post("/api/shares", headers=h_owner, json={
            "resourceType": "scenario", "resourceId": "sc-w6-al",
            "granteeUserId": exec_id, "mode": "ref"})
        assert r.status_code == 201, r.text
        out = await self._precheck(client, h_exec, "sc-w6-al")
        assert out["builtinAuthShadowed"] == []


# ── ⑥ 执行侧非属主脱敏(原件不剥之后的执行兜底)──────────────────────
class TestForeignExecutionDesensitized:
    async def _run_capture(self, client, monkeypatch, h, ds_id) -> tuple:
        import asyncio

        from app.core import db as db_module
        from app.models.execution import ExecutionSnapshot
        from app.services import run_dispatcher as rd

        cap: list[dict] = []

        async def _fake_fanout(*, db_factory, execution_id, **kw):
            cap.append(kw)
            await rd.transition_with_retry(
                db_factory, execution_id, rd.STATUS_DONE)

        monkeypatch.setattr(rd, "_fanout", _fake_fanout)
        r = await client.post("/api/runs", headers=h, json={
            "scenarioId": "sc-w6-ex", "dataSetIds": [ds_id]})
        assert r.status_code == 201, r.text
        eid = r.json()["executionId"]
        for _ in range(200):
            if cap:
                break
            await asyncio.sleep(0.05)
        assert cap, "fanout 未被调度"
        async with db_module.SessionLocal() as s:
            snap = (await s.get(ExecutionSnapshot, eid)).snapshot
        return cap[-1], snap

    async def test_ref_executor_gets_desensitized_shapes(
            self, client: AsyncClient, monkeypatch):
        h_owner = await role_headers(client, "ex_own")
        await client.post("/api/scenarios", headers=h_owner,
                          json=_draft_with_vars("sc-w6-ex"))
        r = await client.post(
            "/api/scenarios/sc-w6-ex/data-sets", headers=h_owner,
            json={"name": "ds", "rows": [{"amount": 1, "password": "pw"}]})
        ds_id = r.json()["datasetId"]

        # 属主自跑:凭证与敏感列原样进执行
        kw, snap = await self._run_capture(client, monkeypatch, h_owner, ds_id)
        assert snap["definition"]["config"]["users"] == _USERS
        assert kw["datasets"][0]["rows"][0][1] == {"amount": 1, "password": "pw"}

        # 引用执行人:快照/任务参数无 config.users,数据集敏感列剥
        await role_headers(client, "ex_ref", role="user")
        roster = (await client.get(
            "/api/users/roster", headers=h_owner)).json()["items"]
        rid = next(u["id"] for u in roster if u["username"] == "ex_ref")
        r = await client.post("/api/shares", headers=h_owner, json={
            "resourceType": "scenario", "resourceId": "sc-w6-ex",
            "granteeUserId": rid, "mode": "ref"})
        assert r.status_code == 201, r.text
        h_ref = await role_headers(client, "ex_ref", role="user")
        kw, snap = await self._run_capture(client, monkeypatch, h_ref, ds_id)
        assert not snap["definition"]["config"].get("users")
        assert not kw["scenario_payload"]["definition"]["config"].get("users")
        assert kw["datasets"][0]["rows"][0][1] == {"amount": 1}


async def test_graph_units_strip_rows_for_foreign_runner(
        client: AsyncClient):
    """graph 编排单元:执行人 ≠ 场景属主 → 选中行的敏感列不进合成
    场景;属主自跑原样。"""
    import json

    from app.core import db as db_module
    from app.services import graph_dispatch

    h = await role_headers(client, "gx_own")
    await client.post("/api/scenarios", headers=h,
                      json=_draft_with_vars("sc-w6-gx"))
    r = await client.post(
        "/api/scenarios/sc-w6-gx/data-sets", headers=h,
        json={"name": "ds", "rows": [{"amount": 7, "password": "pw-secret"}]})
    ds_id = r.json()["datasetId"]
    from sqlalchemy import select as sa_select

    from app.models.user import User

    async with db_module.SessionLocal() as s:
        owner_id = (await s.execute(sa_select(User.id).where(
            User.username == "gx_own"))).scalar_one()
    unit = {"ref": "u1", "scenarioId": "sc-w6-gx",
            "row": {"datasetId": ds_id, "rowIndex": 0}}

    async with db_module.SessionLocal() as s:
        own = await graph_dispatch.resolve_graph_units(s, [unit], owner_id)
        foreign = await graph_dispatch.resolve_graph_units(
            s, [unit], owner_id + 999)
    assert "pw-secret" in json.dumps(own[0]["composed"], default=str)
    assert "pw-secret" not in json.dumps(foreign[0]["composed"], default=str)


# ── ⑦ suite 预检同算内置凭证告警(此前只有单场景预检算)──────────────
async def test_suite_validate_reports_builtin_auth_shadowed(
        client: AsyncClient):
    h_owner = await role_headers(client, "sv_own")
    await client.post("/api/scenarios", headers=h_owner,
                      json=_draft_with_users("sc-w6-sv"))
    r = await client.post("/api/suites", headers=h_owner,
                          json={"name": "w6-sv", "description": ""})
    sid = r.json()["suiteId"]
    await client.post(f"/api/suites/{sid}/members", headers=h_owner,
                      json={"scenarioIds": ["sc-w6-sv"],
                            "publishUnpublished": False})

    # 属主自查:不告警
    r = await client.post(f"/api/suites/{sid}/validate", headers=h_owner)
    assert r.status_code == 200, r.text
    assert not [i for i in r.json()["items"]
                if i["code"] == "builtin_auth_shadowed"]

    # 引用给 bob:bob 预检列出缺的别名
    await role_headers(client, "sv_bob", role="user")
    roster = (await client.get(
        "/api/users/roster", headers=h_owner)).json()["items"]
    bob_id = next(u["id"] for u in roster if u["username"] == "sv_bob")
    r = await client.post("/api/shares", headers=h_owner, json={
        "resourceType": "suite", "resourceId": str(sid),
        "granteeUserId": bob_id, "mode": "ref"})
    assert r.status_code == 201, r.text
    h_bob = await role_headers(client, "sv_bob", role="user")
    r = await client.post(f"/api/suites/{sid}/validate", headers=h_bob)
    assert r.status_code == 200, r.text
    hits = [i for i in r.json()["items"]
            if i["code"] == "builtin_auth_shadowed"]
    assert hits and hits[0]["units"] == ["sc-w6-sv"]
    assert "gitlab" in hits[0]["message"]


# ── ⑧ 最终产物零作者凭证(断言产物,不断言中间层)───────────────────
# 此前用例只钉 prep.built_in_users 与数据集行(中间层);materialize 以
# converted.config.users 为合并基座,作者明文照样进产物 —— 这里逐条链
# 断言**最终产物**(导出回包 / suite 编排单元 / 订阅执行 case / 单场景
# case.json)。plate convert 用 echo:converted 原样带回 config.users,
# 与真实 plate 同形(泄漏正是经由这里)。
_SECRET = "author-secret-pw-9f3"
_SECRET_USERS = {"gitlab": {"url": "https://git.example", "username": "author-acct",
                            "password": _SECRET, "token_type": "Bearer",
                            "expires_in": 7200}}


def _echo_convert(monkeypatch):
    from app.services import plate_client as pc

    async def _fake_convert(scenario):
        return {"consumer": "platform", "converted": dict(scenario)}
    monkeypatch.setattr(pc, "convert", _fake_convert)


async def _mk_secret_scenario(client, h, sid: str, *, public: bool = False):
    draft = make_draft(sid, steps=[_GET_STEP])
    draft["definition"]["config"]["users"] = dict(_SECRET_USERS)
    r = await client.post("/api/scenarios", headers=h, json=draft)
    assert r.status_code in (200, 201), r.text
    if public:
        from tests.inbound_fixtures import publish_scenario

        await publish_scenario(sid)


class TestFinalProductsNoAuthorCredentials:
    async def test_export_by_non_owner(self, client: AsyncClient, monkeypatch):
        """导出:任何登录用户导出他人公共场景 —— 产物无作者明文;属主
        导出照旧带(10-14 口径,行为不变)。"""
        _echo_convert(monkeypatch)
        h_owner = await role_headers(client, "fp_exo")
        await _mk_secret_scenario(client, h_owner, "sc-fp-ex", public=True)
        h_o = await role_headers(client, "fp_exr", role="user")
        # S1.3:非属主只能读公共副本(原件恒私有);副本落库即无明文
        r = await client.get(
            "/api/scenarios/sc-fp-ex-public/export", headers=h_o)
        assert r.status_code == 200, r.text
        assert _SECRET not in r.text and "author-acct" not in r.text
        r = await client.get("/api/scenarios/sc-fp-ex/export", headers=h_owner)
        assert r.status_code == 200, r.text
        assert r.json()["config"]["users"] == _SECRET_USERS

    async def test_suite_graph_unit_for_non_owner(
            self, client: AsyncClient, monkeypatch):
        """suite graph 编排:非属主组装出的单元场景无作者 config.users;
        属主组装照旧带。"""
        import json

        from sqlalchemy import select as sa_select

        from app.core import db as db_module
        from app.models.user import User
        from app.services import graph_dispatch

        _echo_convert(monkeypatch)
        h_owner = await role_headers(client, "fp_gro")
        await _mk_secret_scenario(client, h_owner, "sc-fp-gr")
        await role_headers(client, "fp_grr", role="user")
        async with db_module.SessionLocal() as s:
            ids = dict((await s.execute(sa_select(User.username, User.id).where(
                User.username.in_(["fp_gro", "fp_grr"])))).all())
        spec = {"mode": "chain",
                "units": [{"ref": "a", "scenarioId": "sc-fp-gr"}]}
        async with db_module.SessionLocal() as s:
            foreign = await graph_dispatch.materialize_graph(
                s, ids["fp_grr"], spec)
        assert _SECRET not in json.dumps(foreign, default=str)
        async with db_module.SessionLocal() as s:
            own = await graph_dispatch.materialize_graph(s, ids["fp_gro"], spec)
        assert own["units"][0]["scenario"]["config"]["users"] == _SECRET_USERS

    async def test_single_run_case_file_for_ref_executor(
            self, client: AsyncClient, monkeypatch):
        """单场景执行:引用执行人落盘的 case.json 无作者明文。"""
        import asyncio
        from pathlib import Path

        from app.services import gimbal_launcher as gl
        from tests.helpers import launch_ok

        _echo_convert(monkeypatch)
        cases: list[str] = []

        async def _fake_launch(case_path, **kw):
            cases.append(Path(case_path).read_text(encoding="utf-8"))
            return launch_ok()
        monkeypatch.setattr(gl, "launch", _fake_launch)

        h_owner = await role_headers(client, "fp_sro")
        await _mk_secret_scenario(client, h_owner, "sc-fp-sr")
        await role_headers(client, "fp_srr", role="user")
        roster = (await client.get(
            "/api/users/roster", headers=h_owner)).json()["items"]
        rid = next(u["id"] for u in roster if u["username"] == "fp_srr")
        r = await client.post("/api/shares", headers=h_owner, json={
            "resourceType": "scenario", "resourceId": "sc-fp-sr",
            "granteeUserId": rid, "mode": "ref"})
        assert r.status_code == 201, r.text
        h_ref = await role_headers(client, "fp_srr", role="user")
        r = await client.post("/api/runs", headers=h_ref, json={
            "scenarioId": "sc-fp-sr", "dataSetIds": []})
        assert r.status_code == 201, r.text
        for _ in range(200):
            if cases:
                break
            await asyncio.sleep(0.05)
        assert cases, "case.json 未落盘"
        assert _SECRET not in cases[-1] and "author-acct" not in cases[-1]
