"""UPC-01 Project 容器模型(v2.10 §4、§20):统一资源治理容器。

三区收敛为「真实容器」:private / public / normal 三种 kind 共用同一
模型、服务与页面;kind 表达治理方式,不表达资源结构(v2.10 §1)。

* ``Project``:kind ∈ {private, public, normal}。private 由 ``owner_id``
  表达所有权(每用户可多个,恰一个默认);public 平台恰一行(部分唯一
  索引,系统初始化,不可普通删除);normal 由成员治理,无个人 Owner。
  ``created_by`` 仅审计,不赋权。
* ``project_uid``:服务端生成的不可复用身份(§13.2)—— UUID,唯一非空,
  历史快照按此关联项目,重建同名/同数值 ID 项目无权继承旧历史。
* ``status``:active / archived / deleting / delete_failed(§13.1 状态机;
  M1 落列与约束,处置流程随 M2+ 实现)。
* 库层约束(§20 不变量表,CREATE 全部三路径共享 ``PROJECT_CONTAINER_DDL``):
  kind CHECK、private↔owner 形状 CHECK、is_default 仅 private CHECK、
  每用户至多一个默认私有空间(部分唯一索引)、public 唯一、名称按
  kind 分域唯一;成员行触发器:private/public 不落成员行、活跃 normal
  至少一名有效 admin(延迟约束触发器)、每个非系统用户至少一个默认
  私有空间(延迟约束触发器,注册/建号/迁移事务内保证)。

旧「project_id 空 = 私有区」语义保留在对象表侧,随 M2 资源迁移收口;
本表先就位为唯一容器事实源。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text,
    Uuid, func, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import UtcDateTime


class Project(Base):
    """统一项目容器(UPC-01)。"""

    # kind 取值常量(权威;DB 侧由 ck_projects_kind 钉死)
    KIND_PRIVATE = "private"
    KIND_PUBLIC = "public"
    KIND_NORMAL = "normal"
    KINDS = (KIND_PRIVATE, KIND_PUBLIC, KIND_NORMAL)

    # 生命周期状态(§13.1;M1 先落列与约束,状态机流程随 M2+)
    STATUS_ACTIVE = "active"
    STATUS_ARCHIVED = "archived"
    STATUS_DELETING = "deleting"
    STATUS_DELETE_FAILED = "delete_failed"
    STATUSES = (STATUS_ACTIVE, STATUS_ARCHIVED, STATUS_DELETING,
                STATUS_DELETE_FAILED)

    __tablename__ = "projects"
    __table_args__ = (
        # 公共项目恰一行:部分唯一索引(DB 层钉死「不可再建公共项目」)
        Index("uq_projects_public_kind", "kind", unique=True,
              postgresql_where=text("kind = 'public'")),
        # 每用户至多一个默认私有空间(§4 部分唯一索引 —— AC-01 并发权威)
        Index("uq_projects_private_default", "owner_id", unique=True,
              postgresql_where=text(
                  "kind = 'private' AND is_default")),
        # 名称分域唯一(§4):private 在所有者域内、normal 在平台域内;
        # public 恒一行,系统标识,名称不参与唯一。全局唯一索引随 0067 删除。
        Index("uq_projects_name_private", "owner_id", "name", unique=True,
              postgresql_where=text("kind = 'private'")),
        Index("uq_projects_name_normal", "name", unique=True,
              postgresql_where=text("kind = 'normal'")),
        Index("ix_projects_kind", "kind"),
        CheckConstraint(
            "kind IN ('private', 'public', 'normal')", name="ck_projects_kind"),
        # 归属形状:private 必有 owner;public/normal 必无 owner
        CheckConstraint(
            "(kind = 'private' AND owner_id IS NOT NULL) "
            "OR (kind <> 'private' AND owner_id IS NULL)",
            name="ck_projects_owner_shape"),
        # 默认标记仅对 private 有意义(§4 is_default 仅适用于 private)
        CheckConstraint(
            "NOT is_default OR kind = 'private'",
            name="ck_projects_default_private"),
        CheckConstraint(
            "status IN ('active', 'archived', 'deleting', 'delete_failed')",
            name="ck_projects_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # §13.2 不可复用项目身份:服务端生成,唯一非空,禁止客户端指定
    project_uid: Mapped[str] = mapped_column(
        Uuid, nullable=False, unique=True,
        server_default=func.gen_random_uuid())
    name: Mapped[str] = mapped_column(String(128))
    # private | public | normal(常量见上;CHECK 钉死取值)
    # server_default 与 0040 链上形态对齐(§20.4 双路径一致性)
    kind: Mapped[str] = mapped_column(
        String(16), default="normal", server_default="normal")
    description: Mapped[str] = mapped_column(
        Text, default="", server_default="")
    # 私有空间所有者(private 必非空,public/normal 必空 —— CHECK 钉死)。
    # 不加 ON DELETE:用户删除须先处置私有容器(§13),库层 FK 兜底拦住
    # 未处置直删(与 suites.owner_id 同口径)。
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True)
    # 建项目的人(审计;公共项目行指 __platform__;created_by 不赋予权限)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # 默认私有空间标记(仅 private;每用户至多一个 —— 部分唯一索引)
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false"))
    # 生命周期(§13.1;Deleting 起禁止新写入/授权/执行/调度)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active",
        server_default=text("'active'"))
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now())
    # 环境链第二位(§11:身份标签 > 项目默认 > 平台默认);删环境置空
    default_environment_id: Mapped[int | None] = mapped_column(
        ForeignKey("environments.id", ondelete="SET NULL"), nullable=True)


class ProjectMember(Base):
    """普通项目的成员行;private/public 不落行(触发器钉死,见
    ``PROJECT_CONTAINER_DDL``)。"""

    # 成员角色常量(比较单点:角色字面量守卫的清零终态不回退 ——
    # 用户角色字面量在表 A/表 B,成员角色只在模型常量)
    ROLE_ADMIN = "admin"
    ROLE_MEMBER = "member"
    # M2b Q1 项目用户:只读 + 执行(读 / 复制 / 执行 / 订阅 / 选用项目
    # 凭证;不能新建 / 修改 / 删除 / 提升)
    ROLE_USER = "user"
    # 可写角色(表 B contributor 谓词与项目内新建 / 提升门的单一来源)
    WRITER_ROLES = frozenset({ROLE_ADMIN, ROLE_MEMBER})

    __tablename__ = "project_members"
    __table_args__ = (
        # 「我的项目」反查(/auth/me.projects、visibility_clause)
        Index("ix_project_members_user", "user_id"),
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    # admin(项目管理员)| member | user(M2b 项目用户,只读 + 执行);
    # S1.1 的 padmin / member 谓词数据源;server_default 与 0040 对齐
    role: Mapped[str] = mapped_column(
        String(16), default="member", server_default="member")
    added_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    added_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now())


# ── 共享触发器/函数 DDL(单源)────────────────────────────────────────
# 三路径共用:0067 迁移(增量链)、ensure_schema_sync(空库 fresh 路径)、
# conftest(测试库 create_all 后补挂)—— §20.4 双初始化路径结构一致
# 的前提是不变量全部经由本清单,任何新触发器只改这里(与
# zone.SUITE_ZONE_TRIGGER_DDL 同纪律)。

_PROJECT_ADMIN_REQUIRED = """
    IF EXISTS (SELECT 1 FROM projects p
               WHERE p.id = {pid} AND p.kind = 'normal'
                 AND p.status = 'active')
       AND NOT EXISTS (
           SELECT 1 FROM project_members m
           JOIN users u ON u.id = m.user_id
           WHERE m.project_id = {pid} AND m.role = 'admin'
             AND u.is_active AND NOT u.is_system) THEN
        RAISE EXCEPTION
          'project_admin_required: 活跃普通项目须至少一名有效管理员'
          USING ERRCODE = '23514';
    END IF;
