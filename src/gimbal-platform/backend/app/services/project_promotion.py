"""M2a S7.2 提升流程服务(私有 → 普通项目;D7 = 复制,Q1 = 冲突转审批)。

析出分析:carry 层序在两区的解析差 —— 私有区吃 公共项目层 < 执行人
个人层(S4 tier 序),项目区吃 公共项目层 < 项目层(不吃个人层)。
提升后个人层断供 → 凡「个人层 ∨ 项目层」绑定的路径,两区有效值不同
即是冲突(项目层缺口 projectValue=None 同样要裁决:采纳原件值 = 补写
项目层)。别名登记(S6 起团队共享)与槽位绑定(跟人走)只作提示面。

无冲突 → 立即复制进项目(strip="always":项目成员可读,内置凭证与
数据集敏感列不落副本 —— 与发布复制同口径);有冲突 → pending 申请,
批准时以**批准那一刻**的原件内容复制(decisions 先落项目层再复制,
复制的执行从此吃项目层)。用例集提升:成员场景须已在目标项目
(reference)或私有随行(promote,冲突并入同一张申请单)。
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.composer_scenario import ComposerScenario
from ..models.project import Project, ProjectMember
from ..models.project_promotion import ProjectPromotion
from ..models.suite import Suite, SuiteMember
from ..models.user import User
from . import carry_store, scenario_store
from .run_materialize import referenced_services
from .scenario_store import definition_from_payload


class PromotionError(HTTPException):
    """提升流程错误(detail = {code, message};路由直接抛)。"""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(status_code=status, detail={
            "code": code, "message": message})
        self.code = code
        self.message = message


class SimpleUser:
    """服务内部复用 analyze 的最小用户壳(只需 .id)。"""

    def __init__(self, user_id: int) -> None:
        self.id = user_id


async def require_member(
    db: AsyncSession, project_id: int, user_id: int, *,
    writable: bool = False,
) -> Project:
    """目标项目门:普通项目 + 主体是其成员(公共项目只有「发布」一条路)。
    ``writable=True``(提升 = 往项目里写内容):项目用户(只读 + 执行,
    M2b Q1)→ 403 ``project_role_readonly``。"""
    proj = await db.get(Project, project_id)
    if proj is None:
        raise PromotionError(404, "not_found",
                             f"project not found: {project_id}")
    if proj.kind == "public":
        raise PromotionError(
            422, "public_project_promote_forbidden",
            "公共项目不接受「加入」—— 请使用「发布」")
    role = (await db.execute(select(ProjectMember.role).where(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id))).scalar_one_or_none()
    if role is None:
        raise PromotionError(404, "not_found",
                             f"project not found: {project_id}")
    if writable and role not in ProjectMember.WRITER_ROLES:
        raise PromotionError(403, "project_role_readonly",
                             "项目用户只能读和执行项目内容,不能加入内容")
    return proj


async def require_project_admin(
    db: AsyncSession, project_id: int, user,
) -> None:
    """裁决门(与项目层 carry 写面同口径):项目管理员 ∨ Admin+。"""
    from ..routers._ownership import has_capability

    if has_capability(user, "ops.write"):
        return
    ids = list((await db.execute(select(ProjectMember.user_id).where(
        ProjectMember.project_id == project_id,
        ProjectMember.role == ProjectMember.ROLE_ADMIN))).scalars().all())
    if user.id not in ids:
        raise PromotionError(403, "not_project_admin",
                             "只有项目管理员可以裁决加入申请")


async def project_admin_ids(db: AsyncSession, project_id: int) -> list[int]:
    return list((await db.execute(select(ProjectMember.user_id).where(
        ProjectMember.project_id == project_id,
        ProjectMember.role == ProjectMember.ROLE_ADMIN))).scalars().all())


async def _load_source(
    db: AsyncSession, kind: str, source_id: str, applicant_id: int,
):
    """来源对象门:存在 + 属主是申请人 + 在私有区(未进任何项目)。"""
    if kind == "scenario":
        row = (await db.execute(select(ComposerScenario).where(
            ComposerScenario.scenario_id == source_id))).scalar_one_or_none()
        if row is None:
            raise PromotionError(404, "not_found",
                                 f"scenario not found: {source_id}")
        if row.owner_id != applicant_id:
            raise PromotionError(403, "not_owner", "只能加入自己名下的场景")
        if row.project_id is not None:
            raise PromotionError(
                422, "source_not_private", "场景已在项目中,不能再次加入")
        return row
    if kind == "suite":
        row = ((await db.execute(select(Suite).where(
            Suite.id == int(source_id)))).scalar_one_or_none()
            if source_id.isdigit() else None)
        if row is None:
            raise PromotionError(404, "not_found",
                                 f"suite not found: {source_id}")
        if row.owner_id != applicant_id:
            raise PromotionError(403, "not_owner", "只能加入自己名下的用例集")
        if row.project_id is not None:
            raise PromotionError(
                422, "source_not_private", "用例集已在项目中,不能再次加入")
        return row
    raise PromotionError(422, "kind_invalid", "kind ∈ scenario | suite")


def _referenced(definition: dict) -> set[str]:
    steps = [s for s in (definition.get("steps") or [])
             if isinstance(s, dict)]
    services = set(referenced_services(steps))
    for svc, b in ((definition.get("config") or {}).get(
            "serviceBindings") or {}).items():
        if isinstance(b, dict) and b.get("alias"):
            services.add(svc)
    return services


async def _carry_conflicts(
    db: AsyncSession, services: set[str], project_id: int, applicant_id: int,
) -> list[dict]:
    """两区 carry 解析差(冲突清单):eff_priv = 公共层 < **申请人默认执行
    配置覆盖**(分层⑥起个人层的新家,决策 8;原个人层行已停读迁移),
    eff_proj = 公共层 < 项目层;「配置覆盖 ∨ 项目层」绑定的路径里两者
    不同即冲突(projectValue=None = 项目层缺口)。"""
    from .exec_config import load_choice

    choice = await load_choice(db, applicant_id, None)
    personal_cfg = (choice.carry_overrides if choice is not None else None) or {}
    out: list[dict] = []
    for svc in sorted(services):
        pub = await carry_store.get_bindings(db, svc)
        personal = personal_cfg.get(svc) or {}
        project = await carry_store.get_bindings(
            db, svc, scope=("project", project_id))
        for path in sorted(set(personal) | set(project)):
            eff_priv = personal.get(path, pub.get(path))
            eff_proj = project.get(path, pub.get(path))
            if eff_priv != eff_proj:
                out.append({
                    "service": svc, "path": path,
                    "sourceValue": eff_priv, "projectValue": eff_proj,
                })
    return out


async def _scenario_analysis(
    db: AsyncSession, row: ComposerScenario, project_id: int,
) -> dict:
    definition = definition_from_payload(row.payload)
    services = _referenced(definition)
    return {
        "services": sorted(services),
        "conflicts": await _carry_conflicts(
            db, services, project_id, row.owner_id),
    }


async def _referenced_slots(db: AsyncSession, payload: dict) -> list[str]:
    """引用的槽位(提示面:凭证跟人走,成员各自绑定)。"""
    from .service_aliases import (credential_aliases_for,
                                  exec_auth_aliases_of_definition)
    names = await exec_auth_aliases_of_definition(
        db, definition_from_payload(payload))
    slots = (await credential_aliases_for(db, names)).values()
    return sorted(set(slots))


async def analyze_promotion(
    db: AsyncSession, *, kind: str, source_id: str,
    project_id: int, user,
) -> dict:
    """析出分析(创建申请前的前置预览,与创建同口径)。"""
    await require_member(db, project_id, user.id, writable=True)
    src = await _load_source(db, kind, source_id, user.id)
    blockers: list[dict] = []
    if kind == "scenario":
        analysis = await _scenario_analysis(db, src, project_id)
        slots = await _referenced_slots(db, src.payload)
    else:
        # 用例集:成员场景须已在目标项目(reference)或私有随行(promote);
        # 其余(他人私有 / 别的项目 / 公共副本 / 已删)= 阻断项
        members = (await db.execute(select(SuiteMember).where(
            SuiteMember.suite_id == src.id).order_by(
            SuiteMember.sort))).scalars().all()
        plan: list[dict] = []
        conflicts: list[dict] = []
        services: set[str] = set()
        for m in members:
            scen = (await db.execute(select(ComposerScenario).where(
                ComposerScenario.scenario_id == m.scenario_id))
            ).scalar_one_or_none()
            if scen is None:
                blockers.append({"scenarioId": m.scenario_id,
                                 "reason": "missing"})
                continue
            # 同区触发器(S1.5)钉死私有套件成员必私有;「已在项目」=
            # 该场景此前单独提升过 —— 项目里有 forked_from_id 指向它的
            # 副本,直接 reference(多副本取最近更新的)
            if scen.project_id == project_id:
                plan.append({"scenarioId": m.scenario_id,
                             "action": "reference", "role": m.role or "main"})
            elif scen.project_id is not None:
                blockers.append({"scenarioId": m.scenario_id,
                                 "reason": "in_other_project"})
            else:
                promoted = (await db.execute(
                    select(ComposerScenario.scenario_id)
                    .where(ComposerScenario.project_id == project_id,
                           ComposerScenario.forked_from_id == scen.scenario_id)
                    .order_by(ComposerScenario.updated_at.desc())
                    .limit(1))).scalar_one_or_none()
                if promoted is not None:
                    plan.append({"scenarioId": m.scenario_id,
                                 "action": "reference",
                                 "copyOf": promoted,
                                 "role": m.role or "main"})
                elif scen.owner_id == src.owner_id:
                    plan.append({"scenarioId": m.scenario_id,
                                 "action": "promote",
                                 "role": m.role or "main"})
                    sub = await _scenario_analysis(db, scen, project_id)
                    conflicts += [{**c, "scenarioId": m.scenario_id}
                                  for c in sub["conflicts"]]
                    services.update(sub["services"])
                else:
                    blockers.append({"scenarioId": m.scenario_id,
                                     "reason": "not_owner"})
        slots: list[str] = []
        for m in members:
            scen = (await db.execute(select(ComposerScenario.payload).where(
                ComposerScenario.scenario_id == m.scenario_id))
            ).scalar_one_or_none()
            if scen:
                slots += await _referenced_slots(db, scen)
        analysis = {"services": sorted(services), "conflicts": conflicts,
                    "memberPlan": plan}
    return {**analysis, "blockers": blockers,
            "slots": sorted(set(slots))}


async def _promote_scenario(
    db: AsyncSession, src: ComposerScenario, project_id: int,
) -> str:
    """复制场景进项目(同属主 = 维护者不变;strip=always 不落明文)。"""
    applicant = await db.get(User, src.owner_id)
    resolved, _ = await scenario_store.resolve_name_conflict(
        db, src.owner_id, src.name or src.scenario_id)
    out = await scenario_store.copy_scenario(
        db, src.scenario_id,
        new_owner=(applicant.display_name or applicant.username
                   if applicant else f"user-{src.owner_id}"),
        new_owner_id=src.owner_id, new_name=resolved,
        activity_kind="scenario.promoted",
        activity_detail={"projectId": project_id},
        origin_id=src.scenario_id,
        origin_owner_name=src.owner_name or "",
        project_id=project_id, strip="always")
    return out.meta.scenario_id


async def execute_promotion_copy(
    db: AsyncSession, promo: ProjectPromotion,
    decisions: list[dict], *, approver,
) -> dict:
    """复制执行(立即加入 ∨ 批准那一刻):先落「采纳原件值」裁决到
    项目层(**合并写** —— 只动 use=source 的路径,不动项目层其余值),
    再按当前原件内容复制。前置:调用方已过权限门与状态门。"""
    by_service: dict[str, dict[str, Any]] = {}
    for d in decisions:
        if d.get("use") == "source":
            by_service.setdefault(d["service"], {})[d["path"]] = \
                d.get("sourceValue")
    for svc, entries in by_service.items():
        current = await carry_store.get_bindings(
            db, svc, scope=("project", promo.project_id))
        await carry_store.put_bindings(
            db, svc, {**current, **entries},
            updated_by_id=approver.id,
            updated_by_name=(approver.display_name or approver.username
                             if approver else f"user-{approver.id}"),
            scope=("project", promo.project_id))
    if promo.kind == "scenario":
        src = (await db.execute(select(ComposerScenario).where(
            ComposerScenario.scenario_id == promo.source_id))
        ).scalar_one_or_none()
        if src is None:
            raise PromotionError(409, "source_deleted",
                                 "原件已删除,无法完成加入")
        return {"scenarioId": await _promote_scenario(
            db, src, promo.project_id)}
    # 用例集:按批准那一刻重新核对成员计划(原件在申请期间可能改过)
    suite = (await db.execute(select(Suite).where(
        Suite.id == int(promo.source_id)))).scalar_one_or_none()
    if suite is None:
        raise PromotionError(409, "source_deleted",
                             "原用例集已删除,无法完成加入")
    analysis = await analyze_promotion(
        db, kind="suite", source_id=promo.source_id,
        project_id=promo.project_id, user=SimpleUser(promo.applicant_id))
    if analysis["blockers"]:
        raise PromotionError(409, "members_blocked",
                             "成员场景状态变化,重新发起加入申请")
    from datetime import datetime, timezone
    from .suite_copy import suite_owner_display
    # 同属主内 suite 名唯一(uq_suites_owner_name):计数后缀去冲突
    existing = {n for (n,) in (await db.execute(
        select(Suite.name).where(Suite.owner_id == suite.owner_id))).all()}
    name = suite.name
    if name in existing:
        i = 2
        while f"{name}-{i}" in existing:
            i += 1
        name = f"{name}-{i}"
    new_suite = Suite(
        name=name, description=suite.description,
        owner_id=suite.owner_id, mode=suite.mode, rev=0,
        project_id=promo.project_id,
        forked_from_id=suite.id,
        forked_from_owner_name=await suite_owner_display(db, suite),
        forked_from_at=datetime.now(timezone.utc).replace(tzinfo=None),
        mode_config={})
    db.add(new_suite)
    await db.flush()
    mapping: dict[str, str] = {}
    sort = 0
    copied: list[str] = []
    for m in analysis["memberPlan"]:
        scen = (await db.execute(select(ComposerScenario).where(
            ComposerScenario.scenario_id == m["scenarioId"]))
        ).scalar_one()
        if m["action"] == "reference":
            new_sid = m.get("copyOf") or scen.scenario_id
        else:
            new_sid = await _promote_scenario(db, scen, promo.project_id)
            copied.append(new_sid)
        db.add(SuiteMember(suite_id=new_suite.id, scenario_id=new_sid,
                           role=m["role"], sort=sort))
        mapping[m["scenarioId"]] = new_sid
        sort += 1
    from .suite_copy import remap_config_references
    members_now = (await db.execute(select(SuiteMember).where(
        SuiteMember.suite_id == suite.id))).scalars().all()
    removed = {m.scenario_id for m in members_now} - set(mapping)
    new_suite.mode_config = remap_config_references(
        suite.mode_config or {}, mapping, removed)
    return {"suiteId": new_suite.id, "copiedScenarioIds": copied}


async def source_changed_since(
    db: AsyncSession, promo: ProjectPromotion,
) -> bool:
    """原件在申请后是否改过(审批页提示;批准按当前内容复制)。"""
    if promo.kind == "scenario":
        row = (await db.execute(select(ComposerScenario.updated_at).where(
            ComposerScenario.scenario_id == promo.source_id))
        ).scalar_one_or_none()
    else:
        row = (await db.execute(select(Suite.updated_at).where(
            Suite.id == int(promo.source_id)))).scalar_one_or_none()
    return row is not None and promo.created_at is not None \
        and row > promo.created_at
