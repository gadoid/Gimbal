"""决策 1 执行闸「圈定即承诺」+ 本案分享缺名提示钉位(阶段 1)。

钉子:
* 硬门:生效配置行(显式选定 / 本人默认)圈定集非空 = 白名单生效,
  换用后取用集 ⊄ 圈定集 → 409 ``identity_not_circled``(precheck_hard_
  gate 同一道门;含 slot 换用目标比对);None/空集 = 存量兼容跳过;
* 默认行也承诺(与绑定层「默认不吃」的刻意差异,见 ExecConfigChoice);
* 重跑按首发快照照查(``exec_replay.circledAliases``),不回查配置行;
* 行级 @slot 绑定同一码在派发段拦;
* 预检端点 advisory:``notCircled`` 差集 + scheme_valid=False;
* 本案(凭证治理 v2 §4.3)分享缺名提示:纯引用场景被分享人预检
  ``missingAuths`` 点名 + 派发 account_missing 硬门兜底、
  ``builtinAuthShadowed`` 对新形态静默(三条件不再满足)。
"""
from __future__ import annotations

import pytest
import sqlalchemy as sa

from app.core import db as db_module
from app.core.security import fernet_encrypt
from app.models import AuthAccount, Environment
from app.models.exec_config import ExecConfig
from app.models.service_identity import ServiceIdentity

from .helpers import make_draft, register_and_login
from .test_authz_m2b_q3_dataset_accounts import _binding, _mk_ds
from .test_authz_s8_project_credentials import (
    _STEP, _mk_project, _seed_registry_base, _uid)
from .test_run_m1_capabilities import _patch_launch_capture
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401


def _steps2() -> list[dict]:
    """qa1 + qa2 两条 token 面引用(同一请求体两个模板)。"""
    return [{
        "kind": "step",
        "call": {"service": "s8-alias", "method": "GET", "path": "/x"},
        "request": {"kind": "request", "body": {
            "tok": "${auth.qa1.token}", "tok2": "${auth.qa2.token}"}},
        "strategy": [],
    }]


async def _seed_identity(alias: str, base: str = "fin-svc") -> None:
    """种条目(username-ref,取用名 = 条目名);幂等。"""
    async with db_module.SessionLocal() as db:
        env = (await db.execute(sa.select(Environment.id).where(
            Environment.is_default.is_(True)))).scalar_one()
        if (await db.execute(sa.select(ServiceIdentity.id).where(
                ServiceIdentity.alias_name == alias))
                ).scalar_one_or_none() is None:
            db.add(ServiceIdentity(alias_name=alias, base_service=base,
                                   env_id=env, ref_mode="username",
                                   ref_username=alias))
        await db.commit()


async def _acct(uid: int, alias: str, *, default: bool = False) -> None:
    """执行人池内账户。default=True 的「acct-main」行覆盖 ref_mode=
    default 的条目(qa1/s8-alias 取用户默认行);username-ref 条目取同名行。"""
    async with db_module.SessionLocal() as db:
        env = (await db.execute(sa.select(Environment.id).where(
            Environment.is_default.is_(True)))).scalar_one()
        db.add(AuthAccount(owner_id=uid, system="fin", env_id=env,
                           username=alias, password_enc=fernet_encrypt("p"),
                           is_default=default))
        await db.commit()


async def _mk_config(uid: int, aliases: list[str], *, default: bool = False,
                     name: str = "圈定") -> int:
    """种执行配置行(systems[].aliases = 圈定集)。"""
    async with db_module.SessionLocal() as db:
        cfg = ExecConfig(scope="user", scope_id=uid, name=name,
                        is_default=default,
                        payload={"systems": [{"service": "s8-alias",
                                              "aliases": aliases}]})
        db.add(cfg)
        await db.commit()
        return cfg.id


async def _mk_scenario(client, h, sid: str, steps: list[dict]) -> str:
    r = await client.post("/api/scenarios", headers=h, json=make_draft(
        sid, steps=steps, vars_map={"amount": "1"}))
    assert r.status_code in (200, 201), r.text
    r = await _mk_ds(client, h, sid, [{"amount": "1"}])
    assert r.status_code == 201, r.text
    return r.json()["datasetId"]


