"""项目区判定的共享上下文(M2a S1.1)。

三件小事,全部走 ``db.info`` 会话级缓存(请求内一次查询,谓词反复
求值不再打库):

* :func:`public_project_id` —— 公共项目 id(0040 种子,恰一行);
* :func:`my_project_roles` —— 主体在普通项目的角色表 ``{project_id:
  "admin"|"member"}``(公共项目不落成员行,天然不在表里 —— member /
  padmin 谓词因此不会把公共项目误当普通项目);
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
) -> None:
    """项目内新建门(authz M2a S7.0,D6「项目内可直接新建」):项目须存在
    (否则 404)、不是公共项目(422 —— 内容进公共项目只有「发布」一条路,
    S1.3)、主体是项目成员(非成员 404 不泄露存在性;D1:项目对象权限只看
    项目角色,Admin+ 不旁路)。"""
    proj = await db.get(Project, project_id)
    if proj is None:
        raise ProjectCreateDenied(404, "not_found",
                                  f"project not found: {project_id}")
    if proj.kind == "public":
        raise ProjectCreateDenied(
            422, "public_project_create_forbidden",
            "公共项目不能直接新建 —— 请在私有区创建后发布")
    role = (await my_project_roles(db, user_id)).get(project_id)
    if role is None:
        raise ProjectCreateDenied(404, "not_found",
                                  f"project not found: {project_id}")
    if role not in ProjectMember.WRITER_ROLES:
        # M2b Q1:项目用户只读 + 执行(项目可见,无写权 → 403)
        raise ProjectCreateDenied(
            403, "project_role_readonly",
            "项目用户只能读和执行项目内容,不能新建")


def zone_read_clause(model, viewer_id: int):
    """三区读谓词(带 owner_id + project_id 的任意模型):私有区属主 ∨
    我所在的普通项目 ∨ 公共项目 —— 场景 / suite / 报告定义列表共用
    (ref 分支由调用方叠加,且仅限私有区对象)。SQL 谓词单点,与
    ``routers._ownership.can`` 的表 B 求值同口径。"""
    from sqlalchemy import and_, or_, select as sa_select

    my = sa_select(ProjectMember.project_id).where(
        ProjectMember.user_id == viewer_id)
    pub = sa_select(Project.id).where(Project.kind == "public")
    return or_(
        and_(model.owner_id == viewer_id, model.project_id.is_(None)),
        model.project_id.in_(my),
        model.project_id.in_(pub),
    )


SUITE_ZONE_TRIGGER_DDL = (
    # S1.5 同区触发器(与 ensure_member_same_zone 同口径;0042 迁移与
    # 测试建库共用本单源 —— 测试库走 create_all 不跑迁移,由 conftest
    # 挂同一条触发器,保证端点测试有与生产一致的库层兜底)
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
    *, suite_project_id: int | None, suite_owner_id: int | None,
    scen_project_id: int | None, scen_owner_id: int | None,
    scenario_id: str,
) -> None:
    """S1.5 同区约束(应用层单点):套件成员场景与套件**同 project_id**;
    都为空(私有区)时再要求**同属主**(私有套件仍只放本人的场景)。
    项目套件自此可容纳其他成员的场景。违例 raise ValueError
    ``suite_member_cross_zone``(端点转 422;DB 触发器 0042 兜底
    直插绕过应用层的写法)。"""
    if suite_project_id is None and scen_project_id is None:
        if suite_owner_id != scen_owner_id:
            raise ValueError(
                "suite_member_cross_zone: "
                f"私有套件只能加入自己的场景({scenario_id} 属于他人)")
    elif suite_project_id != scen_project_id:
        raise ValueError(
            "suite_member_cross_zone: "
            f"套件与成员场景须同区({scenario_id} 不在本套件的项目里)")


def apply_public(row: Any, public_pid: int | None) -> None:
    """置公共态(project_id=公共项目)。S1.9/0043 删 visibility 列后
    只写 project_id —— 列的读写全切项目谓词,本函数是唯一写点之一。"""
    row.project_id = public_pid


def apply_private(row: Any) -> None:
    """置私有态(project_id=NULL = 私有区)。"""
    row.project_id = None


async def derive_visibility(db, project_id: int | None) -> str:
    """响应派生(S1.9):visibility 字段的替代口径 —— project_id 为空 =
    'private';公共项目 = 'public';普通项目 = 'private'(前端只把
    'public' 当公共徽章,普通项目内容不出公共页)。pid 走会话缓存。"""
    if project_id is None:
        return "private"
    return "public" if project_id == await public_project_id(db) else "private"