"""

PROJECT_CONTAINER_DDL: tuple[str, ...] = (
    # ① 成员行守卫:private/public 项目不落成员行(§20「Private/Public
    #    无成员行」;应用层 add/patch/remove 的公共守卫是快路径,DB 是权威)
    """
    CREATE OR REPLACE FUNCTION project_member_kind_guard()
    RETURNS trigger AS $$
    DECLARE pk text;
    BEGIN
        SELECT kind INTO pk FROM projects WHERE id = NEW.project_id;
        IF pk IS DISTINCT FROM 'normal' THEN
            RAISE EXCEPTION
              'project_member_kind: kind=% 的项目不落成员行', pk
              USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END $$ LANGUAGE plpgsql
    """,
    "DROP TRIGGER IF EXISTS trg_project_member_kind_guard ON project_members",
    """
    CREATE TRIGGER trg_project_member_kind_guard
    BEFORE INSERT OR UPDATE OF project_id, user_id, role
    ON project_members
    FOR EACH ROW EXECUTE FUNCTION project_member_kind_guard()
    """,
    # ② kind 创建后不可普通修改(§20;publicize/transfer 是资产迁移,
    #    不是改 kind —— 三区结构互转没有合法入口)
    """
    CREATE OR REPLACE FUNCTION project_kind_immutable()
    RETURNS trigger AS $$
    BEGIN
        IF NEW.kind IS DISTINCT FROM OLD.kind THEN
            RAISE EXCEPTION
              'project_kind_immutable: kind 创建后不可修改'
              USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END $$ LANGUAGE plpgsql
    """,
    "DROP TRIGGER IF EXISTS trg_project_kind_immutable ON projects",
    """
    CREATE TRIGGER trg_project_kind_immutable
    BEFORE UPDATE OF kind ON projects
    FOR EACH ROW EXECUTE FUNCTION project_kind_immutable()
    """,
    # ③ 活跃 normal 至少一名有效 admin —— 延迟约束触发器(§20;覆盖
    #    成员增删改;用户停用经 ⑤,用户删除经成员行 CASCADE 亦落此处)
    """
    CREATE OR REPLACE FUNCTION project_member_admin_invariant()
    RETURNS trigger AS $$
    DECLARE pid int;
    BEGIN
        pid := COALESCE(NEW.project_id, OLD.project_id);
        %s
        RETURN NULL;
    END $$ LANGUAGE plpgsql
    """ % _PROJECT_ADMIN_REQUIRED.format(pid="pid"),
    """
    DROP TRIGGER IF EXISTS trg_project_member_admin_invariant
    ON project_members
    """,
    """
    CREATE CONSTRAINT TRIGGER trg_project_member_admin_invariant
    AFTER INSERT OR UPDATE OR DELETE ON project_members
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION project_member_admin_invariant()
    """,
    # ④ 项目侧不变量:活跃 normal 无论新建还是归档恢复(active ←
    #    archived)都须有有效 admin —— 延迟约束触发器(新建项目 +
    #    首个 admin 同事务提交,顺序无关;active → archived 合法,
    #    要求随之解除)
    """
    CREATE OR REPLACE FUNCTION project_admin_invariant()
    RETURNS trigger AS $$
    BEGIN
        IF NEW.kind = 'normal' AND NEW.status = 'active' THEN
            %s
        END IF;
        RETURN NULL;
    END $$ LANGUAGE plpgsql
    """ % _PROJECT_ADMIN_REQUIRED.format(pid="NEW.id"),
    """
    DROP TRIGGER IF EXISTS trg_project_admin_invariant
    ON projects
    """,
    """
    CREATE CONSTRAINT TRIGGER trg_project_admin_invariant
    AFTER INSERT OR UPDATE OF status ON projects
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION project_admin_invariant()
    """,
    # ⑤ 用户停用不击穿「活跃 normal ≥1 有效 admin」(§20:覆盖用户
    #    停用;用户删除走成员行 CASCADE → ③ 兜底)
    """
    CREATE OR REPLACE FUNCTION user_active_admin_invariant()
    RETURNS trigger AS $$
    DECLARE pid int;
    BEGIN
        FOR pid IN SELECT m.project_id FROM project_members m
                   WHERE m.user_id = NEW.id AND m.role = 'admin' LOOP
            %s
        END LOOP;
        RETURN NULL;
    END $$ LANGUAGE plpgsql
    """ % _PROJECT_ADMIN_REQUIRED.format(pid="pid"),
    """
    DROP TRIGGER IF EXISTS trg_user_active_admin_invariant ON users
    """,
    """
    CREATE CONSTRAINT TRIGGER trg_user_active_admin_invariant
    AFTER UPDATE OF is_active ON users
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION user_active_admin_invariant()
    """,
    # ⑥ 每个非系统用户至少一个默认私有空间(§4/§20)—— 延迟约束
    #    触发器:注册/建号/迁移在同一事务内创建,提交时校验;系统用户
    #    (__platform__)排除
    """
    CREATE OR REPLACE FUNCTION user_default_space_invariant()
    RETURNS trigger AS $$
    BEGIN
        IF NOT NEW.is_system AND NOT EXISTS (
            SELECT 1 FROM projects p
            WHERE p.kind = 'private' AND p.owner_id = NEW.id
              AND p.is_default) THEN
            RAISE EXCEPTION
              'user_default_space_required: 每个非系统用户须至少一个'
              '默认私有空间(%)', NEW.id
              USING ERRCODE = '23514';
        END IF;
        RETURN NULL;
    END $$ LANGUAGE plpgsql
    """,
    """
    DROP TRIGGER IF EXISTS trg_user_default_space_invariant ON users
    """,
    """
    CREATE CONSTRAINT TRIGGER trg_user_default_space_invariant
    AFTER INSERT OR UPDATE OF is_system ON users
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION user_default_space_invariant()
    """,
)