async def _dispatch(uid: int, sid: str, ds_id: str, *,
                    exec_config_id: int | None = None,
                    exec_replay: dict | None = None):
    from app.schemas.scenario_composer import RunRequest
    from app.services import run_dispatcher as rd
    from app.services.scenario_store import get_row
    async with db_module.SessionLocal() as db:
        scen = await get_row(db, sid)
        return await rd.dispatch_target(
            db, uid,
            RunRequest(scenarioId=sid, clientRef="circ", dataSetIds=[ds_id],
                       execConfigId=exec_config_id),
            rd.RunTarget(scenario_id=scen.scenario_id,
                         payload=scen.payload or {}, kind="scenario"),
            exec_replay=exec_replay)


async def _setup_pair(client, username: str, sid: str) -> tuple[dict, int, str]:
    """注册底座 + qa2 条目 + 执行人两账户 + 场景(qa1/qa2 引用)+ 数据集。"""
    h = await register_and_login(client, username, "pw123456")
    uid = await _uid(username)
    await _seed_registry_base()
    await _seed_identity("qa2")
    # 取用集 = 模板引用(qa1/qa2)∪ 步骤服务条目默认命中(s8-alias,
    # ref_mode=default 取用户默认行)—— 圈定集必须把三者都算进去
    await _acct(uid, "acct-main", default=True)
    await _acct(uid, "qa2")
    ds_id = await _mk_scenario(client, h, sid, _steps2())
    return h, uid, ds_id


@pytest.mark.asyncio
async def test_dispatch_rejects_uncircled(client, plate_mock, monkeypatch):
    """显式选定配置圈定 qa1,取用集含 qa2 → 409 identity_not_circled,
    未过闸不派发(launch capture 空)。"""
    h, uid, ds_id = await _setup_pair(client, "circ1", "sc-circ-1")
    cfg = await _mk_config(uid, ["s8-alias", "qa1"])
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    from app.services import run_dispatcher as rd
    with pytest.raises(rd.Conflict) as ei:
        await _dispatch(uid, "sc-circ-1", ds_id, exec_config_id=cfg)
    assert ei.value.code == "identity_not_circled"
    assert ei.value.extra == {"aliases": ["qa2"]}
    assert cases == []


@pytest.mark.asyncio
async def test_default_row_circled_governs(client, plate_mock, monkeypatch):
    """默认行圈定同样承诺(与绑定层「默认不吃」的刻意差异):不带
    execConfigId 派发 → load_choice 落默认行 → 同码 409。"""
    h, uid, ds_id = await _setup_pair(client, "circ2", "sc-circ-2")
    await _mk_config(uid, ["s8-alias", "qa1"], default=True, name="常设")
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    from app.services import run_dispatcher as rd
    with pytest.raises(rd.Conflict) as ei:
        await _dispatch(uid, "sc-circ-2", ds_id)
    assert ei.value.code == "identity_not_circled"
    assert ei.value.extra == {"aliases": ["qa2"]}


@pytest.mark.asyncio
async def test_uncircled_config_skips(client, plate_mock, monkeypatch):
    """存量兼容:圈定集空(未圈定)= 白名单关闭 → 闸静默,派发照常
    (capture 到 launch = 过闸证明)。"""
    h, uid, ds_id = await _setup_pair(client, "circ3", "sc-circ-3")
    await _mk_config(uid, [], name="不圈")
    cases: list[dict] = []   # capture 仅作保险(launch 不会同步发生:C11 队列)
    _patch_launch_capture(monkeypatch, cases)
    resp = await _dispatch(uid, "sc-circ-3", ds_id)
    assert resp.run_id, "未圈定配置不应拦截(闸静默 = 派发照常入队)"


@pytest.mark.asyncio
async def test_rerun_snapshot_governs(client, plate_mock, monkeypatch):
    """重跑按首发快照照查:exec_replay.circledAliases 是唯一圈定来源
    (不回查配置行);取用集 ⊄ 快照圈定 → 同码 409。"""
    h, uid, ds_id = await _setup_pair(client, "circ4", "sc-circ-4")
    await _mk_config(uid, ["s8-alias", "qa1", "qa2"])  # 配置行圈全 —— 快照才是权威
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    from app.services import run_dispatcher as rd
    with pytest.raises(rd.Conflict) as ei:
        await _dispatch(uid, "sc-circ-4", ds_id, exec_replay={
            "execConfigId": None, "slotMap": {}, "carryOverrides": None,
            "circledAliases": ["s8-alias", "qa1"],
        })
    assert ei.value.code == "identity_not_circled"
    assert ei.value.extra == {"aliases": ["qa2"]}
    # 旧行缺键(回放空集)= 当时未圈 → 白名单关闭,派发照常
    resp = await _dispatch(uid, "sc-circ-4", ds_id, exec_replay={
        "execConfigId": None, "slotMap": {}, "carryOverrides": None,
        "circledAliases": [],
    })
    assert resp.run_id


