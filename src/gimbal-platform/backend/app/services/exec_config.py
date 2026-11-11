"""执行配置的执行链消费面(执行配置分层②,设计方案 §4/§5)。

管理面(CRUD)在 ``routers/exec_configs``;本模块是**派发/预览链的
解析入口**:把一行配置摊平成链条消费的值对象。

三条链的吃法(§5 全文):

* **环境**:选定配置的 envId 占位②(遮蔽方案存量);默认配置的 envId
  占位④(遮蔽旧偏好 ``run.environment``;无默认配置 → 回落旧偏好,
  §7 存量兼容)。仅当配置**设了** envId 才占位 —— 空值不遮蔽。
* **绑定**:仅**显式选定**的配置参与(「选定执行配置 > 方案遗留 >
  场景 authored > 池默认行」)—— 默认配置的绑定不自动生效,防成员
  默认配置静默改写槽位。语义 = 换池内取用行,**注入标签(场景引用的
  声明槽位)不变**(§5 注入表「改变池内命中哪条」)。
* **carry**:私有区 = 选定或默认配置的覆盖;项目区 = 仅显式选定
  (决策 9「默认不吃、显式吃」)。覆盖键 = 目录服务名(base)。

入口排除(§5 守则):令牌/编排(graph)/临时调用不吃执行配置 ——
同指纹不变量与单元自治,在调用方(dispatch_run)闸。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.exec_config import ExecConfig


class ExecConfigNotFound(LookupError):
    """显式选定的执行配置不存在/不属本人(调用方映射 404)。"""

    def __init__(self, config_id: int) -> None:
        super().__init__(f"exec config not found: {config_id}")
        self.config_id = config_id


@dataclass(frozen=True)
class ExecConfigChoice:
    """一次执行选定的执行配置(摊平形态;零凭证值零地址值)。

    ``explicit`` = 是否显式选定(决策 9 与绑定链的闸:默认行 explicit
    =False,携带 env/carry 但不携带绑定语义)。"""
    config_id: int
    name: str
    is_default: bool
    explicit: bool
    env_id: int | None = None
    # 别名全名 → 槽位名(换池内取用;注入标签不变)
    bindings: dict[str, str] = field(default_factory=dict)
    # 目录服务名 → {字段: 值|null=显式注入 null}
    carry_overrides: dict[str, dict[str, str | None]] = field(
        default_factory=dict)


EMPTY_CHOICE = ExecConfigChoice(
    config_id=0, name="", is_default=False, explicit=False)


def _flatten(systems: Any) -> tuple[dict[str, str],
                                    dict[str, dict[str, str | None]]]:
    bindings: dict[str, str] = {}
    carries: dict[str, dict[str, str | None]] = {}
    for s in systems or []:
        if not isinstance(s, dict):
            continue
        for k, v in (s.get("bindings") or {}).items():
            if isinstance(k, str) and isinstance(v, str) and v:
                bindings[k] = v
        carry = s.get("carryOverrides")
        if isinstance(carry, dict) and carry:
            carries[str(s.get("service") or "")] = dict(carry)
    return bindings, carries


def choice_of_row(row: ExecConfig, *, explicit: bool) -> ExecConfigChoice:
    bindings, carries = _flatten((row.payload or {}).get("systems"))
    return ExecConfigChoice(
        config_id=row.id, name=row.name, is_default=row.is_default,
        explicit=explicit, env_id=row.environment_id,
        bindings=bindings, carry_overrides=carries)


async def load_choice(
    db: AsyncSession, user_id: int, config_id: int | None,
) -> ExecConfigChoice | None:
    """显式 id → 该行(须 ``('user', user_id)``,否则 NotFound);
    None → 默认行;无默认行 → None(全链回落旧链,零行为变化)。"""
    if config_id is not None:
        row = await db.get(ExecConfig, config_id)
        if row is None or row.scope != "user" or row.scope_id != user_id:
            raise ExecConfigNotFound(config_id)
        return choice_of_row(row, explicit=True)
    row = (await db.execute(
        select(ExecConfig).where(
            ExecConfig.scope == "user", ExecConfig.scope_id == user_id,
            ExecConfig.is_default.is_(True)))).scalar()
    return choice_of_row(row, explicit=False) if row is not None else None


def carry_overrides_for(
    choice: ExecConfigChoice | None, project_id: int | None,
) -> dict[str, dict[str, str | None]] | None:
    """carry 覆盖的区规则(决策 9「默认不吃、显式吃」):私有区 = 选定
    或默认配置都吃;项目区 = 仅显式选定的配置携带覆盖。执行与预览
    共用本裁决,口径不得漂移。"""
    if choice is None or not choice.carry_overrides:
        return None
    if project_id is None or choice.explicit:
        return choice.carry_overrides
    return None


async def project_carry_overrides(
    db: AsyncSession, project_id: int | None,
) -> dict[str, dict[str, str | None]] | None:
    """⑧ 项目 scope 默认配置的 carry 覆盖 —— 项目区链位(§5):场景
    显式 > 显式选定个人覆盖 > **项目默认配置覆盖** > 项目层 > 公共
    项目层。确定性取默认行(项目管理员维护;无默认行 = 无本层)。"""
    if project_id is None:
        return None
    row = (await db.execute(
        select(ExecConfig).where(
            ExecConfig.scope == "project", ExecConfig.scope_id == project_id,
            ExecConfig.is_default.is_(True)))).scalar()
    return choice_of_row(row, explicit=False).carry_overrides \
        if row is not None else None


def merge_carry_overrides(
    lower: dict[str, dict[str, str | None]] | None,
    upper: dict[str, dict[str, str | None]] | None,
) -> dict[str, dict[str, str | None]] | None:
    """两层覆盖的字段级合并(upper 压 lower;⑧ 项目区链:显式个人配置
    压项目默认配置)。执行与预览共用。"""
    if not lower:
        return upper or None
    if not upper:
        return lower
    out = {svc: dict(fields) for svc, fields in lower.items()}
    for svc, fields in upper.items():
        out.setdefault(svc, {}).update(fields)
    return out
