"""项目区管理面(UPC M1:v2.10 §4、§6、§9)。

* **创建**:private = 所有人可建自己的空间(§4 额外空间授权创建);
  normal = Admin+(``ops.write``,§4 授权创建)并指定首个项目管理员
  (受让人须在职、非系统用户);public 不可建(部分唯一索引钉死)。
* **可见性**:列表/详情/context 与对象读取共用
  ``services.project_access.visible_projects_clause`` —— 私有空间仅
  所有者可见,**Admin+ 不旁路**(AC-51;§6「Private 其他用户(含
  平台管理员)」全否)。不可见统一 404,不泄露存在性。
* **管理面**:private = 所有者(owner_id,无成员行);normal = 项目
  管理员 ∨ Admin+;public = 仅 Admin+(系统治理)。项目管理员
  (role=admin)管理本项目成员;**末位项目管理员保护** —— 最后一个
  admin 不能被移除或降级(DB 延迟约束触发器兜底)。
* **删除**:private = 所有者,默认空间受专门闸保护(§4);normal =
  Admin+ 且有内容 409 ``project_not_empty``(不做级联删除);公共项目
  不可删不可改 kind。
* **成员关系**:private/public 不落成员行(触发器钉死);普通成员行
  只增不改权限边界:读面由表 B / zone_read_clause 派生。审计:建/删/
  成员变更入审计(admin 面)。
"""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser, MemberUser
from ..models.project import Project, ProjectMember
from ..models.user import User
from ..policies import capabilities_of_kind
from ..services import project_access
from ..services.project_space import (
    create_private_space, dispose_private_containers,
)
from ._ownership import has_capability

router = APIRouter(prefix="/projects", tags=["projects"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


class ProjectCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=2000)
    # UPC §4:private(自己的空间,所有人可建)| normal(Admin+)
    kind: Literal["private", "normal"] = "normal"
    # normal 必填:首个项目管理员;private 不适用(所有者即治理者)
    firstAdminUserId: int | None = Field(default=None, ge=1)


class ProjectPatchIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    # S2.2 环境链第二位(§11:身份标签 > 项目默认 > 平台默认);显式传
    # null = 清空(未传 = 不动)
    defaultEnvironmentId: int | None = Field(default=None, ge=1)


class MemberIn(BaseModel):
    userId: int = Field(ge=1)
    # M2b Q1:user = 项目用户(只读 + 执行)
    role: Literal["admin", "member", "user"] = "member"


class MemberPatchIn(BaseModel):
    role: Literal["admin", "member", "user"]


class ProjectOut(BaseModel):
    id: int
    uid: str = ""
    name: str
    kind: str
    description: str
    # UPC §4:默认私有空间标记(仅 private)
    isDefault: bool = False
    status: str = Project.STATUS_ACTIVE
    memberCount: int = 0
    # 请求者在本项目的角色(admin = 项目管理员;None = 非成员 ——
    # 私有空间所有者不是成员行,治理由 owner_id 表达)
    myRole: str | None = None
    # S2.2:项目默认环境(环境链第二位;None = 未设置)
    defaultEnvironmentId: int | None = None
    # 请求者能否管理(私有 = 所有者;普通 = 项目管理员 ∨ Admin+;
    # 公共 = Admin+)—— 前端据此显隐成员管理 / 配置编辑
    canManage: bool = False
    # M2b Q1:请求者能否在项目内新建 / 修改内容(私有 = 所有者;
    # 普通项目 = 项目管理员 ∨ 项目成员;公共 = 恒 False,内容进公共
    # 项目只有「发布」一条路)—— 前端据此显隐写入口,后端仍是权威
    canWrite: bool = False
    # S7.0 读面:默认环境名 + 各类内容计数(页签徽标数据源)。
    # 列表端点也批量补齐(项目卡片统计行;待审批计数仅详情端点填)
    defaultEnvironmentName: str | None = None
    scenarioCount: int = 0
    suiteCount: int = 0
    taskCount: int = 0
    pendingPromotions: int = 0


class ProjectConfigurationSummary(BaseModel):
    """§9 ProjectConfigurationSummary:非秘密配置摘要(不返回秘密)。"""

    defaultEnvironmentId: int | None = None
    defaultEnvironmentName: str | None = None


class ProjectContextOut(BaseModel):
    """§9 ProjectContext:前端 ProjectLayout 的统一上下文入口。

    effectivePermissions = 主体关系求值(§6);capabilities = 容器
    能力矩阵(§7)。不返回秘密或全部对象级权限;对象状态约束由资源
    接口及后端实时判断。
    """

    id: int
    uid: str
    kind: str
    name: str
    isDefault: bool
    status: str
    effectivePermissions: dict[str, bool]
    capabilities: dict[str, bool]
    configuration: ProjectConfigurationSummary


class MemberOut(BaseModel):
    userId: int
    username: str
    displayName: str
    role: str
    addedAt: str | None = None
    # 成员在本项目的资产数(按 owner 归属聚合);
    # add/patch 单行返回不带计数(默认 0,列表口径才消费)
    scenarioCount: int = 0
    suiteCount: int = 0


async def _load_project(db: AsyncSession, project_id: int) -> Project:
    proj = await db.get(Project, project_id)
    if proj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found",
                    "message": f"project not found: {project_id}"})
    return proj


