"""01-03 §4.1 回归:集成模板 owner 身份不替代项目成员关系。

修前事实(对照 known-issue 登记):①``_can_manage`` owner 直通 ——
被移出项目的创建者凭已知 ID 仍可 PATCH/DELETE;②S8 成员闸豁免
owner —— owner 自有实例照跑;③``instance_cred_project_id`` 不复核
holder 成员关系 —— 被移出创建者继续吃项目凭证定时执行。修复后
四面同门:普通项目模板按**当前成员关系**判(owner 含)——
``_can_manage`` 404/403 面、执行前成员闸、凭证池双保险、移除联动
暂停(执行闸是权威,联动 = 即时收口 + 人话通知)。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core import db as db_module
from app.models.integration_task import IntegrationTask
from app.models.project import Project, ProjectMember
from app.models.user import User
from tests.helpers import make_draft, register_and_login, seed_service_runtime
from tests.test_integration_consent_fixes import (  # noqa: F401
    ANCHORED_STEPS, _subscribe, plate_mock,
)


async def _user_id(username: str) -> int:
    async with db_module.SessionLocal() as db:
        return (await db.execute(select(User).where(
            User.username == username))).scalars().one().id


async def _mk_project(name: str, *, members: dict[str, str]) -> int:
    """直插普通项目 + 成员(UPC §20 布景守卫单点:无 admin 自动补
    守夜人 —— 活跃普通项目 ≥1 有效 admin 的库层不变量)。"""
    from tests.helpers import mk_normal_project

    return await mk_normal_project(name, members)


async def _mk_project_tpl(
    client, plate_mock, *, project: str, owner: str,
    extra_members: dict[str, str] | None = None,
) -> tuple[dict, int, int]:
    """属主(成员角色)建项目场景 + 项目模板 → (owner_headers, pid, tid)。

    修订钉 1.0#1(consent_fixes 同款):声明 working 会在成员闸之前被
    working_preview 早退(集成拒绝触发预览执行),到不了要测的闸。"""
    from tests.test_integration_consent_fixes import FULLS
    plate_mock.fulls.update(FULLS)
    owner_h = await register_and_login(client, owner, "pw123456")
    members = {owner: "member", **(extra_members or {})}
    pid = await _mk_project(project, members=members)
    await seed_service_runtime("jira-svc")
    r = await client.post(f"/api/scenarios?projectId={pid}", headers=owner_h,
                          json=make_draft(f"sc-{project}",
                                          steps=ANCHORED_STEPS,
                                          plate={"jira": "1.0#1"},
                                          system=["jira"]))
    assert r.status_code in (200, 201), r.text
    r = await client.post("/api/integration/tasks", headers=owner_h, json={
        "name": f"{project}-tpl", "scenarioId": f"sc-{project}",
        "identityMode": "personal", "triggerCron": "0 3 * * *",
        "projectId": pid})
    assert r.status_code == 201, r.text
    return owner_h, pid, r.json()["id"]


async def _inst(tpl_id: int, holder: int) -> IntegrationTask | None:
    async with db_module.SessionLocal() as db:
        return (await db.execute(select(IntegrationTask).where(
            IntegrationTask.template_id == tpl_id,
            IntegrationTask.holder_id == holder))).scalar()


async def test_removed_owner_patch_delete_404(client, plate_mock):
    """被移出的创建者:PATCH/DELETE → 404(不可见先于管理,不泄露
    存在性;修前 owner 直通 = 仍可改/删)。成员内为正控。"""
    admin_h = await register_and_login(client, "om_adm1", "pw123456")
    owner_h, pid, tid = await _mk_project_tpl(
        client, plate_mock, project="om-p1", owner="om_own1")
    # 正控:属主仍在成员内 → PATCH 可用
    r = await client.patch(f"/api/integration/tasks/{tid}", headers=owner_h,
                           json={"name": "om-p1-tpl-r2"})
    assert r.status_code == 200, r.text
    # admin 移出属主
    r = await client.delete(
        f"/api/projects/{pid}/members/{await _user_id('om_own1')}",
        headers=admin_h)
    assert r.status_code == 204, r.text
    # 移出后:模板已不可见 → 404(修前 = 403 之外的「照常可改」)
    r = await client.patch(f"/api/integration/tasks/{tid}", headers=owner_h,
                           json={"name": "om-p1-tpl-x"})
    assert r.status_code == 404, r.text
    r = await client.delete(f"/api/integration/tasks/{tid}", headers=owner_h)
    assert r.status_code == 404, r.text


async def test_removed_owner_instance_gated_on_claim(client, plate_mock):
    """执行前成员闸不再豁免 owner:被移出的属主自有实例,认领即
    paused/made_private(S8 权威面;修前 consent_gate 排除 owner)。"""
    from app.services import integration_runner as ir

    admin_h = await register_and_login(client, "om_adm2", "pw123456")
    owner_h, pid, tid = await _mk_project_tpl(
        client, plate_mock, project="om-p2", owner="om_own2")
    uid = await _user_id("om_own2")
    inst_id = (await _inst(tid, uid)).id
    r = await client.delete(f"/api/projects/{pid}/members/{uid}",
                            headers=admin_h)
    assert r.status_code == 204, r.text
    # 联动钩子已把 idle 实例暂停;模拟「漏网路径」置回 idle 再认领 ——
    # 闸必须独立于钩子兜死(与 test_made_private_gate_covers_leak_paths
    # 同法:直调 run_instance 绕过 HTTP 面)
    async with db_module.SessionLocal() as db:
        row = await db.get(IntegrationTask, inst_id)
        row.state = "idle"
        await db.commit()
    await ir.run_instance(inst_id)
    inst = await _inst(tid, uid)
    assert inst.state == "paused"
    assert inst.paused_reason == "made_private"


async def test_member_removal_hook_pauses_owner_and_subscriber(
        client, plate_mock):
    """remove_member 联动:被移出成员在本项目模板上的持有实例(含其
    自建 owner 实例 + 订阅实例)即时暂停并通知(执行闸兜底之上的
    提前收口)。"""
    admin_h = await register_and_login(client, "om_adm3", "pw123456")
    sub_h = await register_and_login(client, "om_sub3", "pw123456")
    owner_h, pid, tid = await _mk_project_tpl(
        client, plate_mock, project="om-p3", owner="om_own3",
        extra_members={"om_sub3": "member"})
    sub_uid = await _user_id("om_sub3")
    r = await _subscribe(client, sub_h, tid)
    assert r.status_code in (200, 201), r.text
    owner_uid = await _user_id("om_own3")
    assert (await _inst(tid, sub_uid)).state == "idle"

    # 移出订阅者 → 其实例暂停
    r = await client.delete(f"/api/projects/{pid}/members/{sub_uid}",
                            headers=admin_h)
    assert r.status_code == 204, r.text
    inst = await _inst(tid, sub_uid)
    assert inst.state == "paused"
    assert inst.paused_reason == "made_private"

    # 移出属主 → 其自有实例同样暂停(§4.1:属主身份不替代成员关系)
    r = await client.delete(f"/api/projects/{pid}/members/{owner_uid}",
                            headers=admin_h)
    assert r.status_code == 204, r.text
    inst = await _inst(tid, owner_uid)
    assert inst.state == "paused"
    assert inst.paused_reason == "made_private"


async def test_instance_cred_project_id_requires_membership(
        client, plate_mock):
    """凭证池双保险:credential_source='project' 的实例,holder(含
    owner)不再是项目成员 → 回落个人池(None;修前不复核,被移出
    创建者继续吃项目凭证)。"""
    from app.services.integration_runner import instance_cred_project_id

    admin_h = await register_and_login(client, "om_adm4", "pw123456")
    owner_h, pid, tid = await _mk_project_tpl(
        client, plate_mock, project="om-p4", owner="om_own4")
    uid = await _user_id("om_own4")
    async with db_module.SessionLocal() as db:
        tpl = await db.get(IntegrationTask, tid)
        inst = await db.get(IntegrationTask, (await _inst(tid, uid)).id)
        inst.credential_source = "project"
        await db.commit()
        # 成员内 → 项目池
        assert await instance_cred_project_id(db, inst, tpl) == pid
    # 移出后 → None(不吃项目池;执行闸通常先拦,这是闸序外兜底)
    await client.delete(f"/api/projects/{pid}/members/{uid}",
                        headers=admin_h)
    async with db_module.SessionLocal() as db:
        tpl = await db.get(IntegrationTask, tid)
        inst = await db.get(IntegrationTask, (await _inst(tid, uid)).id)
        inst.state = "idle"   # 凭证闸与暂停态无关,直判
        await db.commit()
        assert await instance_cred_project_id(db, inst, tpl) is None
