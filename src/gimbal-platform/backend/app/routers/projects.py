"""项目区管理面(M2a S1.4,s1-detail §六)。

* **建项目 = Admin+**(S1-g:`ops.write`),创建时指定首个项目管理员
  (受让人须在职、非系统用户;不需要确认,与删用户「转让」同口径)。
* **项目管理员**(`project_members.role` 取 `ROLE_ADMIN`,padmin)管理本项目
  成员:增删、改角色;**末位项目管理员保护** —— 最后一个 admin 不能被
  移除或降级(与末位 Super Admin 同口径,项目不能无人可管)。
* **删项目 = 仅 Admin+**,且项目内有内容(场景/suite/集成模板/报告
  定义)时 409 `project_not_empty` —— 不做级联删除,先清空或迁走;
  **公共项目不可删不可改 kind**(部分唯一索引钉死恰一行)。
* 普通成员行只增不改权限边界:读面由表 B / zone_read_clause 派生,
  本路由只管成员关系本身。审计:建/删/成员变更入审计(admin 面)。
"""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser, MemberUser
from ..models.project import Project, ProjectMember
from ..models.user import User
from ._ownership import has_capability

router = APIRouter(prefix="/projects", tags=["projects"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


class ProjectCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=2000)
    firstAdminUserId: int = Field(ge=1)


class ProjectPatchIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    # S2.2 环境链第三位;显式传 null = 清空(未传 = 不动)
    defaultEnvironmentId: int | None = Field(default=None, ge=1)


class MemberIn(BaseModel):
    userId: int = Field(ge=1)
    # M2b Q1:user = 项目用户(只读 + 执行)
    role: Literal["admin", "member", "user"] = "member"


class MemberPatchIn(BaseModel):
    role: Literal["admin", "member", "user"]


class ProjectOut(BaseModel):
    id: int
    name: str
    kind: str
    description: str
    memberCount: int = 0
    # 请求者在本项目的角色(admin = 项目管理员;None = 非成员 ——
    # Admin+ 的管理视图可见非成员项目)
    myRole: str | None = None
    # S2.2:项目默认环境(环境链第三位;None = 未设置)
    defaultEnvironmentId: int | None = None
    # S7.0:请求者能否管理(项目管理员 ∨ Admin+;公共项目 = Admin+)——
    # 前端据此显隐成员管理 / 配置编辑,不再自己拼角色判定
    canManage: bool = False
    # M2b Q1:请求者能否在项目内新建 / 修改内容(项目管理员 ∨ 项目成员;
    # 项目用户只读 + 执行)—— 前端据此显隐写入口,后端仍是权威
    canWrite: bool = False
    # S7.0 详情读面:默认环境名 + 各类内容计数(页签徽标数据源;
    # 列表端点不填,保持 0)
    defaultEnvironmentName: str | None = None
    scenarioCount: int = 0
    suiteCount: int = 0
    taskCount: int = 0


class MemberOut(BaseModel):
    userId: int
    username: str
    displayName: str
    role: str
    addedAt: str | None = None


async def _load_project(db: AsyncSession, project_id: int) -> Project:
    proj = await db.get(Project, project_id)
    if proj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found",
                    "message": f"project not found: {project_id}"})
    return proj


async def _my_role(db: AsyncSession, user, project_id: int) -> str | None:
    return (await db.execute(select(ProjectMember.role).where(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user.id))).scalar_one_or_none()


async def _require_manage(
    db: AsyncSession, user, project: Project,
) -> None:
    """管理面门(S1.4):项目管理员 ∨ Admin+(ops.write)。非成员 404
    (不泄露存在性);成员但非项目管理员 403(项目可见,无管理权)。"""
    if has_capability(user, "ops.write"):
        return
    my_role = await _my_role(db, user, project.id)
    if my_role == "admin":
        return
    if my_role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found",
                    "message": f"project not found: {project.id}"})
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "not_project_admin",
                "message": "只有项目管理员(或 Admin+)能管理项目"})


