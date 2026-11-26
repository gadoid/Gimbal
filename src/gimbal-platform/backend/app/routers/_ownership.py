"""Shared composer ownership check.

One canonical rule for the V3 composer routers (scenarios, data-sets,
runs):

* row ownership = ``owner_id`` (int user id) — the single authority
* rules come from Table A (capability × role) and Table B (object ×
  verb) below; no role literals at the call sites
  (authz W3 私有区收窄:admin 对他人私有对象不再有旁路)

Each call-site keeps its own 403 ``detail`` payload (string or dict) so
API responses stay byte-identical.
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from ..models.composer_scenario import ComposerScenario
from ..models.project import ProjectMember


# ── 表 A(authz W2,方案 §2.3):能力 × 角色 —— 唯一规则来源 ──────────
# 角色权威取值 user | admin | super_admin(W1 更名后)。三处消费:
#   * ``core.deps.require_capability``(能力门,错误 capability_forbidden)
#   * ``roles_with(cap)``(SQL 人群选择:告警扇出/通知)
#   * ``/auth/me`` 的 capabilities 下发(``capabilities_of``)
# v1 收编三个门面;W3-W9 随表 B 各模块把行内比较逐批收编进来,
# 能力集只增不改既有语义(收编一处、grep 守卫白名单缩一行)。
# 表 A 变更必须同步 tests/authz_expected.yaml(人工审定快照,R7)。

CAPABILITIES: dict[str, frozenset[str]] = {
    # 用户管理(开号/角色/停用/删除/重置密码)—— 原 admin 级专属
    "users.manage": frozenset({"super_admin"}),
    # 技术运营(适配/别名 CRUD/环境/公告面)—— 原 member+ 级(W5 起
    # 令牌签发、W7 起导入已开放至全体用户,不再由此能力覆盖)
    "ops.write": frozenset({"admin", "super_admin"}),
    # 别名注册表新建条目(导入 decision=create 建名)—— 方案 §2.1
    # 「Admin 维护服务别名注册表」;authz W7:导入门放开给 User 后,
    # 建名仍是 Admin 面(User 只能 reuse/map 到已有别名)
    "alias.write": frozenset({"admin", "super_admin"}),
}

# 权威顺序(低 → 高);roles_with 按此序输出,SQL in_ 与展示都稳定。
ROLES: tuple[str, ...] = ("user", "admin", "super_admin")


def capabilities_of(role: str) -> list[str]:
    """角色 → 能力列表(按 CAPABILITIES 定义序;/auth/me 下发口径)。"""
    return [cap for cap, allowed in CAPABILITIES.items() if role in allowed]


def roles_with(cap: str) -> tuple[str, ...]:
    """能力 → 角色元组(SQL ``in_`` 人群选择)。

    09-29 与 W1 两轮角色更名都发生过「扇出 in_ 写死旧角色、漏发新
    级别」的同款事故;人群选择改由表 A 驱动,更名只动表。
    (W1 的四个扇出点与首注册/末位保护已收编为表驱动。)
    """
    allowed = CAPABILITIES.get(cap)
    if allowed is None:
        raise KeyError(f"unknown capability: {cap!r}(表 A 未登记)")
    return tuple(r for r in ROLES if r in allowed)


def has_capability(user: Any, cap: str) -> bool:
    """JWT 主体的能力判定(表 A 驱动)。行内角色比较应收编到这里或
    ``can()``/``can_pure()``,不再写角色字面量(grep 守卫)。"""
    role = getattr(user, "role", None)
    return role in CAPABILITIES.get(cap, ())


# ── 表 B(authz W3 起,M2a S1.1 扩项目维度;UPC M2 收口)──────────────
# 单元格 = 谓词名集合(命中其一即放行)。谓词按**项目关系**取效
# (UPC M2:对象 project_id NOT NULL,归属权威 = 真实容器):
#   owner     对象所属项目是**主体拥有的私有空间**(全部私有空间,
#             非仅默认;owner_id 列降为审计/维护者快照,不参与判定)
#   member    对象所属普通项目的成员(任意角色,含只读 + 执行的项目
#             用户;公共项目不落成员行)—— 读 / 复制 / 执行
#   contributor 对象所属普通项目的可写角色(项目管理员 ∨ 项目成员;
#             M2b Q1:项目用户只读 + 执行,不命中)—— 写 / 删
#   padmin    对象所属普通项目的项目管理员
#   maintainer 公共项目对象的 owner_id(公共项目写权跟维护者走)
#   public_reader 对象在公共项目(全员可读)
#   public_admin  对象在公共项目 ∧ ops.write(Admin+ 的公共治理,
#             取代 W3 的 steward:下架公共对象,R6 不变)
# 数据集行上没有 project_id:读随父场景(§7.4 引用闭包,实际判定走
# can_read_scenario_row / 父场景 can());运行方案行 M2 起携带从父场景
# 派生的 project_id,判定与父场景动词同形。
# 角色不在表 B 出现:角色差由表 A 表达。表 B 变更必须同步
# tests/authz_expected.yaml 的 table_b 段(人工审定快照,R7)。
# publish 的 maintainer:重新发布 = 维护者更新公共副本,放行避免
# 无谓 403。

# contributor 谓词的角色集(M2b Q1;成员角色字面量只在模型常量)
_CONTRIBUTOR_ROLES = ProjectMember.WRITER_ROLES

TABLE_B: dict[str, dict[str, frozenset[str]]] = {
    "scenario": {
        "read":      frozenset({"owner", "member", "public_reader"}),
        "copy":      frozenset({"owner", "member", "public_reader"}),
        "run":       frozenset({"owner", "member"}),  # 公共不可执行
        "write":     frozenset({"owner", "contributor", "maintainer"}),
        "delete":    frozenset({"owner", "contributor", "maintainer",
                                "public_admin"}),
        "publish":   frozenset({"owner", "padmin", "maintainer"}),
        # 下架 = 对公共副本(维护者撤下 / Admin+ 治理);私有区无下架
        "unpublish": frozenset({"maintainer", "public_admin"}),
        # S1-e 转移维护者:仅公共项目对象(私有区不适用)
        "transfer":  frozenset({"maintainer", "public_admin"}),
    },
    "suite": {
        "read":      frozenset({"owner", "member", "public_reader"}),
        "run":       frozenset({"owner", "member"}),
        "write":     frozenset({"owner", "contributor", "maintainer"}),
        "delete":    frozenset({"owner", "contributor", "maintainer",
                                "public_admin"}),
        "publish":   frozenset({"owner", "padmin", "maintainer"}),
        "unpublish": frozenset({"maintainer", "public_admin"}),
        "transfer":  frozenset({"maintainer", "public_admin"}),
    },
    # 数据集/运行方案行上没有 project_id:读写都随父场景(§7.4 引用
    # 闭包 —— 实际判定 = 父场景 can(read/write);S1.2 写闸已切换,
    # 这里的登记与父场景动词同形,矩阵只测 write)
    "data_set": {
        "read":      frozenset({"owner", "member", "public_reader"}),
        "write":     frozenset({"owner", "contributor", "maintainer"}),
    },
    "run_scheme": {
        "read":      frozenset({"owner", "member", "public_reader"}),
        "write":     frozenset({"owner", "contributor", "maintainer"}),
    },
    # W9-2 语义换轴:编辑 = 私有区属主 ∨ 公共项目维护者;下架(delete)
    # = 维护者 ∨ Admin+(public_admin)
    "report_definition": {
        "read":      frozenset({"owner", "public_reader"}),
        "write":     frozenset({"owner", "maintainer"}),
        "delete":    frozenset({"owner", "maintainer", "public_admin"}),
        "transfer":  frozenset({"maintainer", "public_admin"}),
    },
    # S1.6 起登记(S1.7 全面收编读写面):转移维护者 = mnt ∨ pa,
    # 仅公共项目模板(私有模板无维护者语义,走删用户处置的转让)
    "integration_template": {
        "transfer":  frozenset({"maintainer", "public_admin"}),
    },
}


def _pred_owner(user: Any, obj: Any,
                private_project_ids: "frozenset[int] | None") -> bool:
    """owner 谓词(UPC M2):对象所属项目是主体拥有的私有空间 ——
    涵盖其全部私有空间(默认 + 额外);owner_id 列不再参与判定。"""
    pid = getattr(obj, "project_id", None)
    if pid is None or private_project_ids is None:
        return False
    return pid in private_project_ids


def can_pure(
    user: Any, obj_type: str, verb: str, obj: Any, *,
    public_project_id: int | None = None,
    project_roles: dict[int, str] | None = None,
    private_project_ids: "frozenset[int] | None" = None,
) -> bool:
    """表 B 求值(可注入上下文的纯函数版)。

    ``public_project_id`` / ``project_roles`` / ``private_project_ids``
    (主体拥有的私有空间集合,UPC M2 起 owner 谓词的数据源)由调用方
    注入:不传则 public_reader/maintainer/public_admin/member/padmin/
    owner 谓词按「无上下文」恒 False。未登记的 (对象, 动词) 是编码
    错误,即刻 KeyError(与 roles_with 同口径,而非静默拒绝)。
    """
    preds = TABLE_B.get(obj_type, {}).get(verb)
    if preds is None:
        raise KeyError(f"table B 未登记: {obj_type}.{verb}")
    if "owner" in preds and _pred_owner(user, obj, private_project_ids):
        return True
    pid = getattr(obj, "project_id", None)
    in_public = (public_project_id is not None and pid == public_project_id)
    if in_public:
        if "public_reader" in preds:
            return True
        if "maintainer" in preds and _user_matches(user, obj.owner_id):
            return True
        if "public_admin" in preds and has_capability(user, "ops.write"):
            return True
    elif pid is not None and project_roles:
        role_here = project_roles.get(pid)
        if role_here is not None:
            if "member" in preds:
                return True
            if "contributor" in preds and role_here in _CONTRIBUTOR_ROLES:
                return True
            if "padmin" in preds and role_here == "admin":
                return True
    return False


async def can(db, user: Any, obj_type: str, verb: str, obj: Any) -> bool:
    """表 B 求值(完整版)—— 对象级判定唯一入口。

    obj 需带 ``project_id``(UPC M2:归属权威;``owner_id`` 仅公共项目
    maintainer 谓词消费)。公共项目 id、主体项目角色与私有空间集合各
    一次查询、会话内缓存(services.zone)。S7.4:ref 谓词已随引用分享
    退役,can 与 can_pure 全集等价 —— 签名保留 async 供既有调用方。
    """
    from ..services.zone import (my_private_projects, my_project_roles,
                                  public_project_id)

    ok = can_pure(user, obj_type, verb, obj,
                  public_project_id=await public_project_id(db),
                  project_roles=await my_project_roles(db, user.id),
                  private_project_ids=await my_private_projects(
                      db, user.id))
    if not ok:
        return False
    # §13.1(评审二轮 P1-5):归档起禁止**新写入**与新执行 —— 收敛到表 B
    # 求值单源,不再只依赖创建闸与权限投影(修前归档项目成员 PUT 仍 200)
    if verb in ("write", "run"):
        pid = getattr(obj, "project_id", None)
        if pid is not None:
            from ..models.project import Project

            proj = await db.get(Project, pid)
            if proj is not None and proj.status != Project.STATUS_ACTIVE:
                return False
    return True


def _user_matches(user: Any, owner_id: int) -> bool:
    """Canonical identity match for the composer tables."""
    return user.id == owner_id


def ensure_owner(user: Any, owner_id: int, detail: Any) -> None:
    """403 unless ``user`` is the row owner —— 表 B 私有区各 write/
    delete 动词的属主单判投影(authz W3:admin 越属主旁路已删;对象
    在项目/公共项目时属主身份不给权限 D1,项目动词不经此函数,走
    ``can()``)。

    ``detail`` is passed through verbatim to the HTTPException so each
    router keeps its existing error contract.
    """
    if not _user_matches(user, owner_id):
        raise HTTPException(status_code=403, detail=detail)




async def can_run_scenario(
    db, user: Any, *, scenario_id: str, owner_id: int | None,
    project_id: int,
) -> bool:
    """执行判定(表 B scenario.run = owner ∨ member;UPC M2:project_id
    恒非空,判定 = 项目关系):私有空间仅所有者;普通项目成员可跑;
    公共项目不开执行(公共资源跑需先复制,不变量 7;Admin+ 同样无
    旁路)。owner_id 列不再参与(降为审计)。"""
    from ..services.zone import my_private_projects, my_project_roles

    # §13.1(评审二轮 P1-5):归档起禁止新执行 —— 执行授权单源同闸
    from ..models.project import Project

    proj = await db.get(Project, project_id)
    if proj is None or proj.status != Project.STATUS_ACTIVE:
        return False
    if project_id in await my_private_projects(db, user.id):
        return True
    return project_id in await my_project_roles(db, user.id)


async def can_read_scenario_row(db, user: Any, row: Any) -> bool:
    """读判定(对象级,含项目谓词):行对象须有 scenario_id/project_id。
    统一走 :func:`can`(表 B scenario.read = owner ∨ member ∨
    public_reader),不再各写一支。"""
    return await can(db, user, "scenario", "read", row)


# (W3 收编后 suite 读写判定统一走 can()/can_pure() 查表 B;曾有的
# can_read_suite/can_run_suite 便捷包装零消费者,authz W6 review 删除)