async def _load_visible_project(
    db: AsyncSession, user, project_id: int,
) -> tuple[Project, str | None]:
    """加载并按统一可见性判定(§6;AC-51 与列表同源):不可见统一 404,
    不泄露私有空间存在性。返回 (project, my_role)。"""
    proj = await _load_project(db, project_id)
    my_role = await _my_role(db, user, project_id)
    if not await project_access.can_view_project(db, user.id, proj):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found",
                    "message": f"project not found: {project_id}"})
    return proj, my_role


async def _my_role(db: AsyncSession, user, project_id: int) -> str | None:
    return (await db.execute(select(ProjectMember.role).where(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user.id))).scalar_one_or_none()


async def _require_manage(
    db: AsyncSession, user, project: Project,
) -> None:
    """管理面门:私有 = 所有者(Admin+ 不旁路,他人不可见 → 404);
    普通 = 项目管理员 ∨ Admin+;公共 = Admin+。成员但非项目管理员 403
    (项目可见,无管理权)。"""
    if project.kind == Project.KIND_PRIVATE:
        if project.owner_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "not_found",
                        "message": f"project not found: {project.id}"})
        return
    if has_capability(user, "ops.write"):
        return
    my_role = await _my_role(db, user, project.id)
    if my_role == ProjectMember.ROLE_ADMIN:
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


async def _env_name(db: AsyncSession, env_id: int | None) -> str | None:
    if env_id is None:
        return None
    from ..models.environment import Environment

    row = await db.get(Environment, env_id)
    return row.name if row is not None else None


# ── 项目 CRUD ──────────────────────────────────────────────────────
@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    user: CurrentUser, db: DbSession, body: ProjectCreateIn,
) -> ProjectOut:
    """建项目(§4):private = 自己的空间(所有人);normal = Admin+,
    指定首个项目管理员;public 不可建(uq_projects_public_kind 钉死)。"""
    if body.kind == Project.KIND_PRIVATE:
        if body.firstAdminUserId is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "private_space_no_admin_member",
                        "message": "私有空间不落成员行,无需指定管理员"
                                   "(所有者即治理者)"})
        # 名称所有者域内唯一(uq_projects_name_private):flush 与 commit
        # 任一阶段的违例都归一为 409
        try:
            proj = await create_private_space(
                db, owner_id=user.id, name=body.name,
                description=body.description)
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "project_name_taken",
                        "message": f"空间名已被使用:{body.name}"}) from e
        await db.refresh(proj)
        return ProjectOut(
            id=proj.id, uid=str(proj.project_uid), name=proj.name,
            kind=proj.kind, description=proj.description,
            isDefault=proj.is_default, status=proj.status,
            defaultEnvironmentId=proj.default_environment_id,
            myRole=None, canManage=True, canWrite=True)

    # normal:Admin+(§4 授权创建)
    if not has_capability(user, "ops.write"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "capability_forbidden",
                    "message": "需要技术运营权限(Admin+)"})
    if body.firstAdminUserId is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "first_admin_required",
                    "message": "普通项目须指定首个项目管理员"})
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
    return ProjectOut(id=proj.id, uid=str(proj.project_uid), name=proj.name,
                      kind=proj.kind, description=proj.description,
                      isDefault=proj.is_default, status=proj.status,
                      memberCount=1,
                      myRole=(await _my_role(db, user, proj.id)),
                      defaultEnvironmentId=proj.default_environment_id)