async def _member_count(db: AsyncSession, project_id: int) -> int:
    return (await db.execute(select(func.count()).select_from(
        ProjectMember).where(
            ProjectMember.project_id == project_id))).scalar_one()


async def _audit(db, user, action: str, project: Project, detail: dict):
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=user.display_name or user.username,
        action=action, resource_type="project",
        resource_id=str(project.id), resource_name=project.name,
        detail=detail)


# ── 项目 CRUD ──────────────────────────────────────────────────────
@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    user: MemberUser, db: DbSession, body: ProjectCreateIn,
) -> ProjectOut:
    """建项目(S1-g:Admin+ / ops.write),指定首个项目管理员。"""
    admin = await db.get(User, body.firstAdminUserId)
    if (admin is None or not admin.is_active or admin.is_system):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "first_admin_invalid",
                    "message": "首个项目管理员须为在职、非系统用户"})
    proj = Project(name=body.name, description=body.description,
                   kind="normal", created_by=user.id)
    db.add(proj)
    try:
        await db.flush()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "project_name_taken",
                    "message": f"项目名已被使用:{body.name}"}) from e
    db.add(ProjectMember(project_id=proj.id, user_id=admin.id,
                         role=ProjectMember.ROLE_ADMIN, added_by=user.id))
    await db.commit()
    await db.refresh(proj)
    await _audit(db, user, "project.created", proj,
                 {"name": proj.name, "firstAdminId": admin.id})
    return ProjectOut(id=proj.id, name=proj.name, kind=proj.kind,
                      description=proj.description, memberCount=1,
                      myRole=(await _my_role(db, user, proj.id)),
                      defaultEnvironmentId=proj.default_environment_id)


def _can_manage(user, proj: Project, my_role: str | None) -> bool:
    """管理权(与 ``_require_manage`` 同口径):Admin+ ∨ 项目管理员;
    公共项目无成员行 → 只有 Admin+。"""
    return has_capability(user, "ops.write") or (
        proj.kind != "public" and my_role == "admin")


def _can_write(proj: Project, my_role: str | None) -> bool:
    """项目内写权(M2b Q1,与表 B contributor 同口径):普通项目的项目
    管理员 ∨ 项目成员;公共项目只走「发布」,恒 False。"""
    return proj.kind != "public" and my_role in ProjectMember.WRITER_ROLES


async def _detail_counts(db: AsyncSession, proj: Project) -> dict:
    """S7.0 详情读面:默认环境名 + 场景 / 用例集 / 集成模板计数
    (集成只数模板行,软删不计)。"""
    from ..models.composer_scenario import ComposerScenario
    from ..models.environment import Environment
    from ..models.integration_task import IntegrationTask
    from ..models.suite import Suite

    async def _count(stmt) -> int:
        return (await db.execute(
            stmt.with_only_columns(func.count()).order_by(None))).scalar()

    env_name = None
    if proj.default_environment_id is not None:
        env_row = await db.get(Environment, proj.default_environment_id)
        env_name = env_row.name if env_row is not None else None
    return {
        "defaultEnvironmentName": env_name,
        "scenarioCount": await _count(select(ComposerScenario).where(
            ComposerScenario.project_id == proj.id)),
        "suiteCount": await _count(select(Suite).where(
            Suite.project_id == proj.id)),
        "taskCount": await _count(select(IntegrationTask).where(
            IntegrationTask.project_id == proj.id,
            IntegrationTask.template_id.is_(None),
            IntegrationTask.removed_at.is_(None))),
    }


