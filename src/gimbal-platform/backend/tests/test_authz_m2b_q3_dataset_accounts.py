"""authz M2b Q3:数据集按账号驱动(行账号列 ``@slot.<槽>`` = 绑定名)。

钉子:
* 写面:账号列豁免变量调色板;槽须被场景引用(否则 422 undeclared_slot);
* 派发:逐行注入该行绑定(``${auth}`` 与 ``${slot}`` 同取);缺绑定 / 槽不
  符 → 409 dataset_binding_missing 并列行;项目池同口径;行值不进 vars;
  ``config_json.rowBindings`` 留档;
* suite 编排 409(graph 单元行带账号列)。
"""
from __future__ import annotations
import pytest  # noqa: E402

import sqlalchemy as sa

from app.core import db as db_module
from app.core.security import fernet_encrypt
from app.models import AuthAccount, Environment

from .helpers import make_draft, register_and_login, wait_until
from .test_authz_s8_project_credentials import (
    _STEP, _mk_project, _seed_project_scenario, _uid,
)
from .test_run_m1_capabilities import _patch_launch_capture, _run_payload
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401


async def _seed_alias() -> None:
    """注册底座(默认环境 + 主档 + 条目 s8-alias/qa1)—— 幂等。"""
    from .test_authz_s8_project_credentials import _seed_registry_base
    await _seed_registry_base()


async def _binding(*, owner: int | None = None, project: int | None = None,
                   alias: str, system: str = "fin", org: str,
                   default: bool = False) -> int:
    """行级绑定名 = 条目名:种条目 alias(username-ref)+ 池内账户。
    返回账户 id(config_json.rowBindings 的绑定标识)。"""
    from app.models import Service, ServiceIdentity
    from sqlalchemy import select as _sel
    async with db_module.SessionLocal() as db:
        env = (await db.execute(_sel(Environment.id).where(
            Environment.is_default.is_(True)))).scalar_one()
        if (await db.execute(_sel(Service.id).where(
                Service.name == "fin-svc"))).scalar_one_or_none() is None:
            db.add(Service(name="fin-svc", system="fin", kind="plate"))
        if (await db.execute(_sel(ServiceIdentity.id).where(
                ServiceIdentity.alias_name == alias))
                ).scalar_one_or_none() is None:
            db.add(ServiceIdentity(alias_name=alias, base_service="fin-svc",
                                   env_id=env, ref_mode="username",
                                   ref_username=alias))
        a = AuthAccount(
            owner_id=owner, project_id=project, system="fin", env_id=env,
            username=alias, password_enc=fernet_encrypt("p"),
            account_fields={"orgNo": org}, is_default=default)
        db.add(a)
        await db.commit()
        return a.id


async def _mk_ds(client, h, sid: str, rows: list[dict]):
    return await client.post(f"/api/scenarios/{sid}/data-sets", headers=h,
                             json={"name": "acct", "rows": rows})