def _can_manage(user, proj: Project, my_role: str | None) -> bool:
    """管理权(与 ``_require_manage`` 同口径):私有 = 所有者;
    普通 = 项目管理员 ∨ Admin+;公共 = Admin+。"""
    if proj.kind == Project.KIND_PRIVATE:
        return proj.owner_id == user.id
    if has_capability(user, "ops.write"):
        return True
    return proj.kind != Project.KIND_PUBLIC and my_role == "admin"


def _can_write(user, proj: Project, my_role: str | None) -> bool:
    """项目内写权(M2b Q1,与表 B contributor 同口径):私有 = 所有者;
    普通项目 = 项目管理员 ∨ 项目成员(项目用户只读 + 执行);
    公共项目只走「发布」,恒 False。"""
    if proj.kind == Project.KIND_PRIVATE:
        return proj.owner_id == user.id
    if proj.kind == Project.KIND_PUBLIC:
        return False
    return my_role in ProjectMember.WRITER_ROLES


async def _detail_counts(db: AsyncSession, proj: Project) -> dict:
    """S7.0 详情读面:默认环境名 + 场景 / 用例集 / 集成模板计数
    (集成只数模板行,软删不计)+ 待审批加入申请数(页签徽标)。"""
    from ..models.composer_scenario import ComposerScenario
    from ..models.environment import Environment
    from ..models.integration_task import IntegrationTask
    from ..models.project_promotion import ProjectPromotion
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
        "pendingPromotions": await _count(select(ProjectPromotion).where(
            ProjectPromotion.project_id == proj.id,
            ProjectPromotion.status == "pending")),
    }


@router.get("/{project_id}/slot-status")
async def project_slot_status(
    user: CurrentUser, db: DbSession, project_id: int,
) -> dict:
    """身份条目装载状态(重构:槽位 → 条目;S7.3 项目配置页签,只读
    不落库):项目场景引用的身份条目 × 成员是否已装载(条目 ref 能在
    该成员池解析到账户即算;不给任何账号信息);S8 每条目另给
    ``projectBound``(项目池已覆盖)。门 = 项目成员(仅普通项目 ——
    公共项目内容走订阅,凭证是订阅者自己的事,本端点 422)。"""
    from ..models.auth_account import AuthAccount
    from ..models.composer_scenario import ComposerScenario
    from ..models.service import Service
    from ..models.service_identity import ServiceIdentity
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

    # 条目装载判定(与 run_prepare._resolve_identities 的 ref 语义同构,
    # 批量内存匹配:条目 → (system, env, ref) → 池内账户命中)
    idents = {i.alias_name: i for i in (await db.execute(
        select(ServiceIdentity).where(
            ServiceIdentity.alias_name.in_(slots)))).scalars().all()} \
        if slots else {}
    system_of = dict((await db.execute(
        select(Service.name, Service.system).where(
            Service.name.in_({i.base_service for i in idents.values()}))
    )).all()) if idents else {}

    def _loaded(accounts: list) -> set[str]:
        """池内账户 → 已装载条目名集合(ref 匹配;§8.3 不校验标签)。"""
        out: set[str] = set()
        by_key: set[tuple[str, str]] = {
            (a.system, a.username) for a in accounts}
        default_hit: set[str] = set()
        for a in accounts:
            if a.is_default:
                default_hit.add(a.system)
        for name, ident in idents.items():
            sysname = system_of.get(ident.base_service)
            if not sysname:
                continue
            if ident.ref_mode == "username":
                if (sysname, ident.ref_username) in by_key:
                    out.add(name)
            elif sysname in default_hit:
                out.add(name)
        return out

    member_ids = [m[0] for m in members]
    bound: dict[int, set[str]] = {uid: set() for uid in member_ids}
    if slots and member_ids:
        accs = (await db.execute(
            select(AuthAccount).where(
                AuthAccount.owner_id.in_(member_ids)))).scalars().all()
        by_owner: dict[int, list] = {}
        for a in accs:
            by_owner.setdefault(a.owner_id, []).append(a)
        bound = {uid: _loaded(by_owner.get(uid, [])) for uid in member_ids}
    # S8:项目池是否覆盖该条目(成员可切换为项目账户执行)
    project_bound: set[str] = set()
    if slots:
        proj_accs = (await db.execute(
            select(AuthAccount).where(
                AuthAccount.project_id == project_id))).scalars().all()
        project_bound = _loaded(proj_accs)
    return {"slots": [{
        "slot": slot,
        "scenarios": sorted(slot_scenarios[slot]),
        "projectBound": slot in project_bound,
        "members": [{"userId": uid, "username": uname,
                     "displayName": disp or uname,
                     "bound": slot in bound.get(uid, set())}
                    for uid, uname, disp in members],
    } for slot in slots]}


