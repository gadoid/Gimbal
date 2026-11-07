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


# ── 表 B(authz W3 起,M2a S1.1 扩项目维度):对象 × 动词 ──────────────
# 单元格 = 谓词名集合(命中其一即放行)。谓词按**区**取效(S1 三区:
# project_id 空 = 私有区 / 普通项目 / 公共项目),同格内各区谓词互斥:
#   owner     私有区属主(user.id == obj.owner_id ∧ project_id IS NULL
#             —— D1:project_id 非空时属主身份不给任何权限)
#   ref       主体持有该对象的引用分享(§7.6;需查库,只进 async can;
#             仅私有区对象,S7 退役)
#   member    对象所属普通项目的成员(任意角色;公共项目不落成员行)
#   padmin    对象所属普通项目的项目管理员
#   maintainer 公共项目对象的 owner_id(S1-b 例外:公共项目写权跟
#             维护者走 —— owner_id 在公共项目的语义 = 维护者)
#   public_reader 对象在公共项目(全员可读)
#   public_admin  对象在公共项目 ∧ ops.write(Admin+ 的公共治理,
#             取代 W3 的 steward:下架公共对象,R6 不变)
# 数据集/运行方案行上没有 project_id —— 读随父场景(§7.4 引用闭包,
# 实际判定走 can_read_scenario_row / 父场景 can()),写属主单判。
# 角色不在表 B 出现:角色差由表 A 表达。表 B 变更必须同步
# tests/authz_expected.yaml 的 table_b 段(人工审定快照,R7)。
# publish 的 maintainer:影子期已公共对象再「发布」是空操作,放行
# 维护者避免无谓 403;S1.3 起该格语义 = 重新发布(维护者更新公共副本)。

TABLE_B: dict[str, dict[str, frozenset[str]]] = {
    "scenario": {
        "read":      frozenset({"owner", "ref", "member", "public_reader"}),
        "copy":      frozenset({"owner", "ref", "member", "public_reader"}),
        "run":       frozenset({"owner", "ref", "member"}),  # 公共不可执行
        "write":     frozenset({"owner", "member", "maintainer"}),
        "delete":    frozenset({"owner", "member", "maintainer",
                                "public_admin"}),
        "publish":   frozenset({"owner", "padmin", "maintainer"}),
        # 下架 = 对公共副本(维护者撤下 / Admin+ 治理);私有区无下架
        "unpublish": frozenset({"maintainer", "public_admin"}),
    },
    "suite": {
        "read":      frozenset({"owner", "ref", "member", "public_reader"}),
        "run":       frozenset({"owner", "ref", "member"}),
        "write":     frozenset({"owner", "member", "maintainer"}),
        "delete":    frozenset({"owner", "member", "maintainer",
                                "public_admin"}),
        "publish":   frozenset({"owner", "padmin", "maintainer"}),
        "unpublish": frozenset({"maintainer", "public_admin"}),
    },
    # 数据集/运行方案:读/执行随父场景(§7.4 引用闭包,can_read_
    # scenario_row 承担,这里的 member/public_reader 只是口径登记),
    # 写属主单判
    "data_set": {
        "read":      frozenset({"owner", "ref", "member", "public_reader"}),
        "write":     frozenset({"owner"}),
    },
    "run_scheme": {
        "read":      frozenset({"owner", "ref", "member", "public_reader"}),
        "write":     frozenset({"owner"}),
    },
    # W9-2 语义换轴:编辑 = 私有区属主 ∨ 公共项目维护者;下架(delete)
    # = 维护者 ∨ Admin+(public_admin)
    "report_definition": {
        "read":      frozenset({"owner", "public_reader"}),
        "write":     frozenset({"owner", "maintainer"}),
        "delete":    frozenset({"owner", "maintainer", "public_admin"}),
    },
}


def _pred_owner(user: Any, obj: Any) -> bool:
    """owner 谓词(D1):私有区属主 —— project_id 非空时属主身份不
    给任何权限(公共项目的维护者例外走 maintainer 谓词,S1-b)。"""
    if getattr(obj, "project_id", None) is not None:
        return False
    return _user_matches(user, obj.owner_id)


def can_pure(
    user: Any, obj_type: str, verb: str, obj: Any, *,
    public_project_id: int | None = None,
    project_roles: dict[int, str] | None = None,
) -> bool:
    """表 B 求值(可注入上下文的纯函数版)。

    ``public_project_id`` / ``project_roles``(主体在普通项目的角色表)
    由调用方注入:不传则 public_reader/maintainer/public_admin/member/
    padmin 谓词按「无上下文」恒 False(影子期这些对象只经 :func:`can`
    判定)。``ref`` 谓词恒 False —— 需要引用闭包的判定用 async
    :func:`can`。未登记的 (对象, 动词) 是编码错误,即刻 KeyError
    (与 roles_with 同口径,而非静默拒绝)。
    """
    preds = TABLE_B.get(obj_type, {}).get(verb)
    if preds is None:
        raise KeyError(f"table B 未登记: {obj_type}.{verb}")
    if "owner" in preds and _pred_owner(user, obj):
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
            if "padmin" in preds and role_here == "admin":
                return True
    return False


