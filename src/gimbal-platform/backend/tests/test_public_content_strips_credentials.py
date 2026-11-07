"""authz W6:公共内容不带作者凭证(dev-plan W6 测试项①–⑤)。

主规则(评审 R3):``run_prepare.built_in_users`` 只在执行人 == 场景
属主时生效 —— 一条规则覆盖 share_ref 引用执行 / 订阅执行 / 平台身份
/ 存量公开场景,不需要数据迁移。
附加清理:公开(发布,含 suite 级联)与拷贝(copy_scenario 单点,
覆盖复制到我的/分享拷贝/引用转副本/suite fork)删 ``config.users``;
随场景公开的数据集剥敏感列(10.6)。「订阅时剥离」不成立(E1:订阅
引用活的公共场景,公开时机已剥)。
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


# ── ① 主规则:谓词矩阵(built_in_users / prepare_exec 两层)────────
@pytest.mark.parametrize("executor,owner,expect_kept", [
    (1, 1, True),     # 执行人 = 属主 → 生效
    (2, 1, False),    # 引用执行 / 订阅执行 / 平台身份 → 当空
    (None, 1, True),  # 展示/清单面(不判)→ 原样
    (1, None, True),  # adhoc(无存储属主)→ 原样
])
def test_built_in_users_main_rule(executor, owner, expect_kept):
    from app.services.run_prepare import built_in_users

    payload = {"definition": {"config": {"users": dict(_USERS)}}}
    out = built_in_users(payload, executor_id=executor,
                         scenario_owner_id=owner)
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
    async def test_publish_strips_users_and_dataset_sensitive_columns(
            self, client: AsyncClient):
        from sqlalchemy import select as sa_select

        from app.core import db as db_module
        from app.models.composer_data_set import ComposerDataSet
        from app.models.composer_scenario import ComposerScenario

        draft = _draft_with_users("sc-w6-pub")
        draft["definition"]["config"]["vars"] = {
            "amount": 1, "api_key": "k", "userToken": "t", "note": "n"}
        h = await role_headers(client, "sc_own")
        await client.post("/api/scenarios", headers=h, json=draft)
        await client.post(
            "/api/scenarios/sc-w6-pub/data-sets", headers=h,
            json={"name": "ds", "rows": [
                {"amount": 1, "api_key": "k", "userToken": "t", "note": "n"}]})
        assert (await client.post(
            "/api/scenarios/sc-w6-pub/publish", headers=h)).status_code == 200

        async with db_module.SessionLocal() as s:
            row = (await s.execute(sa_select(ComposerScenario).where(
                ComposerScenario.scenario_id == "sc-w6-pub"))).scalar_one()
            cfg = (row.payload or {}).get("definition", {}).get("config", {})
            assert not cfg.get("users")            # 场景内置凭证剥
            ds = (await s.execute(sa_select(ComposerDataSet).where(
                ComposerDataSet.scenario_id == "sc-w6-pub"))).scalar_one()
            # ③ 数据集:敏感列剥、非敏感列保留
            assert ds.rows and set(ds.rows[0]) == {"amount", "note"}

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
