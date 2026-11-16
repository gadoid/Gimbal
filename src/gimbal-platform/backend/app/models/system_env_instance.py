"""SystemEnvInstance model — 环境×系统部署实例(重构 §1.2)。

一个 (system, env) 唯一实例:部署事实(登录口/版本线/说明)的落库锚,
也是环境配置页的配置面单元。**实例唯一 + 配置 overlay**(决策 4):
差异化走多身份条目与配置值分层,不并排多实例;部署真有多套 → 拆环境。

* ``login_url`` = 登录口(上提自原凭证行 url;拨测 = login_url +
  账户 secret;缺席 = 配置缺失,预检明确报,不回退业务地址);
* ``line`` = 版本线(迁自 environments.lines JSON —— 版本线收口到
  实例:环境比对告警/保存推荐/退役判定改读本表)。

API 地址**不在本表**:仍按服务粒度在 deployments((base_service,
env) → base_url),系统层只做聚合呈现。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import UtcDateTime


class SystemEnvInstance(Base):
    __tablename__ = "system_env_instances"
    __table_args__ = (
        # 实例唯一(决策 4):(system, env) 恰一行
        UniqueConstraint("system", "env_id", name="uq_instance_system_env"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # 系统名(plate system 口径;与 auth_accounts.system 同键域)
    system: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    env_id: Mapped[int] = mapped_column(
        ForeignKey("environments.id", ondelete="CASCADE"),
        nullable=False, index=True)
    login_url: Mapped[str] = mapped_column(
        String(512), nullable=False, default="", server_default=text("''"))
    # 版本线(迁自 environments.lines;空 = 未声明)
    line: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", server_default=text("''"))
    note: Mapped[str] = mapped_column(
        String(256), nullable=False, default="", server_default=text("''"))
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