@pytest.mark.asyncio
async def test_hard_gate_unit_three_states(client, plate_mock):
    """函数级三态 + slot 换用目标比对:None/空集跳过;圈内放行;
    换用目标落圈外 → 目标名点名(不是声明名)。"""
    from app.routers.run_precheck import (PrecheckGateError,
                                          precheck_hard_gate)
    h, uid, _ = await _setup_pair(client, "circ5", "sc-circ-5")
    definition = {"steps": _steps2(), "config": {}}
    async with db_module.SessionLocal() as db:
        # None(无配置面)= 存量兼容,不抛
        out = await precheck_hard_gate(
            db, project_id=None, definition=definition, user_id=uid)
        assert sorted(out["authAliases"]) == ["qa1", "qa2", "s8-alias"]
        # 空集 = 未圈定
        await precheck_hard_gate(
            db, project_id=None, definition=definition, user_id=uid,
            circled=frozenset())
        # 圈内放行
        await precheck_hard_gate(
            db, project_id=None, definition=definition, user_id=uid,
            circled=frozenset({"s8-alias", "qa1", "qa2"}))
        # 圈外 → 409 码 + 点名
        with pytest.raises(PrecheckGateError) as ei:
            await precheck_hard_gate(
                db, project_id=None, definition=definition, user_id=uid,
                circled=frozenset({"s8-alias", "qa1"}))
        assert ei.value.code == "identity_not_circled"
        assert ei.value.detail == {"aliases": ["qa2"]}
        # 换用目标比对:qa1 换用 qa2x(已登记),圈定只含声明名 → 目标落圈外
        await _seed_identity("qa2x")
        await _acct(uid, "qa2x")
        with pytest.raises(PrecheckGateError) as ei:
            await precheck_hard_gate(
                db, project_id=None, definition={
                    "steps": [{
                        "kind": "step",
                        "call": {"service": "s8-alias", "method": "GET",
                                 "path": "/x"},
                        "request": {"kind": "request", "body": {
                            "tok": "${auth.qa1.token}"}},
                        "strategy": []}],
                    "config": {}},
                user_id=uid, slot_map={"qa1": "qa2x"},
                circled=frozenset({"s8-alias", "qa1"}))
        assert ei.value.detail == {"aliases": ["qa2x"]}


@pytest.mark.asyncio
async def test_row_binding_outside_circled(client, plate_mock, monkeypatch):
    """行级 @slot:数据集行绑定的取用名落圈外 → 派发段同码 409
    (定义级圈定已过,行引用只在此可见)。"""
    h = await register_and_login(client, "circ6", "pw123456")
    uid = await _uid("circ6")
    await _seed_registry_base()
    await _binding(owner=uid, alias="acct-a", org="A", default=True)
    await _binding(owner=uid, alias="acct-b", system="fin-b", org="B")
    ds_id = await _mk_scenario(client, h, "sc-circ-6", [_STEP])
    r = await _mk_ds(client, h, "sc-circ-6",
                     [{"amount": "1", "@slot.qa1": "acct-b"}])
    assert r.status_code == 201, r.text
    ds_rows = r.json()["datasetId"]
    cfg = await _mk_config(uid, ["s8-alias", "qa1"])
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    from app.services import run_dispatcher as rd
    with pytest.raises(rd.Conflict) as ei:
        await _dispatch(uid, "sc-circ-6", ds_rows, exec_config_id=cfg)
    assert ei.value.code == "identity_not_circled"
    assert ei.value.extra == {"aliases": ["acct-b"]}
    assert cases == []
    assert ds_id != ds_rows


