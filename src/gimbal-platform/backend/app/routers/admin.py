"""Admin 查询端点(P2-3:审计日志,admin only)。"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import AdminUser
from ..schemas.page import PageOut
from ..services import audit as audit_svc

router = APIRouter(prefix="/admin", tags=["admin"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    actor_id: int | None = Field(default=None, alias="actorId")
    actor_name: str = Field(default="", alias="actorName")
    action: str
    resource_type: str | None = Field(default=None, alias="resourceType")
    resource_id: str | None = Field(default=None, alias="resourceId")
    detail: dict = Field(default_factory=dict)
    created_at: datetime = Field(alias="createdAt")


class AuditLogPage(PageOut[AuditLogOut]):
    """M4 Page 信封(§6.3)+ 可过滤动作词表。"""

    actions: list[str] = Field(default_factory=list)


@router.get("/audit-logs", response_model=AuditLogPage)
async def list_audit_logs(
    user: AdminUser,
    db: DbSession,
    action: Annotated[str | None, Query(max_length=64)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AuditLogPage:
    """特权写审计(权限方案 §6):新→旧分页;``action`` 精确过滤;
    ``actions`` 带回词表供前端过滤 chip。"""
    rows, total = await audit_svc.list_page(
        db, action=action, page=page, page_size=page_size)
    return AuditLogPage(
        items=[AuditLogOut.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
        actions=list(audit_svc.AUDIT_ACTIONS),
    )


# ── 凭证治理阶段 3:清账向导盘点(admin 只读)────────────────────────

class CleanupUnregisteredRow(BaseModel):
    """带未登记身份引用的场景行(引用面 = 保存/导入闸同一单源提取器)。"""
    scenarioId: str
    name: str
    owner: str
    projectId: int | None = Field(default=None, alias="projectId")
    refs: list[str] = Field(default_factory=list)


class CleanupSnapshotRow(BaseModel):
    """明文快照存量行(只列键名 —— 值是明文口令,不出任何面)。"""
    scenarioId: str
    name: str
    owner: str
    keys: list[str] = Field(default_factory=list)
    # 被步骤引用的键(``${auth.*}``/``call.user``/服务键默认命中)——
    # 这些键须先登记同名条目再清快照,否则执行面悬空。
    referencedKeys: list[str] = Field(default_factory=list)


class CleanupBindingRow(BaseModel):
    """绑定换用目标未登记的运行方案行(写面闸历史存量面)。"""
    schemeId: str
    scenarioId: str
    name: str
    unregisteredTargets: list[str] = Field(default_factory=list)


class CleanupSurvey(BaseModel):
    """清账向导盘点(enforce 时点的就绪清单,数字全 live):
    三面全空 = 「引用皆真条目 + 存量无明文」→ 可切 enforce(拍板:
    清账完成即切)。"""
    gateMode: str
    registrySize: int
    unregistered: list[CleanupUnregisteredRow] = Field(default_factory=list)
    snapshots: list[CleanupSnapshotRow] = Field(default_factory=list)
    bindings: list[CleanupBindingRow] = Field(default_factory=list)


@router.get("/cleanup-survey", response_model=CleanupSurvey)
async def cleanup_survey(user: AdminUser, db: DbSession) -> CleanupSurvey:
    """清账向导盘点(阶段 3;admin 只读,零写面)。聚合三张存量面:

    * 未登记引用场景(决策 1 保存/导入闸同一提取器;
      ``REGISTRY_ONLY_IDENTITIES`` audit 态的生产数字即此);
    * 明文快照场景(本案 §7;键名 only,清账走属主保存链显式清空);
    * 方案绑定目标未登记(``validate_binding_aliases`` 历史存量)。

    清账操作不经本端点:登记条目走既有 ``POST /service-aliases``,
    快照清空走属主保存链(PUT users={} 显式清空,admin 无旁路 ——
    W3 拍板,向导只指路不代刀)。
    """
    import logging

    from sqlalchemy import select as sa_select

    from ..core.config import settings
    from ..models.composer_run_scheme import ComposerRunScheme
    from ..models.composer_scenario import ComposerScenario
    from ..services.scenario_store import definition_from_payload
    from ..services.service_aliases import (
        effective_alias, exec_auth_aliases_of_definition)
    from ..models.service_identity import ServiceIdentity

    log = logging.getLogger("admin.cleanup-survey")
    registry = dict((await db.execute(
        sa_select(ServiceIdentity.alias_name,
                  ServiceIdentity.base_service))).all())

    unreg_rows: list[CleanupUnregisteredRow] = []
    snapshot_rows: list[CleanupSnapshotRow] = []
    scen_rows = (await db.execute(
        sa_select(ComposerScenario.scenario_id,
                  ComposerScenario.name,
                  ComposerScenario.owner_name,
                  ComposerScenario.project_id,
                  ComposerScenario.payload))).all()
    for sid, name, owner, project_id, payload in scen_rows:
        definition = definition_from_payload(payload)
        if not definition:
            continue
        refs = await exec_auth_aliases_of_definition(db, definition)
        unreg = sorted(set(refs) - set(registry))
        if unreg:
            unreg_rows.append(CleanupUnregisteredRow(
                scenarioId=sid, name=name or "", owner=owner or "",
                projectId=project_id, refs=unreg))
        users = ((definition.get("config") or {}).get("users"))
        if isinstance(users, dict) and users:
            keys = sorted(str(k) for k in users)
            snapshot_rows.append(CleanupSnapshotRow(
                scenarioId=sid, name=name or "", owner=owner or "",
                keys=keys,
                referencedKeys=sorted(set(keys) & set(refs))))

    binding_rows: list[CleanupBindingRow] = []
    scheme_rows = (await db.execute(
        sa_select(ComposerRunScheme.scheme_id,
                  ComposerRunScheme.scenario_id,
                  ComposerRunScheme.name,
                  ComposerRunScheme.payload))).all()
    for scheme_id, scenario_id, name, payload in scheme_rows:
        bindings = (payload or {}).get("serviceBindings")
        if not isinstance(bindings, dict):
            bindings = (payload or {}).get("service_bindings")
        targets = {svc: effective_alias(svc, bindings)
                   for svc in (bindings or {})}
        unreg = sorted({a for a in targets.values() if a not in registry})
        if unreg:
            binding_rows.append(CleanupBindingRow(
                schemeId=scheme_id, scenarioId=scenario_id,
                name=name or "", unregisteredTargets=unreg))

    mode = settings.REGISTRY_ONLY_IDENTITIES
    log.info("cleanup survey: unregistered=%d snapshots=%d bindings=%d",
             len(unreg_rows), len(snapshot_rows), len(binding_rows))
    return CleanupSurvey(
        gateMode=mode, registrySize=len(registry),
        unregistered=unreg_rows, snapshots=snapshot_rows,
        bindings=binding_rows)
