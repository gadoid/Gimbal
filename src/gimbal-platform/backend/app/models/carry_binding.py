"""carry 值层存储(spec §3.1;重构 2026-11-16 坐标定死 §1.7)。

null 语义(写死):行存在即声明注入,value=NULL 注入 JSON null(显式空);
行不存在才是"未配置",走降级链。值统一存 str(模板 ${var.x} 原样),
注入时按契约 type 宽松转换。

配置坐标 = (scope, config_key, field_path):
* scope 分层:公共项目层 < 项目层;``scope_id`` 多态指向
  projects.id / users.id,应用层校验,不落 FK;
* **环境维已退役(2026-11-17,redesign §8.4)**:环境只做轻量部署标签,
  不再承载 carry 配置层 —— 多服务共享一层配置时同名字段必然打架。
  原 ``env_id`` 覆盖行生产为 0,迁移 0058 直接删除;
* **实例档(2026-11-19,redesign §8.9)**:按部署差异化(测试/预发布/
  生产同字段不同值)的需求落**实例档** —— ``instance_env_id`` 非零行
  = (config_key=系统名, instance_env_id=环境) 实例键,替换原「系统名」
  粗档(系统级跨部署同值场景罕见,档位退场,存量 0 行守卫迁移 0063);
  语义与 §8.4 退役的「任意键 env 覆盖」不同:这是独立实例档,不是
  env 维覆盖。``instance_env_id=0`` = 条目/服务档基线行(默认)。
* ``config_key`` 层内解析序(**细到粗**,§8.9):身份条目名 >
  实例(system, env) > 服务名 > 层默认 —— 实例档压过服务档(部署
  差异化默认值),条目键压过一切;条目键 = 旧别名键(键域兼容,
  存量行自动落「服务」档)。
"""
from __future__ import annotations

from datetime import datetime

from ._types import UtcDateTime
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class CarryServiceBinding(Base):
    __tablename__ = "carry_service_bindings"
    __table_args__ = (
        # §8.9 五键:instance_env_id ∈ {0=基线行, 环境id=实例行}(sentinel
        # 0 避开 NULL 唯一性陷阱;同 config_key 两档并存靠该列区分)
        UniqueConstraint("scope", "scope_id", "config_key", "field_path",
                         "instance_env_id", name="uq_carry_svc_path"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # 配置键(§8.9):身份条目名 / 服务名 / 系统名(实例档专用,配
    # instance_env_id 非零)。读侧按层内链归一(条目键 > 实例键 >
    # 服务键 > 默认表);写侧整表替换按 (scope, config_key,
    # instance_env_id) 坐标操作。
    config_key: Mapped[str] = mapped_column(String(128))
    # §8.9 实例档:0 = 条目/服务档基线行(默认);非零 = 实例键行的
    # 环境 id(config_key 须为该环境实例行的系统名)
    instance_env_id: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0"))
    # S4:作用域('project'|'user';公共项目行 = 旧全局层)
    scope: Mapped[str] = mapped_column(String(16), nullable=False,
                                       default="project",
                                       server_default=text("'project'"))
    scope_id: Mapped[int] = mapped_column(Integer, nullable=False,
                                          default=0,
                                          server_default=text("0"))
    field_path: Mapped[str] = mapped_column(String(255))
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 三件套规范(§2.2):溯源列 FK SET NULL + 姓名快照
    updated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by_name: Mapped[str] = mapped_column(String(128), default="")
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now(), onupdate=func.now()
    )


class CarryGlobalDefault(Base):
    """层默认(旧名 global_defaults 保留;S4 起全局 = 公共项目层)。"""
    __tablename__ = "carry_global_defaults"
    __table_args__ = (
        UniqueConstraint("scope", "scope_id", "field_path",
                         name="uq_carry_default_path"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    field_path: Mapped[str] = mapped_column(String(255))
    scope: Mapped[str] = mapped_column(String(16), nullable=False,
                                       default="project",
                                       server_default=text("'project'"))
    scope_id: Mapped[int] = mapped_column(Integer, nullable=False,
                                          default=0,
                                          server_default=text("0"))
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 三件套规范(§2.2):溯源列 FK SET NULL + 姓名快照
    updated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by_name: Mapped[str] = mapped_column(String(128), default="")
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now(), onupdate=func.now()
    )