class TestAccountColumns:
    async def test_write_validation(self, client):
        h = await register_and_login(client, "q3_w", "pw123456")
        await _seed_alias()
        r = await client.post("/api/scenarios", headers=h, json=make_draft(
            "sc-q3w", steps=[_STEP], vars_map={"amount": "1"}))
        assert r.status_code in (200, 201), r.text
        r = await _mk_ds(client, h, "sc-q3w",
                         [{"amount": "1", "@slot.qa1": "acct-a"}])
        assert r.status_code == 201, r.text
        r = await _mk_ds(client, h, "sc-q3w",
                         [{"amount": "1", "@slot.nope": "acct-a"}])
        assert r.status_code == 422 and "undeclared_slot" in r.text
        r = await _mk_ds(client, h, "sc-q3w", [{"bogus": "1"}])
        assert r.status_code == 422 and "undeclared_var" in r.text

    async def test_per_row_injection_and_missing(
            self, client, plate_mock: PlateMock, monkeypatch):
        plate_mock.behaviour = "echo"
        h = await register_and_login(client, "q3_r", "pw123456")
        await _seed_alias()
        uid = await _uid("q3_r")
        await _binding(owner=uid, alias="acct-a", system="fin", org="A",
                       default=True)
        id_b = await _binding(owner=uid, alias="acct-b", system="fin-b",
                              org="B")
        r = await client.post("/api/scenarios", headers=h, json=make_draft(
            "sc-q3r", steps=[_STEP], vars_map={"amount": "1"}))
        assert r.status_code in (200, 201), r.text
        r = await _mk_ds(client, h, "sc-q3r", [
            {"amount": "1"},                         # 不覆盖 → 默认绑定 A
            {"amount": "2", "@slot.qa1": "acct-b"}])
        ds_id = r.json()["datasetId"]
        cases: list[dict] = []
        _patch_launch_capture(monkeypatch, cases)
        r = await client.post("/api/runs", headers=h, json=_run_payload(
            scenarioId="sc-q3r", dataSetIds=[ds_id]))
        assert r.status_code == 201, r.text
        ex_id = r.json()["executionId"]
        await wait_until(lambda: len(cases) >= 2)
        orgs = sorted(c["steps"][0]["request"]["body"]["org"] for c in cases)
        users = sorted(c["config"]["users"]["qa1"]["username"] for c in cases)
        assert orgs == ["A", "B"]
        # 行级换绑 = 条目 acct-a/acct-b(注入标签 qa1 不变;登录口在
        # 实例,url 不再随账户行走)
        assert users == ["acct-a", "acct-b"]
        # 账号列不进 vars
        assert all("@slot.qa1" not in (c["config"].get("vars") or {})
                   for c in cases)
        from app.models.execution import Execution
        async with db_module.SessionLocal() as db:
            cfg = (await db.get(Execution, ex_id)).config_json
        assert cfg["rowBindings"] == {f"{ds_id}:1": {"qa1": id_b}}
        # 缺绑定 → 409 并列行
        r = await _mk_ds(client, h, "sc-q3r", [
            {"amount": "3", "@slot.qa1": "acct-zz"}])
        ds2 = r.json()["datasetId"]
        r = await client.post("/api/runs", headers=h, json=_run_payload(
            scenarioId="sc-q3r", dataSetIds=[ds2]))
        assert r.status_code == 409, r.text
        det = r.json()["detail"]
        assert det["code"] == "dataset_binding_missing"
        assert det["rows"] == [{"datasetId": ds2, "rowIndex": 0,
                                "slot": "qa1", "alias": "acct-zz"}]

    async def test_project_pool_rows(
            self, client, plate_mock: PlateMock, monkeypatch):
        plate_mock.behaviour = "echo"
        h = await register_and_login(client, "q3_p", "pw123456")
        pid = await _mk_project("q3-proj", members={"q3_p": "member"})
        await _seed_project_scenario(client, h, pid, sid="sc-q3p")
        await _binding(project=pid, alias="pa", system="fin", org="PA",
                       default=True)
        await _binding(project=pid, alias="pb", system="fin-b", org="PB")
        # 个人池同名绑定不被取用(池 = 项目)
        await _binding(owner=await _uid("q3_p"), alias="pb", system="fin",
                       org="ME", default=True)
        # 场景 vars 为空 → 只放账号列
        r = await _mk_ds(client, h, "sc-q3p", [{"@slot.qa1": "pb"}])
        assert r.status_code == 201, r.text
        ds_id = r.json()["datasetId"]
        cases: list[dict] = []
        _patch_launch_capture(monkeypatch, cases)
        r = await client.post("/api/runs", headers=h, json=_run_payload(
            scenarioId="sc-q3p", dataSetIds=[ds_id],
            credentialSource="project"))
        assert r.status_code == 201, r.text
        await wait_until(lambda: len(cases) >= 1)
        assert cases[0]["steps"][0]["request"]["body"]["org"] == "PB"


async def test_graph_unit_with_account_column_rejected(client):
    """suite 编排(graph 单元行)带账号列 → dataset_binding_unsupported。"""
    import pytest

    from app.services.graph_dispatch import (GraphDispatchError,
                                             resolve_graph_units)
    h = await register_and_login(client, "q3_g", "pw123456")
    await _seed_alias()
    await client.post("/api/scenarios", headers=h, json=make_draft(
        "sc-q3g", steps=[_STEP], vars_map={"amount": "1"}))
    r = await _mk_ds(client, h, "sc-q3g",
                     [{"amount": "1", "@slot.qa1": "acct-a"}])
    ds_id = r.json()["datasetId"]
    async with db_module.SessionLocal() as db:
        with pytest.raises(GraphDispatchError) as ei:
            await resolve_graph_units(db, [{
                "ref": "u1", "scenarioId": "sc-q3g",
                "row": {"datasetId": ds_id, "rowIndex": 0}}],
                await _uid("q3_g"))
    assert "dataset_binding_unsupported" in str(ei.value)