@router.get("", response_model=list[ProjectOut])
async def list_projects(user: CurrentUser, db: DbSession) -> list[ProjectOut]:
    """项目列表(统一可见性谓词,AC-51 与 /auth/me、详情、context 同源):
    公共项目 + 我所在的普通项目 + **我的私有空间**。Admin+ 不旁路 ——
    平台管理员看不见他人私有空间(§6 授权矩阵)。"""
    roles = {pid: role for pid, role in (await db.execute(
        select(ProjectMember.project_id, ProjectMember.role).where(
            ProjectMember.user_id == user.id))).all()}
    projs = (await db.execute(
        select(Project).where(
            project_access.visible_projects_clause(user.id))
        .order_by((Project.kind != Project.KIND_PUBLIC), Project.id))
    ).scalars().all()
    counts = {pid: n for pid, n in (await db.execute(
        select(ProjectMember.project_id, func.count()).group_by(
            ProjectMember.project_id))).all()}

    # 批量统计(可见项目集合一次 group_by;空集合跳过)
    scenario_n: dict[int, int] = {}
    suite_n: dict[int, int] = {}
    task_n: dict[int, int] = {}
    env_names: dict[int, str] = {}
    if projs:
        from ..models.composer_scenario import ComposerScenario
        from ..models.environment import Environment
        from ..models.integration_task import IntegrationTask
        from ..models.suite import Suite

        pids = [p.id for p in projs]

        async def _group_n(stmt) -> dict[int, int]:
            return {pid: n for pid, n in (await db.execute(stmt)).all()}

        scenario_n = await _group_n(
            select(ComposerScenario.project_id, func.count())
            .where(ComposerScenario.project_id.in_(pids))
            .group_by(ComposerScenario.project_id))
        suite_n = await _group_n(
            select(Suite.project_id, func.count())
            .where(Suite.project_id.in_(pids))
            .group_by(Suite.project_id))
        task_n = await _group_n(
            select(IntegrationTask.project_id, func.count())
            .where(IntegrationTask.project_id.in_(pids),
                   IntegrationTask.template_id.is_(None),
                   IntegrationTask.removed_at.is_(None))
            .group_by(IntegrationTask.project_id))
        env_ids = {p.default_environment_id for p in projs
                   if p.default_environment_id is not None}
        if env_ids:
            env_names = {eid: name for eid, name in (await db.execute(
                select(Environment.id, Environment.name)
                .where(Environment.id.in_(env_ids)))).all()}

    return [ProjectOut(
        id=p.id, uid=str(p.project_uid), name=p.name, kind=p.kind,
        description=p.description, isDefault=p.is_default, status=p.status,
        memberCount=counts.get(p.id, 0),
        myRole=roles.get(p.id),
        defaultEnvironmentId=p.default_environment_id,
        canManage=_can_manage(user, p, roles.get(p.id)),
        canWrite=_can_write(user, p, roles.get(p.id)),
        defaultEnvironmentName=env_names.get(p.default_environment_id)
        if p.default_environment_id is not None else None,
        scenarioCount=scenario_n.get(p.id, 0),
        suiteCount=suite_n.get(p.id, 0),
        taskCount=task_n.get(p.id, 0)) for p in projs]