@router.get("/{project_id}/slot-status")
async def project_slot_status(
    user: CurrentUser, db: DbSession, project_id: int,
) -> dict:
    """槽位状态 = 成员凭证清单(S7.3 项目配置页签,只读不落库):
    项目场景引用的槽位 × 成员是否已绑定(任意绑定即算;不给任何账号
    信息);S8 每槽另给 ``projectBound``(项目凭证已登记)。门 = 项目成员(仅普通项目 —— 公共项目内容走订阅,凭证是
    订阅者自己的事,本端点 422)。"""
    from ..models.auth_session import AuthSession
    from ..models.composer_scenario import ComposerScenario
    from ..models.user import User
    from ..services.project_promotion import require_member

    await require_member(db, project_id, user.id)
    scen_rows = (await db.execute(select(ComposerScenario.scenario_id,
                                         ComposerScenario.payload).where(
        ComposerScenario.project_id == project_id))).all()
    from ..services.project_promotion import _referenced_slots

    slot_scenarios: dict[str, list[str]] = {}
    for sid, payload in scen_rows:
        for slot in await _referenced_slots(db, payload):
            slot_scenarios.setdefault(slot, []).append(sid)
    members = (await db.execute(
        select(ProjectMember.user_id, User.username, User.display_name)
        .join(User, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.user_id))).all()
    slots = sorted(slot_scenarios)
    bound: set[tuple[int, str]] = set()
    if slots and members:
        rows = (await db.execute(
            select(AuthSession.owner_id, AuthSession.slot).where(
                AuthSession.owner_id.in_([m[0] for m in members]),
                AuthSession.slot.in_(slots)))).all()
        bound = set(rows)
    # S8:项目凭证是否覆盖该槽(成员可切换为项目凭证执行)
    project_bound: set[str] = set()
    if slots:
        project_bound = set((await db.execute(
            select(AuthSession.slot).where(
                AuthSession.project_id == project_id,
                AuthSession.slot.in_(slots)))).scalars().all())
    return {"slots": [{
        "slot": slot,
        "scenarios": sorted(slot_scenarios[slot]),
        "projectBound": slot in project_bound,
        "members": [{"userId": uid, "username": uname,
                     "displayName": disp or uname,
                     "bound": (uid, slot) in bound}
                    for uid, uname, disp in members],
    } for slot in slots]}


@router.get("", response_model=list[ProjectOut])
async def list_projects(user: CurrentUser, db: DbSession) -> list[ProjectOut]:
    """项目列表(S7.0 项目页数据源):公共项目(全员,置顶)+ 我所在的
    项目;Admin+ 管理视图全量。"""
    roles = {pid: role for pid, role in (await db.execute(
        select(ProjectMember.project_id, ProjectMember.role).where(
            ProjectMember.user_id == user.id))).all()}
    from sqlalchemy import or_ as _or
    stmt = select(Project) if has_capability(user, "ops.write") else (
        select(Project).where(_or(
            Project.kind == "public",
            Project.id.in_(roles) if roles else False)))
    projs = (await db.execute(stmt.order_by(
        (Project.kind != "public"), Project.id))).scalars().all()
    counts = {pid: n for pid, n in (await db.execute(
        select(ProjectMember.project_id, func.count()).group_by(
            ProjectMember.project_id))).all()}
    return [ProjectOut(
        id=p.id, name=p.name, kind=p.kind, description=p.description,
        memberCount=counts.get(p.id, 0),
        myRole=roles.get(p.id),
        defaultEnvironmentId=p.default_environment_id,
        canManage=_can_manage(user, p, roles.get(p.id)),
        canWrite=_can_write(p, roles.get(p.id))) for p in projs]


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    user: CurrentUser, db: DbSession, project_id: int,
) -> ProjectOut:
    proj = await _load_project(db, project_id)
    my_role = await _my_role(db, user, project_id)
    # 公共项目全员可读(S7.0 项目页);普通项目非成员 404(Admin+ 管理视图)
    if (my_role is None and proj.kind != "public"
            and not has_capability(user, "ops.write")):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found",
                    "message": f"project not found: {project_id}"})
    return ProjectOut(id=proj.id, name=proj.name, kind=proj.kind,
                      description=proj.description,
                      memberCount=await _member_count(db, project_id),
                      myRole=my_role,
                      defaultEnvironmentId=proj.default_environment_id,
                      canManage=_can_manage(user, proj, my_role),
                      canWrite=_can_write(proj, my_role),
                      **await _detail_counts(db, proj))


