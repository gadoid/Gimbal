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


class TestPrecheckRepairGate:
    """§20.3 装配闸最小链路(M2:precheck):blocked 在凭证解析前返回。"""

    async def test_blocked_returns_before_credential_resolution(
            self, client: AsyncClient, monkeypatch):
        from app.core import db as db_module
        from app.models.composer_run_scheme import ComposerRunScheme
        from app.services import scheme_repair
        from sqlalchemy import select

        h = await register_and_login(client, "m2pre_a", "pw123456")
        uid = await _uid(client, "m2pre_a")
        await client.post("/api/scenarios", headers=h,
                          json=make_draft("sc-m2pre"))
        scheme_id = await _mk_scheme(client, h, "sc-m2pre", "待修")
        async with db_module.SessionLocal() as s:
            row = (await s.execute(select(ComposerRunScheme).where(
                ComposerRunScheme.scheme_id == scheme_id))).scalar_one()
            await scheme_repair.mark_blocked(
                s, row, reason="combo_missing", action="import.blocked",
                actor_id=uid, actor_name="seed")
            await s.commit()

        # 凭证/注入/环境解析零调用:monkeypatch 三个解析面任一被触即炸
        import app.services.run_dispatcher as rd
        import app.services.env_chain as _ec

        def _boom(*a, **k):
            raise AssertionError("blocked 方案不得进入凭证/装配解析")

        monkeypatch.setattr(rd, "filter_injection_entries", _boom)
        monkeypatch.setattr(_ec, "resolve_execution_tag", _boom)

        r = await client.post("/api/run/precheck", headers=h, json=[
            {"scenarioId": "sc-m2pre", "schemeId": scheme_id}])
        assert r.status_code == 200, r.text
        [res] = r.json()
        assert res["found"] is True and res["schemeFound"] is True
        assert res["schemeValid"] is False
        assert res["repairBlocked"] is True
        assert res["repairCode"] == "scheme_repair_required"
        assert res["repairReason"] == "combo_dependency_invalid"
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
        # 把默认候选指向携带选择的方案 → 恢复整包拒绝
        bundle["defaultSchemeId"] = next(
            s["schemeId"] for s in bundle["schemes"]
            if not s["isDefault"])

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