@router.get("/{project_id}/context", response_model=ProjectContextOut)
async def project_context(
    user: CurrentUser, db: DbSession, project_id: int,
) -> ProjectContextOut:
    """§9 ProjectContext:ProjectLayout 的统一上下文(可见性与列表同源,
    不可见 404;不返回秘密与全部对象级权限)。"""
    proj, my_role = await _load_visible_project(db, user, project_id)
    return ProjectContextOut(
        id=proj.id, uid=str(proj.project_uid), kind=proj.kind,
        name=proj.name, isDefault=proj.is_default, status=proj.status,
        effectivePermissions=project_access.effective_permissions(
            user, proj, my_role),
        capabilities=capabilities_of_kind(proj.kind),
        configuration=ProjectConfigurationSummary(
            defaultEnvironmentId=proj.default_environment_id,
            defaultEnvironmentName=await _env_name(
                db, proj.default_environment_id)))


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    user: CurrentUser, db: DbSession, project_id: int,
) -> ProjectOut:
    """项目详情(可见性与列表同源,AC-51):不可见统一 404 ——
    私有空间对他者(含 Admin+)不存在;公共项目全员可读。"""
    proj, my_role = await _load_visible_project(db, user, project_id)
    return ProjectOut(
        id=proj.id, uid=str(proj.project_uid), name=proj.name,
        kind=proj.kind, description=proj.description,
        isDefault=proj.is_default, status=proj.status,
        memberCount=await _member_count(db, project_id),
        myRole=my_role,
        defaultEnvironmentId=proj.default_environment_id,
        canManage=_can_manage(user, proj, my_role),
        canWrite=_can_write(user, proj, my_role),
        **await _detail_counts(db, proj))


@router.patch("/{project_id}", response_model=ProjectOut)
async def patch_project(
    user: CurrentUser, db: DbSession, project_id: int, body: ProjectPatchIn,
) -> ProjectOut:
    proj, _ = await _load_visible_project(db, user, project_id)
    await _require_manage(db, user, proj)
    if proj.kind == Project.KIND_PUBLIC:
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
    return ProjectOut(
        id=proj.id, uid=str(proj.project_uid), name=proj.name,
        kind=proj.kind, description=proj.description,
        isDefault=proj.is_default, status=proj.status,
        memberCount=await _member_count(db, project_id),
        myRole=await _my_role(db, user, project_id),
        defaultEnvironmentId=proj.default_environment_id)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    user: CurrentUser, db: DbSession, project_id: int,
) -> None:
    """删项目(§4/§13):private = 所有者,默认空间专门闸保护
    (default_space_protected);normal = Admin+(§4 授权删除);公共项目
    409。有内容 409(project_not_empty,不做级联删除,先清空或迁走);
    成员行随 CASCADE 消失(项目没了,成员关系无意义)。"""
    proj = await _load_project(db, project_id)
    if proj.kind == Project.KIND_PRIVATE:
        # 不可见统一 404(与列表/详情同源)
        if proj.owner_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "not_found",
                        "message": f"project not found: {project_id}"})
        if proj.is_default:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "default_space_protected",
                        "message": "默认私有空间不可删除;须先原子切换默认"
                                   "空间或走用户处置流程(§4/§13)"})
    else:
        if not has_capability(user, "ops.write"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "capability_forbidden",
                        "message": "删除普通项目需要技术运营权限(Admin+)"})
        if proj.kind == Project.KIND_PUBLIC:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "public_project_protected",
                        "message": "公共项目不可删除"})
    # 内容闸:五张对象表任一挂靠即拒(UPC M2:账户组合进闸,AC-22)
    from sqlalchemy import select as _sel

    from ..models.account_combo import AccountCombo
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
        occupied = (await db.execute(_sel(AccountCombo.id).where(
            AccountCombo.project_id == project_id).limit(1))
        ).scalar_one_or_none()
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
                    "message": "项目内仍有内容(场景/套件/组合/集成模板"
                               "/报告定义),需先清空或迁走再删除"})
    await _audit(db, user, "project.deleted", proj, {"name": proj.name})
    # S8:项目账户随项目删除(FK NO ACTION —— 显式删,凭证是项目的配置
    # 不是内容,不进内容闸)
    from sqlalchemy import delete as _del

    from ..models.auth_account import AuthAccount
    await db.execute(_del(AuthAccount).where(
        AuthAccount.project_id == project_id))
    # M2b Q2:项目令牌随项目删除吊销(令牌行留档,终态只读)
    from .project_tokens import revoke_all_for_project
    await revoke_all_for_project(db, project_id)
    await db.delete(proj)
    await db.commit()


