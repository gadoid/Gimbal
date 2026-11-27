"""执行配置的执行链消费面(v2.10 §11.2 单选契约;执行配置分层②)。

管理面(CRUD)在 ``routers/exec_configs``;本模块是**派发/预览链的
解析入口**:把一行配置摊平成链条消费的值对象。

单选序(§11.2 规范性,所有容器一致):

* **Explicit > ProjectDefault > None** —— 显式选定本人的个人配置或
  **当前项目**的项目配置;其他归属/不存在/失效/无 use 权限一律拒绝,
  **不降级**(fail-closed)。``exec_config.use`` 与 ``read`` 是两个
  权限:个人配置 use = 实际执行主体本人;项目配置 use = 项目执行面
  (§6 ``project.execute`` —— 含 private 属主/normal 三种成员角色)。
* **个人默认不参与后端自动解析**(§11.2:仅交互预选;签核项「取消
  个人默认自动回退」)—— 未显式时按**项目默认**行解析;无项目默认
  行 → 无配置(全链回落零配置,显式传参才吃配置)。
* **单选对配置的全部字段生效**(§11.2 验收例):选定配置整体替换
  项目默认配置 —— 绑定/圈定/carry 覆盖都只来自选定行;项目 Carry
  资源层(公共 < 项目)与配置层正交,照常参与。

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
    """显式选定的执行配置不存在/不属本人/无 use 权限(调用方映射 404)。"""

    def __init__(self, config_id: int) -> None:
        super().__init__(f"exec config not found: {config_id}")
        self.config_id = config_id


@dataclass(frozen=True)
class ExecConfigChoice:
    """一次执行选定的执行配置(摊平形态;零凭证值零地址值)。

    ``explicit`` = 是否显式选定(§11.2 单选的闸:未显式 = 项目默认行
    兜底;绑定/圈定/carry 全部来自选定行)。
    ``circled`` = 圈定集(决策 1 圈定即承诺):生效行 systems[].aliases
    的并集,**非空 = 白名单生效**、空 = 未圈定(存量兼容,等同关闭)。
    """
    config_id: int
    name: str
    is_default: bool
    explicit: bool
    # 别名全名 → 条目名(换池内取用;注入标签不变)
    bindings: dict[str, str] = field(default_factory=dict)
    # 目录服务名 → {字段: 值|null=显式注入 null}
    carry_overrides: dict[str, dict[str, str | None]] = field(
        default_factory=dict)
    # 目录服务名 → (carry 键,…)(§11.4 remove 指针解码后的平键;被删
    # 键从生效 carry 对象消失,预览/物化同源,不再回填)
    carry_removals: dict[str, tuple[str, ...]] = field(
        default_factory=dict)
    # 圈定集(条目名并集;空 = 未圈定,执行闸跳过)
    circled: frozenset[str] = field(default_factory=frozenset)


EMPTY_CHOICE = ExecConfigChoice(
    config_id=0, name="", is_default=False, explicit=False)


def decode_carry_removal_pointer(pointer: str) -> str:
    """§11.4 remove 指针(相对服务对象)→ **最终请求体路径**:
    ``/headers/legacy`` → ``headers.legacy``;``~1``→``/``、``~0``→``~``;
    ``$.`` 前缀值表键写法兼容剥除(寻址统一按体路径);非法转义/空段/
    进入数组的段拒绝(ValueError —— 写面映射 422)。"""
    import re as _re

    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError(f"remove 指针须以 / 开头: {pointer!r}")
    parts: list[str] = []
    for tok in pointer[1:].split("/"):
        if "~" in tok and _re.search(r"~(?![01])", tok):
            raise ValueError(f"remove 指针转义非法: {pointer!r}")
        tok = tok.replace("~1", "/").replace("~0", "~")
        if tok.startswith("$."):      # 值表键写法兼容($.headers.legacy)
            tok = tok[2:]
        if not tok or tok.isdigit():
            raise ValueError(
                f"remove 指针含空段/数组下标段(进入数组拒绝): {pointer!r}")
        parts.append(tok)
    return ".".join(parts)


def _flatten(systems: Any) -> tuple[dict[str, str],
                                    dict[str, dict[str, str | None]],
                                    dict[str, tuple[str, ...]],
                                    frozenset[str]]:
    bindings: dict[str, str] = {}
    carries: dict[str, dict[str, str | None]] = {}
    removals: dict[str, tuple[str, ...]] = {}
    circled: set[str] = set()
    for s in systems or []:
        if not isinstance(s, dict):
            continue
        for k, v in (s.get("bindings") or {}).items():
            if isinstance(k, str) and isinstance(v, str) and v:
                bindings[k] = v
        carry = s.get("carryOverrides")
        if isinstance(carry, dict) and carry:
            carries[str(s.get("service") or "")] = dict(carry)
        rem = s.get("carryRemovals")
        if isinstance(rem, list) and rem:
            removals[str(s.get("service") or "")] = tuple(
                decode_carry_removal_pointer(p) for p in rem)
        for a in (s.get("aliases") or []):
            if isinstance(a, str) and a.strip():
                circled.add(a.strip())
    return bindings, carries, removals, frozenset(circled)


def choice_of_row(row: ExecConfig, *, explicit: bool) -> ExecConfigChoice:
    bindings, carries, removals, circled = _flatten(
        (row.payload or {}).get("systems"))
    return ExecConfigChoice(
        config_id=row.id, name=row.name, is_default=row.is_default,
        explicit=explicit, bindings=bindings, carry_overrides=carries,
        carry_removals=removals, circled=circled)


async def can_use_project_config(
    db: AsyncSession, user_id: int, project_id: int,
) -> bool:
    """项目配置的 ``exec_config.use`` 面(§11.2「区分 use 与 read」):
    项目执行能力 = active 容器 ∧ 可见 ∧(private 属主 ∨ normal 成员
    —— §6 三种成员角色均具 ``project.execute``)。公共项目无项目配置
    (§7 能力矩阵),恒 False。"""
    from ..models.project import Project, ProjectMember

    proj = await db.get(Project, project_id)
    if proj is None or proj.status != Project.STATUS_ACTIVE:
        return False
    if proj.kind == Project.KIND_PRIVATE:
        return proj.owner_id == user_id
    if proj.kind == Project.KIND_PUBLIC:
        return False
    role = (await db.execute(select(ProjectMember.role).where(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id))).scalar_one_or_none()
    return role is not None


async def load_choice(
    db: AsyncSession, user_id: int, project_id: int | None,
    config_id: int | None,
) -> ExecConfigChoice | None:
    """§11.2 单选解析(执行与预览同源):显式 → 本人个人行或当前项目
    行(归属错误/不存在/无 use 权限 → :class:`ExecConfigNotFound`,
    调用方 404,不降级);未显式 → 项目默认行(explicit=False);
    无项目默认行 / 无项目语境 → None(零配置,显式传参才吃)。"""
    if config_id is not None:
        row = await db.get(ExecConfig, config_id)
        if row is None:
            raise ExecConfigNotFound(config_id)
        if row.principal_id is not None:
            # 个人配置:仅实际执行主体本人可显式选择(§11.2)
            if row.principal_id != user_id:
                raise ExecConfigNotFound(config_id)
        else:
            # 项目配置:仅当前项目可用 + 项目执行面(use 权限独立于 read)
            if (project_id is None or row.project_id != project_id
                    or not await can_use_project_config(
                        db, user_id, row.project_id)):
                raise ExecConfigNotFound(config_id)
        return choice_of_row(row, explicit=True)
    if project_id is None:
        return None
    row = (await db.execute(
        select(ExecConfig).where(
            ExecConfig.project_id == project_id,
            ExecConfig.is_default.is_(True)))).scalar()
    return choice_of_row(row, explicit=False) if row is not None else None


def carry_overrides_for(
    choice: ExecConfigChoice | None,
) -> dict[str, dict[str, str | None]] | None:
    """选定配置的 carry 覆盖 —— 「选定执行配置层」的链位输入(§11.4:
    公共 < 项目 Carry 资源 < 选定执行配置覆盖)。单选语义下选定行即
    全部配置层;执行与预览共用本裁决,口径不得漂移。"""
    if choice is None or not choice.carry_overrides:
        return None
    return choice.carry_overrides


def carry_removals_for(
    choice: ExecConfigChoice | None,
) -> dict[str, tuple[str, ...]] | None:
    """选定配置的 carry 删除(§11.4 remove;与 carry_overrides_for 同
    单选语义 —— 预览与物化同一 merged,被删键不回填)。"""
    if choice is None or not choice.carry_removals:
        return None
    return choice.carry_removals


async def project_default_carry_overrides(
    db: AsyncSession, project_id: int | None,
) -> dict[str, dict[str, str | None]] | None:
    """容器默认执行配置的 carry 覆盖(**分析面专用** —— 晋升冲突对照
    等非执行链读者;执行链的单选已含该行,不经过本函数)。确定性取
    默认行(容器管理员/属主维护;无默认行 = 无本层)。"""
    if project_id is None:
        return None
    row = (await db.execute(
        select(ExecConfig).where(
            ExecConfig.project_id == project_id,
            ExecConfig.is_default.is_(True)))).scalar()
    return choice_of_row(row, explicit=False).carry_overrides \
        if row is not None else None
