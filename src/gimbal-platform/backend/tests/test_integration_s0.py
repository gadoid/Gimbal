"""S0 先修批(个人侧方案 v1.4 §2):①方案/数据集归属收口(G-A);
②任一别名缺凭证即暂停(G-G,共享 ``_resolve_exec_auths`` 行为不动)。

- 归属:create/PATCH 对不属于场景的 ``schemeId`` 422;runner 对跨场景
  ``scheme_id``(绕过路由闸的直改)忽略并回退本场景默认方案,跨场景
  数据集不注入;
- 缺凭证:两别名缺其一 → ``paused/missing_credential`` 且 last_error
  只列缺失别名;
- 共享解析函数:部分缺失仍返回已解析子集、不抛(常规测试执行链依赖)。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core import db as db_module
from app.core.security import fernet_encrypt
from app.models.auth_session import AuthSession
from app.models.composer_data_set import ComposerDataSet
from app.models.composer_run_scheme import ComposerRunScheme
from app.models.integration_task import IntegrationTask
from app.models.user import User
from tests.helpers import make_draft, register_and_login
from tests.test_scenario_composer_plate_integration import (  # noqa: F401
    plate_mock,
)

PLAIN_STEPS = [{
    "kind": "step", "description": "探活",
    "call": {"protocol": "http", "service": "svc",
             "method": "GET", "path": "/x", "headers": {}},
    "request": {"kind": "request", "body": {}}, "strategy": [],
}]

TWO_AUTH_STEPS = [{
    "kind": "step", "description": "双凭证",
    "call": {"protocol": "http", "service": "svc",
             "method": "GET", "path": "/x",
             "headers": {"Authorization": "${auth.gitlab.token}",
                         "X-Jira": "${auth.jira.token}"}},
    "request": {"kind": "request", "body": {}}, "strategy": [],
}]


def _task_body(sid: str, **over) -> dict:
    body = {"name": "S0", "scenarioId": sid, "identityMode": "personal",
            "triggerCron": "*/5 * * * *", "resultPolicy": "latest",
            "visibility": "private"}
    body.update(over)
    return body


async def _mk_scenario(client, h, sid: str, steps: list) -> None:
    r = await client.post("/api/scenarios", headers=h,
                          json=make_draft(sid, steps=steps))
    assert r.status_code in (200, 201), r.text


async def _insert_scheme(scenario_id: str, scheme_id: str, *, payload: dict,
                         is_default: bool = False) -> None:
    async with db_module.SessionLocal() as db:
        db.add(ComposerRunScheme(
            scheme_id=scheme_id, scenario_id=scenario_id,
            name=f"s0-{scheme_id}", is_default=is_default, payload=payload))
        await db.commit()


async def _insert_dataset(scenario_id: str, dataset_id: str,
                          rows: list) -> None:
    async with db_module.SessionLocal() as db:
        db.add(ComposerDataSet(
            dataset_id=dataset_id, scenario_id=scenario_id,
            name=f"s0-{dataset_id}", rows=rows))
        await db.commit()


async def _user_id(username: str) -> int:
    async with db_module.SessionLocal() as db:
        return (await db.execute(select(User).where(
            User.username == username))).scalars().one().id


async def test_create_and_patch_reject_foreign_scheme(client):
    """S0①:创建/PATCH 的方案归属闸 —— 他场景 rs-NNN 422 响亮拒绝。"""
    h = await register_and_login(client, "s0_alice", "pw123456")
    await _mk_scenario(client, h, "sc-s0a", PLAIN_STEPS)
    await _mk_scenario(client, h, "sc-s0b", PLAIN_STEPS)
    await _insert_scheme("sc-s0b", "rs-901", payload={})
    await _insert_scheme("sc-s0a", "rs-902", payload={})

    r = await client.post("/api/integration/tasks", headers=h, json=_task_body(
        "sc-s0a", schemeId="rs-901"))
    assert r.status_code == 422, r.text
    assert "scheme_not_owned" in r.text

    r = await client.post("/api/integration/tasks", headers=h, json=_task_body(
        "sc-s0a", schemeId="rs-902"))
    assert r.status_code == 201, r.text
    tid = r.json()["id"]

    r = await client.patch(f"/api/integration/tasks/{tid}", headers=h,
                           json={"schemeId": "rs-901"})
    assert r.status_code == 422, r.text
    assert "scheme_not_owned" in r.text
    # 显式空串 = 清除,维持原语义
    r = await client.patch(f"/api/integration/tasks/{tid}", headers=h,
                           json={"schemeId": ""})
    assert r.status_code == 200, r.text


async def test_runner_scopes_scheme_and_dataset_to_scenario(
        client, monkeypatch):
    """S0①:runner 纵深防御 —— 直改 scheme_id 指向他场景方案(枚举
    rs-NNN 的利用形态)→ 方案被忽略回退本场景默认方案:幽灵别名
    authAlias 不进注入清单(否则在 compose 前就暂停)、他场景数据集
    首行不注入;对照组:本场景方案选自有数据集 → 正常注入。"""
    from app.services import integration_runner as ir

    h = await register_and_login(client, "s0_runner", "pw123456")
    await _mk_scenario(client, h, "sc-s0r", PLAIN_STEPS)
    await _mk_scenario(client, h, "sc-s0v", PLAIN_STEPS)   # "他人"场景
    # sc-s0r 回退落点 = 场景创建时自动生成的默认方案(不另插,
    # uq_run_scheme_default 唯一)
    await _insert_dataset("sc-s0r", "ds-own", [{"who": "me"}])
    await _insert_scheme("sc-s0r", "rs-own", payload={
        "dataSetSelection": [{"datasetId": "ds-own"}]})
    await _insert_dataset("sc-s0v", "ds-foreign", [{"who": "victim"}])
    await _insert_scheme("sc-s0v", "rs-foreign", payload={
        "serviceBindings": {"svc": {"authAlias": "ghost"}},
        "dataSetSelection": [{"datasetId": "ds-foreign"}]})

    r = await client.post("/api/integration/tasks", headers=h,
                          json=_task_body("sc-s0r"))
    assert r.status_code == 201, r.text
    tid = r.json()["id"]

    from app.services import run_dispatcher as rd

    captured: list[dict] = []

    def _fake_compose(payload, vars_):
        captured.append(dict(vars_))
        raise RuntimeError("stop-before-convert")

    # compose_scenario 是 run_instance 内的函数级导入,
    # 打桩须落在源模块 run_dispatcher 上
    monkeypatch.setattr(rd, "compose_scenario", _fake_compose)

    async def _point_scheme(scheme_id: str) -> None:
        # 直改模板行(id == tid 且 template_id IS NULL;此前误选实例行)
        async with db_module.SessionLocal() as db:
            row = await db.get(IntegrationTask, tid)
            assert row is not None and row.template_id is None
            row.scheme_id = scheme_id
            await db.commit()

    await _point_scheme("rs-foreign")
    r = await client.post(f"/api/integration/tasks/{tid}/run", headers=h)
    assert r.status_code == 200, r.text
    # compose 被调到 = 没有因幽灵别名停在凭证段;注入变量为空 =
    # 他场景数据集未注入
    assert len(captured) == 1
    assert captured[0] == {}

    await _point_scheme("rs-own")
    r = await client.post(f"/api/integration/tasks/{tid}/run", headers=h)
    assert r.status_code == 200, r.text
    assert captured[-1] == {"who": "me"}


async def test_partial_missing_credential_pauses(client):
    """S0②:两别名缺其一 → paused/missing_credential,一步不执行;
    last_error 只列缺失别名(S0 前此场景会照跑到步骤级报错)。"""
    h = await register_and_login(client, "s0_partial", "pw123456")
    await _mk_scenario(client, h, "sc-s0p", TWO_AUTH_STEPS)
    r = await client.post("/api/integration/tasks", headers=h,
                          json=_task_body("sc-s0p"))
    assert r.status_code == 201, r.text
    tid = r.json()["id"]

    uid = await _user_id("s0_partial")
    async with db_module.SessionLocal() as db:
        db.add(AuthSession(
            owner_id=uid, alias="gitlab", url="http://127.0.0.1:1",
            username_enc=fernet_encrypt("u"),
            password_enc=fernet_encrypt("p")))
        await db.commit()

    r = await client.post(f"/api/integration/tasks/{tid}/run", headers=h)
    assert r.status_code == 200, r.text

    async with db_module.SessionLocal() as db:
        inst = (await db.execute(select(IntegrationTask).where(
            IntegrationTask.template_id == tid))).scalars().one()
        assert inst.state == "paused"
        assert inst.paused_reason == "missing_credential"
        assert "jira" in (inst.last_error or "")
        assert "gitlab" not in (inst.last_error or "")


async def test_resolve_exec_auths_stays_lenient_on_partial(client):
    """S0② 验收:共享解析函数行为不变 —— 部分缺失不抛不少给,返回
    已解析子集(常规测试执行链依赖的宽松语义)。"""
    from app.services.run_dispatcher import _resolve_exec_auths

    h = await register_and_login(client, "s0_shared", "pw123456")
    uid = await _user_id("s0_shared")
    async with db_module.SessionLocal() as db:
        db.add(AuthSession(
            owner_id=uid, alias="only-one", url="http://127.0.0.1:1",
            username_enc=fernet_encrypt("u"),
            password_enc=fernet_encrypt("p")))
        await db.commit()

    resolved = await _resolve_exec_auths(
        db_module.SessionLocal, uid, ["only-one", "not-there"])
    assert [a.alias for a in resolved] == ["only-one"]