async def can(db, user: Any, obj_type: str, verb: str, obj: Any) -> bool:
    """表 B 求值(完整版,含 ref 与项目谓词)—— 对象级判定唯一入口。

    obj 需带 ``owner_id`` 与 ``project_id``;suite 另带 ``id``、场景系
    对象另带 ``scenario_id``(ref 谓词按对象类型解析,见 ``_pred_ref``)。
    公共项目 id 与主体项目角色一次查询、会话内缓存(services.zone)。
    """
    from ..services.zone import my_project_roles, public_project_id

    if can_pure(user, obj_type, verb, obj,
                public_project_id=await public_project_id(db),
                project_roles=await my_project_roles(db, user.id)):
        return True
    preds = TABLE_B[obj_type][verb]
    if "ref" in preds and await _pred_ref(db, obj_type, obj, user.id):
        return True
    return False


async def _pred_ref(db, obj_type: str, obj: Any, user_id: int) -> bool:
    """ref 谓词:suite 按套件引用,场景系按场景引用(直接 ∨ 经 suite)。"""
    if obj_type == "suite":
        return await has_suite_ref(db, user_id, obj.id)
    scen_id = getattr(obj, "scenario_id", None)
    return scen_id is not None and await has_scenario_ref(db, user_id, scen_id)


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


# ── 引用分享(权限域二期 P2,§7.6)────────────────────────────────
# 判定单点收敛:ref 谓词只在本模块;各 router/查询一律引用此处,
# 禁止自写 EXISTS(§7.6「单点收敛」)。

def ref_exists_clauses(viewer_id: int):
    """PG 谓词用的两条 EXISTS(scenario_query.visibility_clause 引用;
    深度固定不递归:直接引用 ∨ 所在 suite 被引用)。"""
    from sqlalchemy import exists, select

    from ..models.share_ref import ShareRef
    from ..models.suite import SuiteMember

    direct = exists(select(ShareRef.id).where(
        ShareRef.scenario_id == ComposerScenario.scenario_id,
        ShareRef.grantee_user_id == viewer_id)).correlate(ComposerScenario)
    via_suite = exists(
        select(ShareRef.id)
        .join(SuiteMember, SuiteMember.suite_id == ShareRef.suite_id)
        .where(SuiteMember.scenario_id == ComposerScenario.scenario_id,
               ShareRef.grantee_user_id == viewer_id)
    ).correlate(ComposerScenario)
    return direct, via_suite


async def referenced_scenario_ids(db, user_id: int) -> set[str]:
    """SQLite 兜底/徽标用:user 的引用场景全集(直接 ∨ 经 suite),
    一次取集合(团队规模有界,§2.3)。"""
    from sqlalchemy import select

    from ..models.share_ref import ShareRef
    from ..models.suite import SuiteMember

    direct = (await db.execute(
        select(ShareRef.scenario_id).where(
            ShareRef.grantee_user_id == user_id,
            ShareRef.scenario_id.is_not(None)))).scalars().all()
    via = (await db.execute(
        select(SuiteMember.scenario_id)
        .join(ShareRef, ShareRef.suite_id == SuiteMember.suite_id)
        .where(ShareRef.grantee_user_id == user_id))).scalars().all()
    return set(direct) | set(via)


async def has_scenario_ref(db, user_id: int, scenario_id: str) -> bool:
    """can_run_scenario 的引用分支(§7.6):直接引用 ∨ 所在 suite 被引用。"""
    return scenario_id in await referenced_scenario_ids(db, user_id)


async def has_suite_ref(db, user_id: int, suite_id: int) -> bool:
    from sqlalchemy import select

    from ..models.share_ref import ShareRef

    return (await db.execute(
        select(ShareRef.id).where(
            ShareRef.grantee_user_id == user_id,
            ShareRef.suite_id == suite_id))).scalar_one_or_none() is not None


async def can_run_scenario(
    db, user: Any, *, scenario_id: str, owner_id: int | None,
    project_id: int | None = None,
) -> bool:
    """执行判定(表 B scenario.run = owner ∨ ref ∨ member):私有区
    属主 ∨ 引用;普通项目成员可跑;公共项目不开执行(公共资源跑需
    先 fork,不变量 7;W3 起 admin 同样无旁路)。owner 谓词带区守卫
    (D1:project_id 非空时属主身份不给权限);owner_id=None(孤儿)
    时仅引用 / 项目分支可过。"""
    if project_id is None:
        if owner_id is not None and _user_matches(user, owner_id):
            return True
        return await has_scenario_ref(db, user.id, scenario_id)
    from ..services.zone import my_project_roles
    return project_id in await my_project_roles(db, user.id)


async def can_read_scenario_row(db, user: Any, row: Any) -> bool:
    """读判定(对象级,含引用与项目谓词):行对象须有 scenario_id/
    owner_id/project_id。S1.1 起统一走 :func:`can`(表 B scenario.read
    = owner ∨ ref ∨ member ∨ public_reader),不再各写一支。"""
    return await can(db, user, "scenario", "read", row)


# (W3 收编后 suite 读写判定统一走 can()/can_pure() 查表 B;曾有的
# can_read_suite/can_run_suite 便捷包装零消费者,authz W6 review 删除)