@router.patch("/{project_id}", response_model=ProjectOut)
async def patch_project(
    user: CurrentUser, db: DbSession, project_id: int, body: ProjectPatchIn,
) -> ProjectOut:
    proj = await _load_project(db, project_id)
    await _require_manage(db, user, proj)
    if proj.kind == "public":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "public_project_protected",
                    "message": "公共项目不可修改"})
    if body.name is not None and body.name != proj.name:
        proj.name = body.name
        try:
            await db.flush()
        except IntegrityError as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "project_name_taken",
                        "message": f"项目名已被使用:{body.name}"}) from e
    if body.description is not None:
        proj.description = body.description
    if "defaultEnvironmentId" in body.model_fields_set:
        env_id = body.defaultEnvironmentId
        if env_id is not None:
            from ..models.environment import Environment
            if await db.get(Environment, env_id) is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"code": "environment_not_found",
                            "message": f"environment not found: {env_id}"})
        proj.default_environment_id = env_id
    await db.commit()
    await db.refresh(proj)
    await _audit(db, user, "project.patched", proj,
                 {"defaultEnvironmentId": proj.default_environment_id}
                 if "defaultEnvironmentId" in body.model_fields_set else {})
    return ProjectOut(id=proj.id, name=proj.name, kind=proj.kind,
                      description=proj.description,
                      memberCount=await _member_count(db, project_id),
                      myRole=await _my_role(db, user, project_id),
                      defaultEnvironmentId=proj.default_environment_id)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    user: MemberUser, db: DbSession, project_id: int,
) -> None:
    """删项目 = 仅 Admin+(ops.write);有内容 409(先清空或迁走);
    公共项目 409。成员行随 CASCADE 消失(项目没了,成员关系无意义)。"""
    proj = await _load_project(db, project_id)
    if proj.kind == "public":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "public_project_protected",
                    "message": "公共项目不可删除"})
    # 内容闸:四张对象表任一挂靠即拒
    from sqlalchemy import select as _sel

    from ..models.composer_scenario import ComposerScenario
    from ..models.integration_task import IntegrationTask
    from ..models.report_definition import ReportDefinitionRow
    from ..models.suite import Suite

    occupied = (await db.execute(_sel(ComposerScenario.id).where(
        ComposerScenario.project_id == project_id).limit(1))
    ).scalar_one_or_none()
    if occupied is None:
        occupied = (await db.execute(_sel(Suite.id).where(
            Suite.project_id == project_id).limit(1))).scalar_one_or_none()
    if occupied is None:
        occupied = (await db.execute(_sel(IntegrationTask.id).where(
            IntegrationTask.project_id == project_id,
            IntegrationTask.template_id.is_(None)).limit(1))
        ).scalar_one_or_none()
    if occupied is None:
        occupied = (await db.execute(_sel(ReportDefinitionRow.id).where(
            ReportDefinitionRow.project_id == project_id).limit(1))
        ).scalar_one_or_none()
    if occupied is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "project_not_empty",
                    "message": "项目内仍有内容(场景/套件/集成模板/报告"
                               "定义),需先清空或迁走再删除"})
    await _audit(db, user, "project.deleted", proj, {"name": proj.name})
    # S8:项目凭证随项目删除(FK NO ACTION —— 显式删,凭证是项目的配置
    # 不是内容,不进内容闸)
    from sqlalchemy import delete as _del

    from ..models.auth_session import AuthSession
    await db.execute(_del(AuthSession).where(
        AuthSession.project_id == project_id))
    # M2b Q2:项目令牌随项目删除吊销(令牌行留档,终态只读)
    from .project_tokens import revoke_all_for_project
    await revoke_all_for_project(db, project_id)
    await db.delete(proj)
    await db.commit()


# ── 成员管理 ───────────────────────────────────────────────────────
@router.get("/{project_id}/members", response_model=list[MemberOut])
async def list_members(
    user: CurrentUser, db: DbSession, project_id: int,
) -> list[MemberOut]:
    proj = await _load_project(db, project_id)
    await _require_manage(db, user, proj)
    rows = (await db.execute(
        select(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.user_id))).all()
    return [MemberOut(
        userId=m.user_id, username=u.username,
        displayName=u.display_name or u.username, role=m.role,
        addedAt=m.added_at.isoformat() if m.added_at else None)
        for m, u in rows]