# ── 实例 × 凭证匹配 ────────────────────────
class MatchAddrOut(BaseModel):
    service: str
    baseUrl: str


class MatchCredOut(BaseModel):
    id: int
    # 成员视图脱敏(username='',与项目凭证列表同口径)
    username: str
    isDefault: bool


class MatchInstanceOut(BaseModel):
    system: str
    tags: list[str] = Field(default_factory=list)
    loginUrl: str | None = None
    line: str | None = None
    addresses: list[MatchAddrOut] = Field(default_factory=list)
    projectCredentials: list[MatchCredOut] = Field(default_factory=list)
    personalCount: int = 0


class InstanceCredentialMatchOut(BaseModel):
    envId: int
    canManage: bool
    instances: list[MatchInstanceOut] = Field(default_factory=list)


@router.get("/{project_id}/instance-credential-matches",
            response_model=InstanceCredentialMatchOut)
async def instance_credential_matches(
    user: CurrentUser, db: DbSession, project_id: int,
    env_id: Annotated[int, Query(alias="envId", ge=1)],
) -> InstanceCredentialMatchOut:
    """服务实例 × 凭证匹配聚合(A 级批次):配置页「实例×凭证匹配」分区
    原由前端拼 5 路端点(instances/deployments/services/项目凭证/个人
    凭证),此处一次拉齐。行 = 环境下注册簿实例,按 (system, env) 拼
    部署地址与两池凭证 —— 与前端 MatchRow 形状对齐。

    门与项目凭证列表同口径:普通项目成员(Admin+ 非成员同 404);
    非管理员成员的 username 脱敏(_member_view 同款)。"""
    from ..models.auth_account import AuthAccount
    from ..models.deployment import Deployment
    from ..models.environment import Environment as Env
    from ..models.service import Service
    from ..models.system_env_instance import SystemEnvInstance

    proj = await _load_project(db, project_id)
    # §7 矩阵:项目凭证池仅 normal 开放(private/public API 同样拒绝)
    if proj.kind != Project.KIND_NORMAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "project_kind_no_credentials",
                    "message": "私有/公共项目没有项目凭证池"
                               "(公共内容由订阅者用自己的凭证执行;私有"
                               "空间凭证为个人池)"})
    role = await _my_role(db, user, project_id)
    if role is None:
        # Admin+ 非成员同 404(读面不因平台角色放宽,与凭证列表一致)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found",
                    "message": f"project not found: {project_id}"})
    can_manage = role == "admin"

    inst_rows = (await db.execute(
        select(SystemEnvInstance).where(
            SystemEnvInstance.env_id == env_id)
        .order_by(SystemEnvInstance.system))).scalars().all()
    # 同组标签集(一实例多标签;与 services.list_instances 同口径)
    from .services import _tags_by_group

    tags_by_group = await _tags_by_group(
        db, {inst.group_id for inst in inst_rows})
    # 部署地址(按 env 收敛;服务名→系统名经主档翻译)
    dep_rows = (await db.execute(
        select(Deployment).where(Deployment.env_id == env_id))).scalars().all()
    svc_system = dict((await db.execute(
        select(Service.name, Service.system))).all())
    # 项目凭证(按 env 过滤;非管理员脱敏 username)
    proj_creds = (await db.execute(
        select(AuthAccount).where(
            AuthAccount.project_id == project_id,
            AuthAccount.env_id == env_id))).scalars().all()
    # 个人池只数计数(本人在该 (system, env) 的凭证数)
    mine_counts = dict((await db.execute(
        select(AuthAccount.system, func.count())
        .where(AuthAccount.owner_id == user.id,
               AuthAccount.env_id == env_id)
        .group_by(AuthAccount.system))).all())

    instances = [
        MatchInstanceOut(
            system=inst.system,
            tags=tags_by_group.get(inst.group_id, []),
            loginUrl=inst.login_url, line=inst.line,
            addresses=[
                MatchAddrOut(service=d.base_service, baseUrl=d.base_url)
                for d in dep_rows
                if svc_system.get(d.base_service) == inst.system],
            projectCredentials=[
                MatchCredOut(
                    id=c.id,
                    username=c.username if can_manage else "",
                    isDefault=bool(c.is_default))
                for c in proj_creds if c.system == inst.system],
            personalCount=mine_counts.get(inst.system, 0),
        )
        for inst in inst_rows]
    return InstanceCredentialMatchOut(
        envId=env_id, canManage=can_manage, instances=instances)


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
    # 成员 × 本项目资产数(A 级批次):owner 归属权威,按 (project_id,
    # owner_id) 一次 GROUP BY(照 list_projects 的 _group_n 模板)。
    from ..models.composer_scenario import ComposerScenario
    from ..models.suite import Suite

    async def _owner_n(stmt) -> dict[int, int]:
        return {uid: n for uid, n in (await db.execute(stmt)).all()}

    scenario_n = await _owner_n(
        select(ComposerScenario.owner_id, func.count())
        .where(ComposerScenario.project_id == project_id)
        .group_by(ComposerScenario.owner_id))
    suite_n = await _owner_n(
        select(Suite.owner_id, func.count())
        .where(Suite.project_id == project_id)
        .group_by(Suite.owner_id))
    return [MemberOut(
        userId=m.user_id, username=u.username,
        displayName=u.display_name or u.username, role=m.role,
        addedAt=m.added_at.isoformat() if m.added_at else None,
        scenarioCount=scenario_n.get(m.user_id, 0),
        suiteCount=suite_n.get(m.user_id, 0))
        for m, u in rows]


