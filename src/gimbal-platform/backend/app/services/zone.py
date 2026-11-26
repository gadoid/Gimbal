"""项目区判定的共享上下文(M2a S1.1)。

三件小事,全部走 ``db.info`` 会话级缓存(请求内一次查询,谓词反复
求值不再打库):

* :func:`public_project_id` —— 公共项目 id(0040 种子,恰一行);
* :func:`my_project_roles` —— 主体在普通项目的角色表 ``{project_id:
  "admin"|"member"|"user"}``(M2b Q1:项目用户只读 + 执行;公共项目
  不落成员行,天然不在表里 —— member / padmin 谓词因此不会把公共
  项目误当普通项目);
* :func:`apply_public` / :func:`apply_private` —— **影子写**(S1.1–
  S1.8):``visibility`` 与 ``project_id`` 必须同步翻转(public ⇔
  project_id=公共项目)。0040 迁入 + 0041 回填保证存量一致,新写入
  由这两个helper钉死;S1.9(0043)删 ``visibility`` 列后 ``apply_*``
  收敛为只写 ``project_id``。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.project import Project, ProjectMember

_INFO_PUBLIC = "zone:public_project_id"
_INFO_ROLES = "zone:project_roles:"


async def public_project_id(db: AsyncSession) -> int | None:
    """公共项目 id(None = 尚未种子,判定按「无公共项目」收口)。"""
    cached = db.info.get(_INFO_PUBLIC, "...")  # None 也是合法缓存值
    if cached != "...":
        return cached
    pid = (await db.execute(
        select(Project.id).where(Project.kind == "public"))).scalar_one_or_none()
    db.info[_INFO_PUBLIC] = pid
    return pid


async def my_project_roles(db: AsyncSession, user_id: int) -> dict[int, str]:
    """主体在普通项目的角色表(member / padmin 谓词数据源)。"""
    key = _INFO_ROLES + str(user_id)
    cached = db.info.get(key)
    if cached is not None:
        return cached
    rows = (await db.execute(
        select(ProjectMember.project_id, ProjectMember.role)
        .where(ProjectMember.user_id == user_id))).all()
    roles = {pid: role for pid, role in rows}
    db.info[key] = roles
    return roles


async def my_private_projects(db: AsyncSession, user_id: int) -> frozenset[int]:
    """主体拥有的全部私有空间 id 集合(会话级缓存)—— 表 B owner
    谓词(UPC M2:私有对象挂真实私有空间,owner 判定 = 空间所有权,
    owner_id 列降为审计快照)。"""
    key = "zone:private_projects:" + str(user_id)
    cached = db.info.get(key)
    if cached is not None:
        return cached
    rows = (await db.execute(
        select(Project.id).where(
            Project.kind == Project.KIND_PRIVATE,
            Project.owner_id == user_id))).scalars().all()
    value = frozenset(rows)
    db.info[key] = value
    return value


async def can_use_project_credentials(
    db: AsyncSession, user_id: int | None, project_id: int | None,
) -> bool:
    """项目凭证选用门(authz M2a S8):对象属**普通项目**且主体是该项目
    成员(任一角色)。公共项目不落成员行 → 天然 False(公共项目无项目
    凭证);Admin+ 不旁路(凭证是项目的,不是平台的)。"""
    if project_id is None or user_id is None:
        return False
    return project_id in await my_project_roles(db, user_id)


class ProjectCreateDenied(Exception):
    """项目内新建被拒(调用方映射 HTTP:404 / 403 / 422)。"""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


async def ensure_can_create_in_project(
    db: AsyncSession, user_id: int, project_id: int,
) -> "Project":
    """项目内新建门(UPC M2:三 kind 统一口径,资源创建目标解析的单
    校验点):项目须存在(404)、状态 active(§13.1 归档起禁止新写入,
    409)、公共项目 422(内容进公共项目只有「发布」一条路)、private
    仅所有者(非所有者 404 不泄露存在性)、normal 须可写成员(非成员
    404;项目用户只读 403,D1:Admin+ 不旁路)。返回校验过的项目行。"""
    proj = await db.get(Project, project_id)
    if proj is None:
        raise ProjectCreateDenied(404, "not_found",
                                  f"project not found: {project_id}")
    if proj.status != Project.STATUS_ACTIVE:
        raise ProjectCreateDenied(
            409, "project_not_active",
            f"项目状态为 {proj.status},禁止新写入(§13.1)")
    if proj.kind == Project.KIND_PUBLIC:
        raise ProjectCreateDenied(
            422, "public_project_create_forbidden",
            "公共项目不能直接新建 —— 请在私有空间创建后发布")
    if proj.kind == Project.KIND_PRIVATE:
        # owner 比较单点在 project_space/表 B 谓词;此处是创建门的一部分
        from .project_access import relation_of_project

        if relation_of_project(proj, user_id) != "owner":
            raise ProjectCreateDenied(404, "not_found",
                                      f"project not found: {project_id}")
        return proj
    role = (await my_project_roles(db, user_id)).get(project_id)
    if role is None:
        raise ProjectCreateDenied(404, "not_found",
                                  f"project not found: {project_id}")
    if role not in ProjectMember.WRITER_ROLES:
        # M2b Q1:项目用户只读 + 执行(项目可见,无写权 → 403)
        raise ProjectCreateDenied(
            403, "project_role_readonly",
            "项目用户只能读和执行项目内容,不能新建")
    return proj


def zone_read_clause(model, viewer_id: int):
    """对象可见性谓词(UPC M2 收口):project_id NOT NULL 后,对象
    可见 ≡ 所属项目可见 —— 私有空间属主 ∨ 普通项目成员 ∨ 公共项目。
    与 ``project_access.visible_projects_clause`` 同语义(项目级单点),
    本函数是**对象级** SQL 单点;AC-51 令两条路径返回一致的 ID 集合。
    旧「owner_id ∧ project_id IS NULL」私有区分支随 M2 资源迁移退役。"""
    from sqlalchemy import or_, select as sa_select

    my = sa_select(ProjectMember.project_id).where(
        ProjectMember.user_id == viewer_id)
    pub = sa_select(Project.id).where(Project.kind == Project.KIND_PUBLIC)
    priv = sa_select(Project.id).where(
        Project.kind == Project.KIND_PRIVATE,
        Project.owner_id == viewer_id)
    return or_(
        model.project_id.in_(priv),
        model.project_id.in_(my),
        model.project_id.in_(pub),
    )


SUITE_ZONE_TRIGGER_DDL = (
    # 历史链工件(0042 的执行体;UPC M2/0068 起 §20.6 复合 FK 取代
    # 本触发器 —— fresh 路径不再挂,链路径由 0042 挂上、0068 摘除,
    # 两路径最终结构一致 §20.4)。常量保留仅为让 0042 可导入执行,
    # 新代码不得引用。
    """
    CREATE OR REPLACE FUNCTION suite_member_same_zone()
    RETURNS trigger AS $$
    DECLARE
        s_pid int; s_owner int; c_pid int; c_owner int;
    BEGIN
        SELECT project_id, owner_id INTO s_pid, s_owner
          FROM suites WHERE id = NEW.suite_id;
        SELECT project_id, owner_id INTO c_pid, c_owner
          FROM composer_scenarios WHERE scenario_id = NEW.scenario_id;
        IF (s_pid IS NULL AND c_pid IS NULL) THEN
            IF s_owner IS DISTINCT FROM c_owner THEN
                RAISE EXCEPTION
                  'suite_member_cross_zone: 私有套件只能加入自己的场景';
            END IF;
        ELSIF s_pid IS DISTINCT FROM c_pid THEN
            RAISE EXCEPTION
              'suite_member_cross_zone: 套件与成员场景须同区';
        END IF;
        RETURN NEW;
    END $$ LANGUAGE plpgsql
    """,
    "DROP TRIGGER IF EXISTS trg_suite_member_same_zone ON suite_members",
    """
    CREATE TRIGGER trg_suite_member_same_zone
    BEFORE INSERT OR UPDATE OF suite_id, scenario_id ON suite_members
    FOR EACH ROW EXECUTE FUNCTION suite_member_same_zone()
    """,
)


def ensure_member_same_zone(
    *,
    suite_project_id: int | None, scen_project_id: int | None,
    scenario_id: str,
) -> None:
    """同区校验(应用层单点,UPC M2 §20.6):套件成员场景与套件同
    ``project_id``。旧「同空时同属主」分支随资源迁移退役 —— 私有区
    内容挂真实私有空间,两个私有空间即使同属一人也互斥(§5.1 硬同区
    按项目判)。违例 raise ValueError ``suite_member_cross_zone``
    (端点转 422;DB 侧由 0068 的两条复合外键兜底直插绕过)。"""
    if suite_project_id != scen_project_id:
        raise ValueError(
            "suite_member_cross_zone: "
            f"套件与成员场景须同区({scenario_id} 不在本套件的项目里)")


def apply_public(row: Any, public_pid: int | None) -> None:
    """置公共态(project_id=公共项目;发布路径唯一写点之一)。"""
    row.project_id = public_pid


async def apply_private_zone(
    db: AsyncSession, row: Any, owner_id: int,
) -> None:
    """置私有态(UPC M2):对象回到 **owner 的默认私有空间**(真实
    容器;下架/转私路径的写点)。旧 apply_private(project_id=None)
    随「空 = 私有区」语义退役;无默认空间 = 用户处置未完成,拒绝。"""
    from .project_space import get_default_private_project

    proj = await get_default_private_project(db, owner_id)
    if proj is None:
        raise ValueError(
            "default_space_missing: 用户没有默认私有空间,无法落私有区"
            "(用户处置未完成或异常状态)")
    row.project_id = proj.id


async def derive_visibility(db, project_id: int) -> str:
    """响应派生:公共项目 = 'public',其余(private/normal)= 'private'
    (前端只把 'public' 当公共徽章,普通项目内容不出公共页)。pid 走
    会话缓存。UPC M2:project_id 恒非空,None 分支随资源迁移退役。"""
    return "public" if project_id == await public_project_id(db) else "private"