@pytest.mark.asyncio
async def test_precheck_endpoint_not_circled_advisory(client, plate_mock):
    """预检端点 advisory:notCircled 差集 + scheme_valid=False(真拒在
    派发 409);未按执行配置口径 = 空清单。"""
    from app.models.composer_run_scheme import ComposerRunScheme
    from app.services import scheme_store
    h, uid, _ = await _setup_pair(client, "circ7", "sc-circ-7")
    async with db_module.SessionLocal() as db:
        await scheme_store.ensure_default_scheme(db, "sc-circ-7")
        scheme_id = (await db.execute(sa.select(
            ComposerRunScheme.scheme_id).where(
            ComposerRunScheme.scenario_id == "sc-circ-7",
            ComposerRunScheme.is_default.is_(True)))).scalar_one()
    cfg_circled = await _mk_config(uid, ["s8-alias", "qa1"])
    cfg_open = await _mk_config(uid, [], name="不圈7")

    async def _precheck(exec_cfg: int | None) -> dict:
        r = await client.post("/api/run/precheck", headers=h, json=[{
            "scenarioId": "sc-circ-7", "schemeId": scheme_id,
            "execConfigId": exec_cfg}])
        assert r.status_code == 200, r.text
        return r.json()[0]

    one = await _precheck(cfg_circled)
    assert one["notCircled"] == ["qa2"]
    assert one["schemeValid"] is False
    one = await _precheck(cfg_open)
    assert one["notCircled"] == []
    one = await _precheck(None)
    assert one["notCircled"] == []


@pytest.mark.asyncio
async def test_share_missing_name_hint(client, plate_mock):
    """本案(凭证治理 v2 §4.3)分享缺名提示钉位:纯引用场景(无
    config.users)被分享人执行 —— 预检 missingAuths 点名缺的条目、
    builtinAuthShadowed 静默(三条件②不再满足);派发 account_missing
    硬门兜底(个人池口径)。"""
    owner = await register_and_login(client, "circ8o", "pw123456")
    grantee = await register_and_login(client, "circ8g", "pw123456")
    g_id = await _uid("circ8g")
    pid = await _mk_project("circ-proj", members={
        "circ8o": "admin", "circ8g": "member"})
    await _seed_registry_base()
    r = await client.post("/api/scenarios?projectId=%d" % pid, headers=owner,
                          json=make_draft("sc-circ-8", steps=[_STEP],
                                          vars_map={"amount": "1"}))
    assert r.status_code in (200, 201), r.text
    ds_id = (await _mk_ds(client, owner, "sc-circ-8",
                          [{"amount": "1"}])).json()["datasetId"]
    # 属主有账户;被分享人名下无 → 缺名
    await _acct(await _uid("circ8o"), "qa1")

    from app.models.composer_run_scheme import ComposerRunScheme
    from app.services import scheme_store
    async with db_module.SessionLocal() as db:
        await scheme_store.ensure_default_scheme(db, "sc-circ-8")
        scheme_id = (await db.execute(sa.select(
            ComposerRunScheme.scheme_id).where(
            ComposerRunScheme.scenario_id == "sc-circ-8",
            ComposerRunScheme.is_default.is_(True)))).scalar_one()

    r = await client.post("/api/run/precheck", headers=grantee, json=[{
        "scenarioId": "sc-circ-8", "schemeId": scheme_id}])
    assert r.status_code == 200, r.text
    one = r.json()[0]
    assert "qa1" in one["missingAuths"]      # s8-alias(步骤服务条目)同缺,一并点名
    assert one["builtinAuthShadowed"] == []      # 新形态静默(钉「不吵」)

    from app.services import run_dispatcher as rd
    from app.services.scenario_store import get_row
    from app.schemas.scenario_composer import RunRequest
    async with db_module.SessionLocal() as db:
        scen = await get_row(db, "sc-circ-8")
        with pytest.raises(rd.Conflict) as ei:
            await rd.dispatch_target(
                db, g_id,
                RunRequest(scenarioId="sc-circ-8", clientRef="circ8",
                           dataSetIds=[ds_id]),
                rd.RunTarget(scenario_id=scen.scenario_id,
                             payload=scen.payload or {}, kind="scenario"))
    assert ei.value.code == "account_missing"
    assert "qa1" in ei.value.extra["aliases"]
    assert ei.value.extra["credentialSource"] == "personal"