@router.post("/{project_id}/members", response_model=MemberOut,
             status_code=status.HTTP_201_CREATED)
async def add_member(
    user: CurrentUser, db: DbSession, project_id: int, body: MemberIn,
) -> MemberOut:
    proj = await _load_project(db, project_id)
    await _require_manage(db, user, proj)
    # 成员行守卫:不变量「private/public 不落成员行」(§4/§20,触发器
    # 兜底直插绕过应用层的写)—— 只有 normal 有成员概念
    if proj.kind != Project.KIND_NORMAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "project_kind_no_members",
                    "message": "私有/公共项目无成员概念,不可添加成员"})
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
    # 成员行守卫(与 add_member 同闸同码;private/public 不落成员行)
    if proj.kind != Project.KIND_NORMAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "project_kind_no_members",
                    "message": "私有/公共项目无成员概念,不可修改成员"})
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
    # 公共项目**不设** add/patch 守卫同款 409:
    # remove 是 B1 窗口期遗留成员行的唯一 API 补救通道 —— 全闸会把病害
    # 锁进库(can_run_scenario 纯查成员表,残留行即活越权面)。放行删除 =
    # 朝「公共项目无成员行」不变量收敛;存量行当前为 0,守卫语义不变。
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
    # 01-03 §4.1:被移出成员在本项目模板上的持有实例(含其自建的
    # owner 实例)联动暂停 —— 执行前成员闸是权威,这里是即时收口 +
    # 人话通知(与令牌换绑提醒同挂 remove 之后)。
    from ..services import integration_runner as _ir
    await _ir.pause_instances_of_removed_member(project_id, member_user_id)