@router.post("/{project_id}/members", response_model=MemberOut,
             status_code=status.HTTP_201_CREATED)
async def add_member(
    user: CurrentUser, db: DbSession, project_id: int, body: MemberIn,
) -> MemberOut:
    proj = await _load_project(db, project_id)
    await _require_manage(db, user, proj)
    target = await db.get(User, body.userId)
    if target is None or not target.is_active or target.is_system:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "member_invalid",
                    "message": "成员须为在职、非系统用户"})
    existing = (await db.execute(select(ProjectMember).where(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == body.userId))).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "member_exists",
                    "message": f"用户已是项目成员:{target.username}"})
    m = ProjectMember(project_id=project_id, user_id=body.userId,
                      role=body.role, added_by=user.id)
    db.add(m)
    await db.commit()
    await _audit(db, user, "project.member_added", proj,
                 {"userId": m.user_id, "role": m.role})
    return MemberOut(userId=m.user_id, username=target.username,
                     displayName=target.display_name or target.username,
                     role=m.role)


@router.patch("/{project_id}/members/{member_user_id}",
              response_model=MemberOut)
async def patch_member(
    user: CurrentUser, db: DbSession, project_id: int,
    member_user_id: int, body: MemberPatchIn,
) -> MemberOut:
    proj = await _load_project(db, project_id)
    await _require_manage(db, user, proj)
    m = (await db.execute(select(ProjectMember).where(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == member_user_id))).scalar_one_or_none()
    if m is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found",
                    "message": f"member not found: {member_user_id}"})
    # 降级(→ 成员 / 项目用户)都要过「最后一个管理员」保护
    if (m.role == ProjectMember.ROLE_ADMIN
            and body.role != ProjectMember.ROLE_ADMIN):
        admins = (await db.execute(select(func.count()).select_from(
            ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.role == ProjectMember.ROLE_ADMIN))
        ).scalar_one()
        if admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "last_project_admin",
                        "message": "最后一个项目管理员不能降级"
                                   "(项目不能无人可管)"})
    demoted = (m.role == ProjectMember.ROLE_ADMIN
               and body.role != ProjectMember.ROLE_ADMIN)
    m.role = body.role
    await db.commit()
    if demoted:
        # M2b Q2:降级的管理员若是项目令牌负责人 → 提醒其余管理员换绑
        from .project_tokens import notify_holder_lost
        await notify_holder_lost(db, project_id, member_user_id)
    target = await db.get(User, member_user_id)
    await _audit(db, user, "project.member_role_changed", proj,
                 {"userId": member_user_id, "role": body.role})
    return MemberOut(userId=m.user_id,
                     username=target.username if target else "",
                     displayName=(target.display_name if target else "")
                     or (target.username if target else ""),
                     role=m.role)


@router.delete("/{project_id}/members/{member_user_id}",
               status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    user: CurrentUser, db: DbSession, project_id: int, member_user_id: int,
) -> None:
    proj = await _load_project(db, project_id)
    await _require_manage(db, user, proj)
    m = (await db.execute(select(ProjectMember).where(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == member_user_id))).scalar_one_or_none()
    if m is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found",
                    "message": f"member not found: {member_user_id}"})
    if m.role == ProjectMember.ROLE_ADMIN:
        admins = (await db.execute(select(func.count()).select_from(
            ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.role == ProjectMember.ROLE_ADMIN))
        ).scalar_one()
        if admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "last_project_admin",
                        "message": "最后一个项目管理员不能移除"
                                   "(项目不能无人可管)"})
    await _audit(db, user, "project.member_removed", proj,
                 {"userId": member_user_id})
    await db.delete(m)
    await db.commit()
    # M2b Q2:被移出的成员若是项目令牌负责人 → 提醒其余管理员换绑
    from .project_tokens import notify_holder_lost
    await notify_holder_lost(db, project_id, member_user_id)
