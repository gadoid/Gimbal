"""ServiceAlias model — 服务别名注册表(服务画像方案 §4.1/§5.3)。

别名是「配置的最小锚点」的显式登记:命名规则复用编排引擎既有的
``<服务名>-<后缀>`` 识别(``derive_base``,最后一个 ``-`` 切分、前缀
必须落在 Plate 目录内)—— 本表只是把隐式推导变成可管理的登记面,
不新起一套匹配规则。

* ``alias_name`` PK;``base_service`` 由 ``derive_base`` 派生,冗余存
  一份便于按服务聚合查询(目录改名会漂移,读侧以派生为准);
* ``slot`` = 别名声明的凭证槽位,按**执行者本人**的槽位绑定解析(owner
  隔离池,方案 §4.1 拍板)—— 同一别名行被不同人执行时各拿各的凭证;
* authz M2a S6 别名瘦身:``base_url`` / ``environment_id`` /
  ``owner_user_id`` / ``credential_alias`` 已删(0047)—— 地址 = 环境 →
  部署表(``deployments``),环境 = 执行时环境链,别名全部团队共享,
  槽位唯一口径 = ``slot``;
* ``carry_profile_ref``(取值集引用)按挂起清单 §5.6 不建列 —— 别名级
  carry 差异用 ``carry_bindings`` 别名键直接落(CarryServiceBinding 的
  service_name 本就是自由字符串,稀疏覆盖语义在 carry_injection 合并)。
"""
from __future__ import annotations

from datetime import datetime

from ._types import UtcDateTime
from sqlalchemy import Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class ServiceAlias(Base):
    __tablename__ = "service_aliases"
    __table_args__ = (
        # 服务信息管理页按服务聚合的查询面
        Index("ix_service_alias_base", "base_service"),
    )

    alias_name: Mapped[str] = mapped_column(String(128), primary_key=True)
    base_service: Mapped[str] = mapped_column(String(128))
    # authz M2a S3:别名声明槽位(可空 = 不声明;执行时按执行人本人的
    # 槽位绑定解析 —— S6 起唯一凭证口径)
    slot: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 三态接入(P1.0/缺口收口计划 §0 裁定 4):plate = 落在 plate 系统
    # services 声明内(受管,可版本化);external = 第三方服务,无版本
    # 管理 —— 不触发预览、不阻塞集成,单独统计不入基线。存量行随
    # 0019 server_default 回填 'plate'(登记强约束保证 base 在 plate
    # 目录内);审计/纠偏走 scripts/p1_backfill_service_kinds.py。
    kind: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="plate")
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now(), onupdate=func.now()
    )
