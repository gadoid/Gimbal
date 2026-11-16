"""ServiceIdentity model — 身份条目(重构 §1.3;替代 service_aliases)。

条目 = 「某环境某服务以什么身份登录」的引用声明,**不内嵌任何密码**
(决策 5:声明与凭证解耦落到表结构)。一个 (env, 服务) 下可挂多套
条目(普通/管理员/只读等多角色身份,决策 4 的差异化出口)。

* ``alias_name`` = 引用键(uq)—— 场景 ``${auth.X}`` / ``${slot.X.*}`` /
  ``call.user=X`` / token scope / 数据集行绑定全部按此名引用。
  命名规约延续 ``<服务名>-<后缀>``(决策 7:场景键稳定是架构决策,
  存量键天然落位,**不写旧形态适配分支**);**不可改名**(改名 = 删旧
  建新,引用全断);
* ``base_service`` = 服务锚(→ services.name 逻辑关联,与 deployments
  同风格不落硬 FK;resolve_base/地址解析按服务名);
* ``env_id`` **必填**(环境显式化:别名词缀模拟环境词缀的历史到此
  为止;环境删除 → 条目级联删,同部署行语义);
* ``ref_mode``/``ref_username`` = 对账户的引用:
  - ``default``:取 (执行人池, 条目系统, env) 的 is_default 账户;
  - ``username``:取同域 ``ref_username`` 账户(多条目共享同一账户
    即「一个凭证装载在多套身份上」的实现)。

条目的系统归属经 base_service → services.system 派生(解析时 join,
不冗余存,目录改名由对账兜底)。管理面在环境配置页(旧服务子页迁居)。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import UtcDateTime


class ServiceIdentity(Base):
    __tablename__ = "service_identities"
    __table_args__ = (
        # 服务聚合查询面(环境配置页按 (服务, 环境) 分组)
        Index("ix_identity_service_env", "base_service", "env_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # 引用键(决策 7;uq 由应用层校验 + 唯一索引双保险)
    alias_name: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True)
    base_service: Mapped[str] = mapped_column(String(128), nullable=False)
    env_id: Mapped[int] = mapped_column(
        ForeignKey("environments.id", ondelete="CASCADE"), nullable=False)
    # 'default' | 'username'(缺省 default:跟随系统默认账户)
    ref_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default="default",
        server_default=text("'default'"))
    ref_username: Mapped[str] = mapped_column(
        String(128), nullable=False, default="", server_default=text("''"))
    display: Mapped[str] = mapped_column(
        String(128), nullable=False, default="", server_default=text("''"))
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
