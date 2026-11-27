"""UPC M2 领域验收(v2.10 §5/§16.1/§20.3/§14.2 —— AC-08/39/40/41/44/45/46)。

覆盖面(对应 M2 退出条件):

* **AC-08 账户组合**:CRUD / 条目保存面校验 / 默认切换 / revision
  语义(仅条目 +1)/ 引用统计(显式列)/ 删除保护(409 + 引用清单)
  / 能力闸(公共项目 422)/ 写门(私有属主 ∨ 项目可写成员;Admin+
  非成员不旁路)。
* **§16.1 / AC-39 绑定收敛**:DTO ``accountComboId`` ↔ 显式列双向
  映射(payload 不保存绑定);跨区 422;复制恒剥 + 阻塞继承。
* **§20.3 / AC-40/41 修复状态**:blocked 经导入/处置产生,普通
  PATCH 不得解除;修复命令(rebind_combo / confirm_no_combo)带
  expected_revision 原子提交,行级审计(scheme_repair_events)同事务;
  库层非法状态组合直接拒绝。
* **AC-44 诊断授权投影**:调用者可读目标组合 → 精确 combo_cross_zone;
  否则一律通用投影;修复命令不得成为存在性探针。
* **AC-45/46 资产包最小闭环**:导出(秘密剥离)→ 原子恢复(组合
  依赖确定性映射 / 默认候选先验证零提交 / 修复状态持久化)→ 预检
  blocked 在凭证解析前返回(凭证调用数为零)→ 幂等重放 / 摘要冲突。
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.helpers import (default_space_id, make_draft, mk_user_with_space,
                            register_and_login)

async def _mk_scheme(client: AsyncClient, h: dict, sid: str, name: str,
                     *, combo_id: "int | None" = None,
                     default: bool = False) -> str:
    body: dict = {
        "name": name, "isDefault": default,
        "dataSetSelection": [], "injectionEntryIds": [],
        "serviceBindings": {}, "options": {
            "step_from": None, "step_to": None, "n_runs": 1,
            "parallel": 1, "subscribe": None},
    }
    if combo_id is not None:
        body["accountComboId"] = combo_id
    r = await client.post(f"/api/scenarios/{sid}/run-schemes",
                          headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()["schemeId"]


class TestAccountComboCrud:
    """AC-08:组合 CRUD / 条目校验 / 默认 / revision / 引用统计 / 删除保护。"""

    async def test_crud_gates_and_revision(self, client: AsyncClient):
        from app.core import db as db_module
        from .conftest import seed_identity_fixture

        h = await register_and_login(client, "m2c_own", "pw123456")
        uid = (await _uid(client, "m2c_own"))
        async with db_module.SessionLocal() as s:
            await seed_identity_fixture(
                s, alias="m2-qa", username="u", password="p",
                service="fin-service", owner_id=uid)
            await seed_identity_fixture(
                s, alias="m2-qa2", username="u2", password="p",
                service="fin-service", owner_id=uid, is_default=False)
            space = await default_space_id(s, uid)
            await s.commit()

        # 建组合(条目合法)
        r = await client.post(f"/api/projects/{space}/account-combos",
                              headers=h, json={
                                  "name": "测试组合", "entries": [
                                      {"service": "fin-service",
                                       "alias": "m2-qa"}]})
        assert r.status_code == 201, r.text
        combo_id = r.json()["id"]
        assert r.json()["revision"] == 1 and r.json()["isDefault"] is False

        # 形状违例(空服务键)→ 域码;重复服务 → 域码
        for bad in ({"service": "", "alias": "m2-qa"}, None):
            entries = [{"service": "fin-service", "alias": "m2-qa"},
                       (bad or {"service": "fin-service",
                                "alias": "m2-qa"})]
            r = await client.post(
                f"/api/projects/{space}/account-combos",
                headers=h, json={"name": "坏组合", "entries": entries})
            assert r.status_code == 422, r.text
            assert (r.json()["detail"]["code"]
                    == "account_combo_entry_invalid"), r.text

        # 异基础服务(保存面复用既有码族)→ binding_alias_mismatch
        r = await client.post(
            f"/api/projects/{space}/account-combos",
            headers=h, json={"name": "错源组合", "entries": [
                {"service": "svc2", "alias": "m2-qa"}]})
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["code"] == "binding_alias_mismatch"

        # 未知别名 → 保存面复用 binding_alias_unknown
        r = await client.post(
            f"/api/projects/{space}/account-combos", headers=h,
            json={"name": "悬空", "entries": [
                {"service": "fin-service", "alias": "no-such"}]})
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["code"] == "binding_alias_unknown"

        # 同名 → 409
        r = await client.post(
            f"/api/projects/{space}/account-combos", headers=h,
            json={"name": "测试组合", "entries": []})
        assert r.status_code == 409, r.text

        # 元数据修改不加 revision;条目替换 +1
        r = await client.patch(
            f"/api/projects/{space}/account-combos/{combo_id}",
            headers=h, json={"description": "v2"})
        assert r.status_code == 200 and r.json()["revision"] == 1
        # 同值替换不加;条目实质变化(alias 换绑)+1
        r = await client.patch(
            f"/api/projects/{space}/account-combos/{combo_id}",
            headers=h, json={"entries": [
                {"service": "fin-service", "alias": "m2-qa"}]})
        assert r.status_code == 200 and r.json()["revision"] == 1
        r = await client.patch(
            f"/api/projects/{space}/account-combos/{combo_id}",
            headers=h, json={"entries": [
                {"service": "fin-service", "alias": "m2-qa2"}]})
        assert r.status_code == 200 and r.json()["revision"] == 2

        # set-default(唯一默认)
        r = await client.post(
            f"/api/projects/{space}/account-combos/{combo_id}/set-default",
            headers=h)
        assert r.status_code == 200 and r.json()["isDefault"] is True

        # 列表含引用计数(显式列)
        r = await client.get(f"/api/projects/{space}/account-combos",
                            headers=h)
        assert r.status_code == 200
        [row] = [c for c in r.json() if c["id"] == combo_id]
        assert row["referenceCount"] == 0

    async def test_write_gates_and_capability(self, client: AsyncClient):
        from tests.helpers import mk_normal_project

        # 先注册(mk_user 直插的密码哈希与登录口令不一致),后挂项目
        h_mem = await register_and_login(client, "m2g_mem", "pw123456")
        h_ro = await register_and_login(client, "m2g_ro", "pw123456")
        h_out = await register_and_login(client, "m2g_out", "pw123456")
        pid = await mk_normal_project("m2-gate", members={
            "m2g_mem": "member", "m2g_ro": "user"})

        # 项目可写成员可建;只读角色 403;非成员(含平台 Admin)404
        r = await client.post(f"/api/projects/{pid}/account-combos",
                              headers=h_mem, json={"name": "项目组合"})
        assert r.status_code == 201, r.text
        r = await client.post(f"/api/projects/{pid}/account-combos",
                              headers=h_ro, json={"name": "只读建"})
        assert r.status_code == 403, r.text
        r = await client.post(f"/api/projects/{pid}/account-combos",
                              headers=h_out, json={"name": "路人建"})
        assert r.status_code == 404, r.text

        # 公共项目:§7 能力关闭 → API 拒绝(AC-26)
        from app.core import db as db_module

        async with db_module.SessionLocal() as s:
            from sqlalchemy import select

            from app.models.project import Project

            pub = (await s.execute(select(Project.id).where(
                Project.kind == "public"))).scalar()
        r = await client.post(f"/api/projects/{pub}/account-combos",
                              headers=h_out, json={"name": "公共组合"})
        assert r.status_code == 422, r.text
        # 公共项目两条 422 均成立:创建门(public_project_create_
        # forbidden)先拒 —— 同为「关闭能力后 API 同样拒绝」的落法
        assert (r.json()["detail"]["code"]
                in ("public_project_create_forbidden",
                    "account_combo_capability_disabled"))

    async def test_delete_in_use_protection(self, client: AsyncClient):
        from app.core import db as db_module
        from .conftest import seed_identity_fixture

        h = await register_and_login(client, "m2d_own", "pw123456")
        uid = await _uid(client, "m2d_own")
        async with db_module.SessionLocal() as s:
            await seed_identity_fixture(
                s, alias="m2d-qa", username="u", password="p",
                service="fin-service", owner_id=uid)
            space = await default_space_id(s, uid)
            await s.commit()
        r = await client.post(f"/api/projects/{space}/account-combos",
                              headers=h, json={"name": "被引用组合",
                                               "entries": [
                                                   {"service": "fin-service",
                                                    "alias": "m2d-qa"}]})
        combo_id = r.json()["id"]

        await client.post("/api/scenarios", headers=h,
                          json=make_draft("sc-m2d"))
        scheme_id = await _mk_scheme(client, h, "sc-m2d", "绑定方案",
                                     combo_id=combo_id)

        # 被引用 → 409 + 引用方案清单(不级联解绑)
        r = await client.delete(
            f"/api/projects/{space}/account-combos/{combo_id}",
            headers=h)
        assert r.status_code == 409, r.text
        assert r.json()["detail"]["code"] == "account_combo_in_use"
        [ref] = r.json()["detail"]["schemes"]
        assert ref["schemeId"] == scheme_id and ref["scenarioId"] == "sc-m2d"

        # 解绑后可删;列表引用计数归零
        r = await client.put(
            f"/api/scenarios/sc-m2d/run-schemes/{scheme_id}",
            headers=h, json={
                "name": "绑定方案", "accountComboId": None,
                "dataSetSelection": [], "injectionEntryIds": [],
                "serviceBindings": {}, "options": {
                    "step_from": None, "step_to": None, "n_runs": 1,
                    "parallel": 1, "subscribe": None}})
        assert r.status_code == 200 and r.json()["accountComboId"] is None
        r = await client.delete(
            f"/api/projects/{space}/account-combos/{combo_id}",
            headers=h)
        assert r.status_code == 204


class TestSchemeBindingConvergence:
    """§16.1 / AC-39:DTO↔显式列双向映射;跨区拒绝;复制恒剥+继承阻塞。"""

    async def test_roundtrip_and_zone_gates(self, client: AsyncClient):
        from app.core import db as db_module
        from .conftest import seed_identity_fixture

        h = await register_and_login(client, "m2b_a", "pw123456")
        h_b = await register_and_login(client, "m2b_b", "pw123456")
        uid_a = await _uid(client, "m2b_a")
        uid_b = await _uid(client, "m2b_b")
        async with db_module.SessionLocal() as s:
            await seed_identity_fixture(
                s, alias="m2b-qa", username="u", password="p",
                service="fin-service", owner_id=uid_a)
            space_a = await default_space_id(s, uid_a)
            space_b = await default_space_id(s, uid_b)
            await s.commit()

        combo_a = (await client.post(
            f"/api/projects/{space_a}/account-combos", headers=h,
            json={"name": "甲组合", "entries": [
                {"service": "fin-service", "alias": "m2b-qa"}]})
        ).json()["id"]
        combo_b = (await client.post(
            f"/api/projects/{space_b}/account-combos", headers=h_b,
            json={"name": "乙组合"})).json()["id"]

        await client.post("/api/scenarios", headers=h,
                          json=make_draft("sc-m2b"))
        scheme_id = await _mk_scheme(client, h, "sc-m2b", "绑定方案",
                                     combo_id=combo_a)

        # 双向映射:wire 回带 accountComboId;payload 不含绑定键
        r = await client.get(f"/api/scenarios/sc-m2b/run-schemes",
                            headers=h)
        [row] = [x for x in r.json() if x["schemeId"] == scheme_id]
        assert row["accountComboId"] == combo_a
        async with db_module.SessionLocal() as s:
            from sqlalchemy import select

            from app.models.composer_run_scheme import ComposerRunScheme

            raw = (await s.execute(select(ComposerRunScheme.payload).where(
                ComposerRunScheme.scheme_id == scheme_id))).scalar_one()
            assert "accountComboId" not in raw
            row_db = (await s.execute(select(ComposerRunScheme).where(
                ComposerRunScheme.scheme_id == scheme_id))).scalar_one()
            assert row_db.project_id == space_a
            assert row_db.repair_status == "ready"
            assert row_db.scheme_uid

        # 跨区绑定:可读但异项目的组合 → scope_mismatch(A 是另一普通
        # 项目成员,组合可读、不同区);不可读(他人私有空间)→ 统一
        # not_found,不泄露存在性
        from tests.helpers import mk_normal_project

        await mk_user_with_space("m2b_c", role="user")
        pid = await mk_normal_project("m2b-proj", members={
            "m2b_a": "member", "m2b_c": "member"})
        combo_p = (await client.post(
            f"/api/projects/{pid}/account-combos", headers=h,
            json={"name": "项目组合"})).json()["id"]
        r = await client.put(
            f"/api/scenarios/sc-m2b/run-schemes/{scheme_id}", headers=h,
            json={"name": "绑定方案", "accountComboId": combo_p,
                  "dataSetSelection": [], "injectionEntryIds": [],
                  "serviceBindings": {}, "options": {
                      "step_from": None, "step_to": None, "n_runs": 1,
                      "parallel": 1, "subscribe": None}})
        assert r.status_code == 422, r.text
        assert (r.json()["detail"]["code"]
                == "account_combo_scope_mismatch"), r.text
        r = await client.put(
            f"/api/scenarios/sc-m2b/run-schemes/{scheme_id}", headers=h,
            json={"name": "绑定方案", "accountComboId": combo_b,
                  "dataSetSelection": [], "injectionEntryIds": [],
                  "serviceBindings": {}, "options": {
                      "step_from": None, "step_to": None, "n_runs": 1,
                      "parallel": 1, "subscribe": None}})
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["code"] == "account_combo_not_found"
        # 不存在/不可读 → 统一 422(不泄露存在性)
        r = await client.put(
            f"/api/scenarios/sc-m2b/run-schemes/{scheme_id}", headers=h,
            json={"name": "绑定方案", "accountComboId": 10 ** 9,
                  "dataSetSelection": [], "injectionEntryIds": [],
                  "serviceBindings": {}, "options": {
                      "step_from": None, "step_to": None, "n_runs": 1,
                      "parallel": 1, "subscribe": None}})
        assert r.status_code == 422
        assert (r.json()["detail"]["code"] == "account_combo_not_found")

    async def test_copy_strips_binding_and_inherits_blocked(
            self, client: AsyncClient):
        from app.core import db as db_module
        from app.models.composer_run_scheme import ComposerRunScheme
        from app.services import scheme_repair
        from sqlalchemy import select

        h = await register_and_login(client, "m2cp_a", "pw123456")
        uid = await _uid(client, "m2cp_a")
        async with db_module.SessionLocal() as s:
            space = await default_space_id(s, uid)
            await s.commit()
        combo_id = (await client.post(
            f"/api/projects/{space}/account-combos", headers=h,
            json={"name": "复制组合"})).json()["id"]

        await client.post("/api/scenarios", headers=h,
                          json=make_draft("sc-m2cp"))
        ready_id = await _mk_scheme(client, h, "sc-m2cp", "正常方案",
                                    combo_id=combo_id)
        blocked_id = await _mk_scheme(client, h, "sc-m2cp", "待修方案")

        # 服务层置 blocked(导入/处置面;测试注入状态)
        async with db_module.SessionLocal() as s:
            row = (await s.execute(select(ComposerRunScheme).where(
                ComposerRunScheme.scheme_id == blocked_id))).scalar_one()
            await scheme_repair.mark_blocked(
                s, row, reason="combo_missing", action="import.blocked",
                source_combo_ref="combo:legacy",
                actor_id=uid, actor_name="m2cp_a")
            await s.commit()

        # 复制到自己的另一空间:绑定恒剥;blocked 继承
        r = await client.post("/api/scenarios/sc-m2cp/copy", headers=h)
        assert r.status_code in (200, 201), r.text
        copy_sid = r.json()["meta"]["scenarioId"]
        async with db_module.SessionLocal() as s:
            rows = {r_.scheme_id: r_ for r_ in (
                await s.execute(select(ComposerRunScheme).where(
                    ComposerRunScheme.scenario_id == copy_sid))).scalars()}
        names = {r_.name: r_ for r_ in rows.values()}
        assert names["正常方案"].account_combo_id is None      # 恒剥
        assert names["正常方案"].repair_status == "ready"
        assert names["待修方案"].repair_status == "blocked"    # 继承
        assert names["待修方案"].repair_reason == "combo_missing"

        # 普通 PUT 不得清除阻塞 / 改绑 blocked
        r = await client.put(
            f"/api/scenarios/{copy_sid}/run-schemes/"
            f"{names['待修方案'].scheme_id}",
            headers=h, json={"name": "待修方案", "accountComboId": combo_id,
                             "dataSetSelection": [], "injectionEntryIds": [],
                             "serviceBindings": {}, "options": {
                                 "step_from": None, "step_to": None,
                                 "n_runs": 1, "parallel": 1,
                                 "subscribe": None}})
        assert r.status_code == 409, r.text
        assert r.json()["detail"]["code"] == "scheme_repair_required"


class TestRepairCommandsAndProjection:
    """§20.3 / AC-40/41/44:修复命令 / 事务审计 / 诊断授权投影。"""

    async def _blocked_scheme(self, client, h, *, uid, reason,
                              sid="sc-m2r",
                              source_ref="combo:legacy",
                              resolved_combo_id=None,
                              resolved_project_id=None):
        from app.core import db as db_module
        from app.models.composer_run_scheme import ComposerRunScheme
        from app.services import scheme_repair
        from sqlalchemy import select

        # 同场景多次置 blocked:方案名须唯一
        await client.post("/api/scenarios", headers=h,
                          json=make_draft(sid))
        self._seq = getattr(self, "_seq", 0) + 1
        scheme_id = await _mk_scheme(
            client, h, sid, f"待修{self._seq}")
        async with db_module.SessionLocal() as s:
            row = (await s.execute(select(ComposerRunScheme).where(
                ComposerRunScheme.scheme_id == scheme_id))).scalar_one()
            await scheme_repair.mark_blocked(
                s, row, reason=reason, action="import.blocked",
                source_combo_ref=source_ref,
                resolved_combo_id=resolved_combo_id,
                resolved_project_id=resolved_project_id,
                actor_id=uid, actor_name="seed")
            await s.commit()
        return scheme_id

    async def test_rebind_happy_path_and_conflicts(self, client):
        from app.core import db as db_module
        from app.models.composer_run_scheme import ComposerRunScheme
        from app.models.scheme_repair import SchemeRepairEvent
        from sqlalchemy import select

        h = await register_and_login(client, "m2r_a", "pw123456")
        uid = await _uid(client, "m2r_a")
        async with db_module.SessionLocal() as s:
            space = await default_space_id(s, uid)
            await s.commit()
        combo_id = (await client.post(
            f"/api/projects/{space}/account-combos", headers=h,
            json={"name": "修复目标组合"})).json()["id"]
        scheme_id = await self._blocked_scheme(
            client, h, uid=uid, reason="combo_missing")

        # 非法 revision → 409;blocked 才可修
        r = await client.post(
            f"/api/scenarios/sc-m2r/run-schemes/{scheme_id}/rebind-combo",
            headers=h, json={"comboId": combo_id, "expectedRevision": 99})
        assert r.status_code == 409, r.text
        assert r.json()["detail"]["code"] == "scheme_revision_conflict"

        r = await client.post(
            f"/api/scenarios/sc-m2r/run-schemes/{scheme_id}/confirm-no-combo",
            headers=h, json={"expectedRevision": 2, "reason": "不再依赖"})
        assert r.status_code == 200, r.text
        # ready 后修复命令再入 → 409 not_blocked
        r = await client.post(
            f"/api/scenarios/sc-m2r/run-schemes/{scheme_id}/rebind-combo",
            headers=h, json={"comboId": combo_id, "expectedRevision": 3})
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "scheme_not_blocked"

        # 再置 blocked → rebind 合法腿(修订 + 审计同事务)
        scheme_id2 = await self._blocked_scheme(
            client, h, uid=uid, reason="combo_missing")
        r = await client.post(
            f"/api/scenarios/sc-m2r/run-schemes/{scheme_id2}/rebind-combo",
            headers=h, json={"comboId": combo_id, "expectedRevision": 2})
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["repairStatus"] == "ready" and out["accountComboId"] == \
            combo_id

        async with db_module.SessionLocal() as s:
            row = (await s.execute(select(ComposerRunScheme).where(
                ComposerRunScheme.scheme_id == scheme_id2))).scalar_one()
            assert row.repair_status == "ready"
            assert row.repair_reason is None
            assert row.account_combo_id == combo_id
            # 行级审计(同事务落账;old/new 全套)
            ev = (await s.execute(select(SchemeRepairEvent).where(
                SchemeRepairEvent.scheme_id == scheme_id2
            ).order_by(SchemeRepairEvent.id.desc()))).scalars().first()
            assert ev is not None and ev.action == "rebind_combo"
            assert ev.old_status == "blocked" and ev.new_status == "ready"
            assert ev.old_reason == "combo_missing"
            assert ev.old_combo_id is None and ev.new_combo_id == combo_id
            assert ev.old_revision == 2 and ev.new_revision == 3

        # 跨区组合 → 422;不可读组合 → 404(存在性不泄露)
        h_b = await register_and_login(client, "m2r_b", "pw123456")
        uid_b = await _uid(client, "m2r_b")
        async with db_module.SessionLocal() as s:
            space_b = await default_space_id(s, uid_b)
            await s.commit()
        other = (await client.post(
            f"/api/projects/{space_b}/account-combos", headers=h_b,
            json={"name": "外域组合"})).json()["id"]
        scheme_id3 = await self._blocked_scheme(
            client, h, uid=uid, reason="combo_missing", sid="sc-m2r-a2")
        r = await client.post(
            f"/api/scenarios/sc-m2r-a2/run-schemes/{scheme_id3}"
            f"/rebind-combo",
            headers=h, json={"comboId": other, "expectedRevision": 2})
        assert r.status_code == 404, r.text
        assert (r.json()["detail"]["code"]
                == "account_combo_not_found"), r.text
        r = await client.post(
            f"/api/scenarios/sc-m2r-a2/run-schemes/{scheme_id3}"
            f"/rebind-combo",
            headers=h, json={"comboId": 10 ** 9, "expectedRevision": 2})
        assert r.status_code == 404
        assert r.json()["detail"]["code"] == "account_combo_not_found"

        # confirm_no_combo:理由必填
        scheme_id4 = await self._blocked_scheme(
            client, h, uid=uid, reason="combo_missing")
        r = await client.post(
            f"/api/scenarios/sc-m2r/run-schemes/"
            f"{scheme_id4}/confirm-no-combo",
            headers=h, json={"expectedRevision": 2, "reason": ""})
        assert r.status_code == 422
        r = await client.post(
            f"/api/scenarios/sc-m2r/run-schemes/"
            f"{scheme_id4}/confirm-no-combo",
            headers=h, json={"expectedRevision": 2, "reason": "改用步骤直引"})
        assert r.status_code == 200

    async def test_projection_visibility_rules(self, client):
        """AC-44:可读目标 → 精确 cross_zone;否则一律通用投影。"""
        from tests.helpers import mk_normal_project

        await register_and_login(client, "m2p_mem", "pw123456")
        await register_and_login(client, "m2p_out", "pw123456")
        pid = await mk_normal_project("m2-proj", members={
            "m2p_mem": "member", "m2p_out": "user"})
        # 跨区目标组合(普通项目内;诊断记录指向它)
        h_mem = await register_and_login(client, "m2p_mem", "pw123456")
        combo_x = (await client.post(
            f"/api/projects/{pid}/account-combos", headers=h_mem,
            json={"name": "跨区组合"})).json()["id"]

        # ① 可读目标(项目成员)→ 精确 combo_cross_zone
        h = await register_and_login(client, "m2p_a", "pw123456")
        uid = await _uid(client, "m2p_a")
        await mk_proj_member(pid, "m2p_a")
        scheme_id = await self._blocked_scheme(
            client, h, uid=uid, reason="combo_cross_zone",
            resolved_combo_id=combo_x, resolved_project_id=pid)
        r = await client.get(f"/api/scenarios/sc-m2r/run-schemes",
                             headers=h)
        [row] = [x for x in r.json()
                 if x["schemeId"] == scheme_id]
        assert row["repairStatus"] == "blocked"
        assert row["repairReason"] == "combo_cross_zone"

        # ② 非目标项目成员 → 通用投影(不可见目标 ≈ 不存在)
        h2 = await register_and_login(client, "m2p_b", "pw123456")
        uid2 = await _uid(client, "m2p_b")
        scheme_id2 = await self._blocked_scheme(
            client, h2, uid=uid2, reason="combo_cross_zone",
            sid="sc-m2r-b",
            resolved_combo_id=combo_x, resolved_project_id=pid)
        r = await client.get(f"/api/scenarios/sc-m2r-b/run-schemes",
                             headers=h2)
        [row2] = [x for x in r.json()
                  if x["schemeId"] == scheme_id2]
        assert row2["repairReason"] == "combo_dependency_invalid"

        # ③ combo_missing → 恒通用投影(目标不存在无人可读)
        scheme_id3 = await self._blocked_scheme(
            client, h, uid=uid, reason="combo_missing", sid="sc-m2r-a2")
        r = await client.get(f"/api/scenarios/sc-m2r-a2/run-schemes",
                             headers=h)
        [row3] = [x for x in r.json()
                  if x["schemeId"] == scheme_id3]
        assert row3["repairReason"] == "combo_dependency_invalid"

    async def test_db_rejects_illegal_repair_states(self, client):
        """AC-41:直接 SQL 非法状态组合(ready+reason / blocked+combo /
        未知原因)全部拒绝。"""
        from sqlalchemy import text
        from sqlalchemy.exc import IntegrityError

        from app.core import db as db_module

        h = await register_and_login(client, "m2n_a", "pw123456")
        await client.post("/api/scenarios", headers=h,
                         json=make_draft("sc-m2n"))
        scheme_id = await _mk_scheme(client, h, "sc-m2n", "非法状态")
        bad_states = [
            "UPDATE composer_run_schemes SET repair_reason = 'combo_missing'"
            " WHERE scheme_id = :s",                      # ready+reason
            "UPDATE composer_run_schemes SET repair_status = 'blocked'"
            " WHERE scheme_id = :s",                      # blocked无原因
            "UPDATE composer_run_schemes SET repair_status = 'blocked',"
            " repair_reason = 'combo_nope' WHERE scheme_id = :s",  # 未列原因
        ]
        for sql in bad_states:
            async with db_module.SessionLocal() as s:
                with pytest.raises(IntegrityError):
                    await s.execute(text(sql), {"s": scheme_id})
                    await s.commit()
                await s.rollback()

    async def test_repair_command_revision_race_serialized(self, client):
        """评审 M1 回归:expected_revision 检查-递增在行锁(FOR UPDATE)
        内串行 —— 同 revision 的两笔并发修复命令恰一笔生效;败者在锁
        释放后读到已提交终态(ready)被拒,不再双双通过同一 revision
        后互相覆盖(lost update)。"""
        import asyncio

        from sqlalchemy import select

        from app.core import db as db_module
        from app.models.composer_run_scheme import ComposerRunScheme
        from app.services import scheme_repair
        from app.services.scheme_repair import RepairCommandError

        h = await register_and_login(client, "m2r_race", "pw123456")
        uid = await _uid(client, "m2r_race")
        async with db_module.SessionLocal() as s:
            space = await default_space_id(s, uid)
            await s.commit()
        combo_id = (await client.post(
            f"/api/projects/{space}/account-combos", headers=h,
            json={"name": "竞态组合"})).json()["id"]
        scheme_id = await self._blocked_scheme(
            client, h, uid=uid, reason="combo_missing")
        user = type("U", (), {"id": uid, "display_name": "racer"})()

        async with db_module.SessionLocal() as s1,                 db_module.SessionLocal() as s2:
            sch1 = (await s1.execute(select(ComposerRunScheme).where(
                ComposerRunScheme.scheme_id == scheme_id))).scalar_one()
            sch2 = (await s2.execute(select(ComposerRunScheme).where(
                ComposerRunScheme.scheme_id == scheme_id))).scalar_one()
            rev = sch1.revision
            await scheme_repair.rebind_combo(
                s1, sch1, user=user, combo_id=combo_id,
                expected_revision=rev)          # 行锁在 s1 未提交事务内
            lose_task = asyncio.ensure_future(
                scheme_repair.rebind_combo(
                    s2, sch2, user=user, combo_id=combo_id,
                    expected_revision=rev))     # 入口 refresh 挂在行锁上
            await asyncio.sleep(0.05)           # 让败者先挂进锁队列
            await s1.commit()                   # 提交并释放锁
            with pytest.raises(RepairCommandError) as ei:
                await asyncio.wait_for(lose_task, 10)
            # 败者锁释放后读到已提交终态:ready → not_blocked(等价拒收,
            # 与 revision 冲突同一 409 面 —— 关键是不再双双通过)
            assert ei.value.code == "scheme_not_blocked"
            await s2.rollback()

        # 恰一笔生效:绑定/状态落定,revision 恰 +1
        async with db_module.SessionLocal() as s:
            row = (await s.execute(select(ComposerRunScheme).where(
                ComposerRunScheme.scheme_id == scheme_id))).scalar_one()
            assert row.account_combo_id == combo_id
            assert row.repair_status == "ready"
            assert row.revision == rev + 1


class TestPrecheckRepairGate:
    """§20.3 装配闸最小链路(M2:precheck):blocked 在凭证解析前返回。"""

    async def test_blocked_returns_before_credential_resolution(
            self, client: AsyncClient, monkeypatch):
        """§20.3 装配闸 + 评审 P1-2/P2-15 收口:**非属主执行人** + 场景
        含 ``config.users`` 的真实泄露路径探针 —— blocked 预检对
        ``resolve_exec_auths``(解密/身份解析)**零调用**;ready 对照腿
        照常解析(自证探针有效)。修前外层无条件跑 builtin_auth_shadowed,
        blocked 也会解密 1 个凭证。"""
        from sqlalchemy import select

        from app.core import db as db_module
        from app.models.composer_run_scheme import ComposerRunScheme
        from app.services import run_prepare, scheme_repair
        from tests.helpers import mk_normal_project, seed_legacy_users

        h_own = await register_and_login(client, "m2pre_own", "pw123456")
        h_exec = await register_and_login(client, "m2pre_exec", "pw123456")
        uid_own = await _uid(client, "m2pre_own")
        pid = await mk_normal_project("m2pre-proj", {
            "m2pre_own": "admin", "m2pre_exec": "member"})
        await client.post(f"/api/scenarios?projectId={pid}",
                          headers=h_own, json=make_draft("sc-m2pre"))
        # 存量形态:场景携带明文内置凭证基座(§7 老行)
        await seed_legacy_users("sc-m2pre", {
            "qa-legacy": {"username": "u", "password": "p"}})
        scheme_id = await _mk_scheme(client, h_own, "sc-m2pre", "待修")
        ready_scheme_id = await _mk_scheme(
            client, h_own, "sc-m2pre", "ready对照")
        async with db_module.SessionLocal() as s:
            row = (await s.execute(select(ComposerRunScheme).where(
                ComposerRunScheme.scheme_id == scheme_id))).scalar_one()
            await scheme_repair.mark_blocked(
                s, row, reason="combo_missing", action="import.blocked",
                actor_id=uid_own, actor_name="seed")
            await s.commit()

        calls = {"resolve": 0}
        orig = run_prepare.resolve_exec_auths

        async def counting(factory, *a, **k):
            calls["resolve"] += 1
            return await orig(factory, *a, **k)

        monkeypatch.setattr(run_prepare, "resolve_exec_auths", counting)
        import app.services.env_chain as _ec
        import app.services.run_dispatcher as rd

        def _boom(*a, **k):
            raise AssertionError("blocked 方案不得进入凭证/装配解析")

        # 独立 MonkeyPatch 实例(解析面炸点只作用于 blocked 腿;ready
        # 对照腿合法解析,解除后再跑 —— fresh_db 持有的测试级 monkeypatch
        # 不可整体 undo,见 conftest 注记)
        mp = pytest.MonkeyPatch()
        mp.setattr(rd, "filter_injection_entries", _boom)
        mp.setattr(_ec, "resolve_execution_tag", _boom)

        # 非属主执行人预检 blocked 方案:辅助凭证解析零调用(P1-2)
        r = await client.post("/api/run/precheck", headers=h_exec, json=[
            {"scenarioId": "sc-m2pre", "schemeId": scheme_id}])
        assert r.status_code == 200, r.text
        [res] = r.json()
        assert res["found"] is True and res["schemeFound"] is True
        assert res["schemeValid"] is False
        assert res["repairBlocked"] is True
        assert res["repairCode"] == "scheme_repair_required"
        assert res["repairReason"] == "combo_dependency_invalid"
        assert calls["resolve"] == 0, "blocked 预检不得解析/解密凭证"
        mp.undo()

        # ready 对照腿:同一非属主执行人预检 ready 方案 —— 解析照常
        # 发生(证明探针在位,blocked 的零调用是闸的功劳不是布景失效)
        r = await client.post("/api/run/precheck", headers=h_exec, json=[
            {"scenarioId": "sc-m2pre", "schemeId": ready_scheme_id}])
        assert r.status_code == 200, r.text
        assert calls["resolve"] >= 1, "ready 对照腿应触发辅助凭证解析"

        # 修复面带 revision(§20.3:稳定错误码 + revision)
        async with db_module.SessionLocal() as s:
            row = (await s.execute(select(ComposerRunScheme).where(
                ComposerRunScheme.scheme_id == scheme_id))).scalar_one()
        assert res["repairRevision"] == row.revision


class TestAssetBundleRoundtrip:
    """AC-45/46:导出 → 原子恢复 → 预检;幂等 / 摘要冲突 / 修复状态。"""

    async def _seed_source(self, client, tag: str):
        """导出侧布景:场景 + 数据集 + 默认/回归方案 + 组合绑定。

        ``tag``:每用例独立用户名(注册速率限制按账号计数)。"""
        from app.core import db as db_module
        from .conftest import seed_identity_fixture

        me = f"m2x_{tag}"
        h = await register_and_login(client, me, "pw123456")
        uid = await _uid(client, me)
        async with db_module.SessionLocal() as s:
            await seed_identity_fixture(
                s, alias="m2x-qa", username="u", password="p",
                service="fin-service", owner_id=uid)
            space = await default_space_id(s, uid)
            await s.commit()
        combo_id = (await client.post(
            f"/api/projects/{space}/account-combos", headers=h,
            json={"name": "导出组合", "entries": [
                {"service": "fin-service", "alias": "m2x-qa"}]})
        ).json()["id"]

        await client.post("/api/scenarios", headers=h,
                          json=make_draft("sc-m2x", vars_map={"x": 0}))
        # 数据集(回归方案带行级选择)
        r = await client.post(
            "/api/scenarios/sc-m2x/data-sets", headers=h,
            json={"name": "数据A", "rows": [{"x": 1}, {"x": 2}]})
        assert r.status_code in (200, 201), r.text
        ds_id = r.json()["datasetId"]

        # 默认方案由场景创建钩子自动物化;此处只建回归方案
        qa_id = await _mk_scheme(client, h, "sc-m2x", "回归方案",
                                 combo_id=combo_id)
        r = await client.put(
            f"/api/scenarios/sc-m2x/run-schemes/{qa_id}", headers=h,
            json={"name": "回归方案", "accountComboId": combo_id,
                  "dataSetSelection": [{"datasetId": ds_id,
                                        "rowIndexes": [0]}],
                  "injectionEntryIds": [],
                  "serviceBindings": {}, "options": {
                      "step_from": None, "step_to": None, "n_runs": 1,
                      "parallel": 1, "subscribe": None}})
        assert r.status_code == 200, r.text
        return h, space, combo_id, ds_id, qa_id

    async def test_roundtrip_idempotent_and_conflict(self, client):
        h, _space, _combo, _ds, _qa = await self._seed_source(client, "a")

        # 导出(读闸;秘密剥离;包标识/组合依赖随行)
        r = await client.get("/api/scenarios/sc-m2x/asset-bundle",
                             headers=h)
        assert r.status_code == 200, r.text
        bundle = r.json()
        assert bundle["format"] == "gimbal-upc-asset"
        assert bundle["comboDependencies"], "回归方案的组合依赖随包"
        assert not (bundle["scenario"]["definition"].get("config") or {}
                    ).get("users"), "明文凭证不外带"
        assert bundle["defaultSchemeId"]

        # 恢复到另一用户的默认空间
        h_b = await register_and_login(client, "m2x_b", "pw123456")
        uid_b = await _uid(client, "m2x_b")
        from app.core import db as db_module

        async with db_module.SessionLocal() as s:
            space_b = await default_space_id(s, uid_b)
            await s.commit()
        r = await client.post(f"/api/projects/{space_b}/asset-bundles",
                              headers=h_b, json=bundle)
        assert r.status_code == 201, r.text
        report = r.json()
        assert report["restoredBindings"] == 1
        assert report["blockedSchemes"] == []
        assert report["datasets"] >= 1
        new_sid = report["scenarioId"]

        # 数量/默认项/引用映射逐项比对(§14.2)
        async with db_module.SessionLocal() as s:
            from sqlalchemy import select

            from app.models.account_combo import AccountCombo
            from app.models.composer_run_scheme import ComposerRunScheme

            schemes = (await s.execute(select(ComposerRunScheme).where(
                ComposerRunScheme.scenario_id == new_sid))).scalars().all()
            assert len(schemes) == 2
            by_name = {x.name: x for x in schemes}
            assert by_name["默认方案"].is_default is True
            qa = by_name["回归方案"]
            assert qa.is_default is False
            assert qa.account_combo_id is not None       # 确定性绑定
            assert qa.repair_status == "ready"
            combo = await s.get(AccountCombo, qa.account_combo_id)
            assert combo.project_id == space_b
            assert combo.payload["entries"] == [
                {"service": "fin-service", "alias": "m2x-qa"}]
            assert qa.project_id == space_b

        # 同键同摘要 = 重放,返回已提交映射
        r = await client.post(f"/api/projects/{space_b}/asset-bundles",
                              headers=h_b, json=bundle)
        assert r.status_code == 200, r.text
        assert r.json()["replayed"] is True
        assert r.json()["scenarioId"] == new_sid

        # 同键不同摘要 → 409 供处置
        tampered = dict(bundle)
        tampered["schemes"] = list(bundle["schemes"]) + [{
            "schemeId": "rs-evil", "name": "篡改", "isDefault": False,
            "payload": {}}]
        r = await client.post(f"/api/projects/{space_b}/asset-bundles",
                              headers=h_b, json=tampered)
        assert r.status_code == 409, r.text
        assert r.json()["detail"]["code"] == "asset_bundle_conflict"

    async def test_skip_combos_blocked_then_precheck_and_rebind(
            self, client):
        """组合不随包恢复 → blocked(combo_missing)持久化;预检在
        凭证解析前返回;修复命令解封。"""
        h, _space, _combo, _ds, _qa = await self._seed_source(client, "b")
        bundle = (await client.get(
            "/api/scenarios/sc-m2x/asset-bundle", headers=h)).json()
        # 组合条目依赖的别名在目标侧未登记 → 无法合法恢复(§14.2);
        # 直接跳过恢复(skipCombos)→ 显式解绑待修复
        bundle["skipCombos"] = True

        h_b = await register_and_login(client, "m2y_b", "pw123456")
        uid_b = await _uid(client, "m2y_b")
        from app.core import db as db_module

        async with db_module.SessionLocal() as s:
            space_b = await default_space_id(s, uid_b)
            await s.commit()
        r = await client.post(f"/api/projects/{space_b}/asset-bundles",
                              headers=h_b, json=bundle)
        assert r.status_code == 201, r.text
        report = r.json()
        assert report["blockedSchemes"], "依赖组合的方案待修复"
        new_sid = report["scenarioId"]
        qa_new = next(x for x in report["schemeIds"]
                      if x != report["defaultSchemeId"])

        # 持久化 blocked(重启语义:独立会话读取)
        async with db_module.SessionLocal() as s:
            from sqlalchemy import select

            from app.models.composer_run_scheme import ComposerRunScheme
            from app.models.scheme_repair import (SchemeRepairDiagnosis,
                                                  SchemeRepairEvent)

            row = (await s.execute(select(ComposerRunScheme).where(
                ComposerRunScheme.scheme_id == qa_new))).scalar_one()
            assert row.repair_status == "blocked"
            assert row.repair_reason == "combo_missing"
            diag = await s.get(SchemeRepairDiagnosis, row.scheme_id)
            assert diag is not None and diag.source_combo_ref
            ev = (await s.execute(select(SchemeRepairEvent).where(
                SchemeRepairEvent.scheme_id == row.scheme_id))).scalars()
            assert any(e.action == "import.blocked" for e in ev)

        # 预检:凭证解析前返回授权投影
        r = await client.post("/api/run/precheck", headers=h_b, json=[
            {"scenarioId": new_sid, "schemeId": qa_new}])
        assert r.status_code == 200, r.text
        [res] = r.json()
        assert res["repairBlocked"] is True
        assert res["repairReason"] == "combo_dependency_invalid"
        assert res["schemeValid"] is False

        # 修复命令解封(目标侧先建合法组合)
        combo_b = (await client.post(
            f"/api/projects/{space_b}/account-combos", headers=h_b,
            json={"name": "目标组合"})).json()["id"]
        async with db_module.SessionLocal() as s:
            from sqlalchemy import select

            from app.models.composer_run_scheme import ComposerRunScheme

            row = (await s.execute(select(ComposerRunScheme).where(
                ComposerRunScheme.scheme_id == qa_new))).scalar_one()
            rev = row.revision
        r = await client.post(
            f"/api/scenarios/{new_sid}/run-schemes/{qa_new}/rebind-combo",
            headers=h_b, json={"comboId": combo_b, "expectedRevision": rev})
        assert r.status_code == 200, r.text
        assert r.json()["repairStatus"] == "ready"

    async def test_default_with_selections_zero_commit(self, client):
        """§14.2:含数据集/注入条目的默认候选导致**零提交**(整体
        回滚,无半成品)。"""
        h, _space, _combo, ds_id, _qa = await self._seed_source(client, "c")
        bundle = (await client.get(
            "/api/scenarios/sc-m2x/asset-bundle", headers=h)).json()
        # 把默认候选指向携带选择的方案 → 恢复整包拒绝(P1-6:改指同时
        # 清掉原默认方案的包内标记,defaultSchemeId 是唯一权威)
        bundle["defaultSchemeId"] = next(
            s["schemeId"] for s in bundle["schemes"]
            if not s["isDefault"])
        bundle["schemes"] = [
            dict(s, isDefault=(s["schemeId"] == bundle["defaultSchemeId"]))
            for s in bundle["schemes"]]

        h_b = await register_and_login(client, "m2z_b", "pw123456")
        uid_b = await _uid(client, "m2z_b")
        from app.core import db as db_module

        async with db_module.SessionLocal() as s:
            space_b = await default_space_id(s, uid_b)
            await s.commit()
        r = await client.post(f"/api/projects/{space_b}/asset-bundles",
                              headers=h_b, json=bundle)
        assert r.status_code == 422, r.text
        assert (r.json()["detail"]["code"]
                == "asset_bundle_default_invalid")
        # 零提交:目标侧无新场景 / 无方案 / 无台账
        async with db_module.SessionLocal() as s:
            from sqlalchemy import func, select

            from app.models.composer_scenario import ComposerScenario
            from app.models.scenario_asset_import import (
                ScenarioAssetImport)

            n = (await s.execute(select(func.count()).select_from(
                ComposerScenario).where(
                    ComposerScenario.scenario_id != "sc-m2x"))).scalar_one()
            assert n == 0
            n = (await s.execute(select(func.count()).select_from(
                ScenarioAssetImport))).scalar_one()
            assert n == 0

    async def test_cross_zone_mapping_blocked(self, client):
        """显式 comboId 映射指向**跨区**组合 → blocked combo_cross_zone;
        可读目标者见精确原因,其余通用投影(AC-44 全链)。"""
        from app.core import db as db_module
        from tests.helpers import mk_normal_project, mk_user_with_space

        h, _space, _combo, _ds, _qa = await self._seed_source(client, "d")
        bundle = (await client.get(
            "/api/scenarios/sc-m2x/asset-bundle", headers=h)).json()

        h_mem = await register_and_login(client, "m2w_mem", "pw123456")
        pid = await mk_normal_project("m2-proj-x", members={
            "m2w_mem": "member"})
        combo_x = (await client.post(
            f"/api/projects/{pid}/account-combos", headers=h_mem,
            json={"name": "外域"})).json()["id"]
        # 映射把回归方案指到跨区组合
        qa_old = next(s["schemeId"] for s in bundle["schemes"]
                      if not s["isDefault"])
        bundle["comboIdMappings"] = {qa_old: combo_x}

        h_b = await register_and_login(client, "m2w_b", "pw123456")
        uid_b = await _uid(client, "m2w_b")
        async with db_module.SessionLocal() as s:
            space_b = await default_space_id(s, uid_b)
            await s.commit()
        r = await client.post(f"/api/projects/{space_b}/asset-bundles",
                              headers=h_b, json=bundle)
        assert r.status_code == 201, r.text
        report = r.json()
        assert report["restoredBindings"] == 0
        qa_new = next(x for x in report["schemeIds"]
                      if x != report["defaultSchemeId"])

        from sqlalchemy import select

        from app.models.composer_run_scheme import ComposerRunScheme

        async with db_module.SessionLocal() as s:
            row = (await s.execute(select(ComposerRunScheme).where(
                ComposerRunScheme.scheme_id == qa_new))).scalar_one()
            assert row.repair_reason == "combo_cross_zone"
        # 恢复者不可读目标 → 通用投影
        r = await client.get(
            f"/api/scenarios/{report['scenarioId']}/run-schemes",
            headers=h_b)
        [w] = [x for x in r.json() if x["schemeId"] == qa_new]
        assert w["repairReason"] == "combo_dependency_invalid"

    # ── AC-46 故障注入 + 并发重试 ────────────────────────────────────
    async def _zero_residue(self, s, space_b: int) -> None:
        """整场景零提交断言:目标项目内场景 / 方案 / 数据集 / 台账 /
        修复事件一件不落(无半成品,AC-46)。"""
        from sqlalchemy import func, select

        from app.models.composer_data_set import ComposerDataSet
        from app.models.composer_run_scheme import ComposerRunScheme
        from app.models.composer_scenario import ComposerScenario
        from app.models.scenario_asset_import import ScenarioAssetImport
        from app.models.scheme_repair import SchemeRepairEvent

        sids = select(ComposerScenario.scenario_id).where(
            ComposerScenario.project_id == space_b).scalar_subquery()
        assert (await s.execute(select(
            func.count()).select_from(
            ComposerScenario).where(
            ComposerScenario.project_id == space_b))).scalar_one() == 0
        assert (await s.execute(select(
            func.count()).select_from(
            ComposerRunScheme).where(
            ComposerRunScheme.project_id == space_b))).scalar_one() == 0
        assert (await s.execute(select(
            func.count()).select_from(
            ComposerDataSet).where(
            ComposerDataSet.scenario_id.in_(sids)))).scalar_one() == 0
        assert (await s.execute(select(
            func.count()).select_from(
            ScenarioAssetImport).where(
            ScenarioAssetImport.project_id == space_b))).scalar_one() == 0
        assert (await s.execute(select(
            func.count()).select_from(
            SchemeRepairEvent))).scalar_one() == 0

    async def test_fault_at_scheme_write_zero_residue(self, client):
        """AC-46:写 Scheme 处注入故障 → 整场景零提交(含幂等台账)。
        第二个方案写前抛错,回滚后无任何半成品;重试(解除注入)成功。

        注:注入用独立 MonkeyPatch 实例 —— fresh_db 持有的测试级
        monkeypatch 绑定了 app 引擎/会话工厂,不可整体 undo。"""
        from app.core import db as db_module
        from app.services import scheme_store
        from app.services import scenario_asset_package as asset_pkg

        h, _space, _combo, _ds, _qa = await self._seed_source(client, "f1")
        bundle = (await client.get(
            "/api/scenarios/sc-m2x/asset-bundle", headers=h)).json()
        h_b = await register_and_login(client, "m2x_fb1", "pw123456")
        uid_b = (await client.get("/api/auth/me", headers=h_b)
                 ).json()["user"]["id"]

        calls = {"n": 0}
        orig = scheme_store.normalized

        def boom(payload):
            calls["n"] += 1
            if calls["n"] >= 2:      # 默认方案已写,回归方案写前炸
                raise RuntimeError("injected: scheme write failure")
            return orig(payload)

        mp = pytest.MonkeyPatch()
        mp.setattr(scheme_store, "normalized", boom)
        async with db_module.SessionLocal() as s:
            from app.models.user import User

            owner = await s.get(User, uid_b)
            space_b = await default_space_id(s, uid_b)
            with pytest.raises(RuntimeError):
                await asset_pkg.restore_bundle(
                    s, project_id=space_b, bundle=bundle, user=owner)
            await s.rollback()
            await self._zero_residue(s, space_b)
        mp.undo()

        # 重试(同包同摘要)从零开始照常恢复 —— 失败不留下任何状态
        r = await client.post(f"/api/projects/{space_b}/asset-bundles",
                              headers=h_b, json=bundle)
        assert r.status_code == 201, r.text
        assert r.json()["restoredBindings"] == 1

    async def test_fault_at_repair_audit_zero_residue(
            self, client, monkeypatch):
        """AC-46:事务内审计写入处注入故障(修复事件落库前)→ 同样
        整场景零提交:恢复单元「导入必须原子写入绑定、修复状态及审计,
        不能先提交空绑定再补状态」(§14.2)。"""
        from app.core import db as db_module
        from app.services import scheme_repair
        from app.services import scenario_asset_package as asset_pkg

        h, _space, _combo, _ds, _qa = await self._seed_source(client, "f2")
        bundle = (await client.get(
            "/api/scenarios/sc-m2x/asset-bundle", headers=h)).json()
        bundle["skipCombos"] = True          # 回归方案走 blocked → 触审计
        h_b = await register_and_login(client, "m2x_fb2", "pw123456")
        uid_b = (await client.get("/api/auth/me", headers=h_b)
                 ).json()["user"]["id"]

        async def boom(*_a, **_k):
            raise RuntimeError("injected: repair audit failure")

        monkeypatch.setattr(scheme_repair, "mark_blocked", boom)
        async with db_module.SessionLocal() as s:
            from app.models.user import User

            owner = await s.get(User, uid_b)
            space_b = await default_space_id(s, uid_b)
            with pytest.raises(RuntimeError):
                await asset_pkg.restore_bundle(
                    s, project_id=space_b, bundle=bundle, user=owner)
            await s.rollback()
            await self._zero_residue(s, space_b)
            await s.commit()

    async def test_concurrent_same_key_retry_converges(self, client):
        """AC-46 并发重试:同键并发两笔恢复 —— 唯一约束裁定先提交者
        (201);败者整笔回滚后重查台账,同摘要重放收敛(200,同映射);
        库内恒恰一份场景 + 台账一行。"""
        import asyncio

        from sqlalchemy import func, select

        from app.core import db as db_module
        from app.models.composer_scenario import ComposerScenario
        from app.models.scenario_asset_import import ScenarioAssetImport

        h, _space, _combo, _ds, _qa = await self._seed_source(client, "c1")
        bundle = (await client.get(
            "/api/scenarios/sc-m2x/asset-bundle", headers=h)).json()
        h_b = await register_and_login(client, "m2x_cb1", "pw123456")
        uid_b = (await client.get("/api/auth/me", headers=h_b)
                 ).json()["user"]["id"]
        async with db_module.SessionLocal() as s:
            space_b = await default_space_id(s, uid_b)
            await s.commit()

        path = f"/api/projects/{space_b}/asset-bundles"
        r1, r2 = await asyncio.gather(
            client.post(path, headers=h_b, json=bundle),
            client.post(path, headers=h_b, json=bundle))
        outcomes = sorted((r1.status_code, r2.status_code))
        assert outcomes == [200, 201], (r1.text, r2.text)
        win = r1 if r1.status_code == 201 else r2
        lose = r2 if r1.status_code == 201 else r1
        assert lose.json()["replayed"] is True
        assert lose.json()["scenarioId"] == win.json()["scenarioId"]

        async with db_module.SessionLocal() as s:
            n_import = (await s.execute(select(
                func.count()).select_from(
                ScenarioAssetImport).where(
                ScenarioAssetImport.project_id == space_b))).scalar_one()
            n_scen = (await s.execute(select(
                func.count()).select_from(
                ComposerScenario).where(
                ComposerScenario.project_id == space_b))).scalar_one()
            assert n_import == 1
            assert n_scen == 1

    async def test_blocked_scheme_roundtrip_stays_blocked(self, client):
        """评审 H1 回归:源侧 blocked 方案随包导出再导入,**不得静默变
        ready**(§20.3/§14.2:修复状态是资产事实,不把待修复计为可执行)。
        链:A(绑定组合)→ skipCombos 导 B(blocked)→ 从 B 导出
        (repairStatus/reason 随包)→ 导 C → 仍 blocked 且零绑定。"""
        h_a, _space_a, _combo, _ds, _qa = await self._seed_source(client, "bk")
        bundle_a = (await client.get(
            "/api/scenarios/sc-m2x/asset-bundle", headers=h_a)).json()

        h_b = await register_and_login(client, "m2x_blkb", "pw123456")
        uid_b = (await client.get("/api/auth/me", headers=h_b)
                 ).json()["user"]["id"]
        from app.core import db as db_module

        async with db_module.SessionLocal() as s:
            space_b = await default_space_id(s, uid_b)
            await s.commit()
        r = await client.post(f"/api/projects/{space_b}/asset-bundles",
                              headers=h_b, json=dict(bundle_a,
                                                     skipCombos=True))
        assert r.status_code == 201, r.text
        sid_b = r.json()["scenarioId"]

        # 从 B 导出:blocked 状态与原因随包
        r = await client.get(f"/api/scenarios/{sid_b}/asset-bundle",
                             headers=h_b)
        assert r.status_code == 200, r.text
        bundle_b = r.json()
        blocked_out = [s for s in bundle_b["schemes"]
                       if s.get("repairStatus") == "blocked"]
        assert blocked_out, "blocked 方案的修复状态随包导出"
        # P2-9:只随授权投影后的原因(内部精确原因与诊断引用不出包)
        assert blocked_out[0]["repairReason"] == "combo_dependency_invalid"
        assert "sourceComboRef" not in blocked_out[0]

        # 导 C:不跳过组合 —— 无绑定无映射的源 blocked 仍恢复为 blocked
        h_c = await register_and_login(client, "m2x_blkc", "pw123456")
        uid_c = (await client.get("/api/auth/me", headers=h_c)
                 ).json()["user"]["id"]
        async with db_module.SessionLocal() as s:
            space_c = await default_space_id(s, uid_c)
            await s.commit()
        r = await client.post(f"/api/projects/{space_c}/asset-bundles",
                              headers=h_c, json=bundle_b)
        assert r.status_code == 201, r.text
        report = r.json()
        assert report["blockedSchemes"], "blocked 方案恢复后仍 blocked"
        assert report["restoredBindings"] == 0
        sid_c = report["scenarioId"]
        async with db_module.SessionLocal() as s:
            from sqlalchemy import select

            from app.models.composer_run_scheme import ComposerRunScheme

            rows = (await s.execute(select(ComposerRunScheme).where(
                ComposerRunScheme.scenario_id == sid_c))).scalars().all()
            by_name = {x.name: x for x in rows}
            qa = by_name["回归方案"]
            assert qa.repair_status == "blocked"
            assert qa.repair_reason == "combo_dependency_invalid"
            assert qa.account_combo_id is None
            assert by_name["默认方案"].repair_status == "ready"

    async def test_shared_combo_dedup_across_schemes(self, client):
        """评审 M4 回归:两个方案引用同一源组合 → 恢复侧按 ref 去重只建
        一份组合,两方案绑定同一目标组合(复用语义与 revision 溯源不
        破坏;§5/§20.2)。"""
        h, _space, combo_id, _ds, _qa1 = await self._seed_source(client, "dp")
        await _mk_scheme(client, h, "sc-m2x", "回归方案B", combo_id=combo_id)
        bundle = (await client.get(
            "/api/scenarios/sc-m2x/asset-bundle", headers=h)).json()
        assert len(bundle["comboDependencies"]) == 2  # 两方案各带依赖项

        h_b = await register_and_login(client, "m2x_dupb", "pw123456")
        uid_b = (await client.get("/api/auth/me", headers=h_b)
                 ).json()["user"]["id"]
        from app.core import db as db_module

        async with db_module.SessionLocal() as s:
            space_b = await default_space_id(s, uid_b)
            await s.commit()
        r = await client.post(f"/api/projects/{space_b}/asset-bundles",
                              headers=h_b, json=bundle)
        assert r.status_code == 201, r.text
        report = r.json()
        assert report["restoredBindings"] == 2
        sid_b = report["scenarioId"]
        async with db_module.SessionLocal() as s:
            from sqlalchemy import func, select

            from app.models.account_combo import AccountCombo
            from app.models.composer_run_scheme import ComposerRunScheme

            n = (await s.execute(select(func.count()).select_from(
                AccountCombo).where(
                AccountCombo.project_id == space_b))).scalar_one()
            assert n == 1, "同一源组合按 ref 去重,只建一份"
            rows = (await s.execute(select(ComposerRunScheme).where(
                ComposerRunScheme.scenario_id == sid_b))).scalars().all()
            bound = {x.name: x.account_combo_id for x in rows}
            assert bound["回归方案"] is not None
            assert bound["回归方案"] == bound["回归方案B"]


async def _uid(client: AsyncClient, username: str) -> int:
    h = await register_and_login(client, username, "pw123456")
    me = (await client.get("/api/auth/me", headers=h)).json()
    return me["user"]["id"]


async def mk_proj_member(pid: int, username: str) -> None:
    from sqlalchemy import select

    from app.core import db as db_module
    from app.models.project import ProjectMember
    from app.models.user import User

    async with db_module.SessionLocal() as s:
        uid = (await s.execute(select(User.id).where(
            User.username == username))).scalar_one()
        s.add(ProjectMember(project_id=pid, user_id=uid, role="member"))
        await s.commit()


async def test_publish_to_public_generates_ready_for_severed_combo(
        client: AsyncClient):
    """复核 P2:发布(公共目标域,组合能力关闭,§7)继承 blocked 即
    修复死角 —— 副本组合引用已剥(绑定恒剥),「组合依赖受阻」对副本
    事实不成立:copy_schemes 按依赖事实生成 ready(§20.3「由领域服务
    按依赖事实生成」;§20.3「继承阻塞**或**在目标域显式修复」的第二
    分支在公共域结构性不可用)。源方案保持 blocked(本域可显式修复);
    同域复制腿(test_copy_strips_binding_and_inherits_blocked)不受影响。"""
    from app.core import db as db_module
    from app.models.composer_run_scheme import ComposerRunScheme
    from app.services import scheme_repair
    from sqlalchemy import select

    h = await register_and_login(client, "m2pub_a", "pw123456")
    uid = await _uid(client, "m2pub_a")
    await client.post("/api/scenarios", headers=h,
                      json=make_draft("sc-m2pub"))
    await _mk_scheme(client, h, "sc-m2pub", "公共候选")

    async with db_module.SessionLocal() as s:
        row = (await s.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == "sc-m2pub",
            ComposerRunScheme.is_default == True))).scalar_one()
        await scheme_repair.mark_blocked(
            s, row, reason="combo_missing", action="import.blocked",
            source_combo_ref="combo:legacy",
            actor_id=uid, actor_name="m2pub_a")
        await s.commit()

    r = await client.post("/api/scenarios/sc-m2pub/publish", headers=h)
    assert r.status_code == 200, r.text

    async with db_module.SessionLocal() as s:
        src = (await s.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == "sc-m2pub"))).scalars().all()
        copy = (await s.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == "sc-m2pub-public"))
        ).scalars().all()
    src_status = {x.name: x.repair_status for x in src}
    assert src_status["公共候选"] == "ready"        # 源原样(ready 行)
    assert "blocked" in set(src_status.values()), \
        "源 blocked 行保持 blocked(本域可显式修复)"
    assert copy, "公共副本应继承方案行"
    assert {x.repair_status for x in copy} == {"ready"}, \
        f"公共副本按依赖事实生成 ready: {[(x.name, x.repair_status) for x in copy]}"
    assert all(x.repair_reason is None for x in copy)
    assert all(x.account_combo_id is None for x in copy)
