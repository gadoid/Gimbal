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
    # 平台身份事件告警受众 —— 与 ops.write 同口径(原 member+ 扇出)
    "platform.alerts": frozenset({"admin", "super_admin"}),
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


# ── 表 B(authz W3,方案 §2.3):对象 × 动词 —— 对象级规则唯一来源 ──
# 单元格 = 谓词名集合(命中其一即放行),谓词定义紧跟表后:
#   owner     主体是对象属主(user.id == obj.owner_id)
#   public    对象处于公共态 —— visibility=="public"(W9-2 起
#             report_definition 同口径:公共定义带维护者 owner)
#   ref       主体持有该对象的引用分享(§7.6;需查库,只进 async can)
#   steward   ops.write 能力(表 A)∧ 对象公共 —— Admin+ 的公共治理
#             (下架公共对象,R6:admin 对他人对象没有发布权,对私有
#             对象没有任何动词)
#   maintain  users.manage 能力 ∧ 对象公共 —— report_definition 的
#             下架面(W9-2 起编辑归维护者,Admin+ 仅可下架)
# 角色不在表 B 出现:角色差由表 A 表达;对象级判定对同谓词主体同权。
# W3 收窄后 admin 与普通用户在对象级唯一的差别就是 steward/maintain
# 两个「公共态 × 能力」谓词。表 B 变更必须同步 tests/authz_expected.yaml
# 的 table_b 段(人工审定快照,R7)。

TABLE_B: dict[str, dict[str, frozenset[str]]] = {
    "scenario": {
        "read":      frozenset({"owner", "public", "ref"}),
        "copy":      frozenset({"owner", "public", "ref"}),
        "run":       frozenset({"owner", "ref"}),
        "write":     frozenset({"owner"}),
        "delete":    frozenset({"owner"}),
        # 发布(私有→公共的可见性扩张)是属主动作;admin 对他人对象
        # 无发布权(R6)—— 已公共对象再「发布」本是空操作,不损失什么
        "publish":   frozenset({"owner"}),
        # 下架:Admin+ 仅对**已是公共**的对象(steward)
        "unpublish": frozenset({"owner", "steward"}),
    },
    "suite": {
        "read":      frozenset({"owner", "public", "ref"}),
        "run":       frozenset({"owner", "ref"}),
        "write":     frozenset({"owner"}),
        "delete":    frozenset({"owner"}),
        "publish":   frozenset({"owner"}),
        "unpublish": frozenset({"owner", "steward"}),
    },
    # 数据集/运行方案没有自己的可见性 —— 读随父场景(§7.4 引用闭包),
    # 写属主单判
    "data_set": {
        "read":      frozenset({"owner", "public", "ref"}),
        "write":     frozenset({"owner"}),
    },
    "run_scheme": {
        "read":      frozenset({"owner", "public", "ref"}),
        "write":     frozenset({"owner"}),
    },
    # authz W9-2:公共定义有维护者 —— 编辑(owner 单判)只有维护者;
    # delete(下架)再给 maintain(Admin+ 治理面,方案 §1.4)
    "report_definition": {
        "read":      frozenset({"owner", "public"}),
        "write":     frozenset({"owner"}),
        "delete":    frozenset({"owner", "maintain"}),
    },
}


def _pred_owner(user: Any, obj: Any) -> bool:
    return _user_matches(user, obj.owner_id)


def obj_is_public(obj_type: str, obj: Any) -> bool:
    """public 谓词:对象是否处于公共态(visibility 列;authz W9-2 起
    report_definition 同口径 —— 公共定义带维护者,不再以无主为公共)。"""
    return (getattr(obj, "visibility", None) or "private") == "public"


def can_pure(user: Any, obj_type: str, verb: str, obj: Any) -> bool:
    """表 B 求值(纯谓词版):owner/public/steward/maintain,不查库。

    ``ref`` 谓词恒为 False —— 需要引用闭包的判定用 async :func:`can`。
    未登记的 (对象, 动词) 是编码错误,即刻 KeyError(与 roles_with
    同口径,而非静默拒绝)。
    """
    preds = TABLE_B.get(obj_type, {}).get(verb)
    if preds is None:
        raise KeyError(f"table B 未登记: {obj_type}.{verb}")
    if "owner" in preds and _pred_owner(user, obj):
        return True
    if "public" in preds and obj_is_public(obj_type, obj):
        return True
    if "steward" in preds and obj_is_public(obj_type, obj) \
            and has_capability(user, "ops.write"):
        return True
    if "maintain" in preds and obj_is_public(obj_type, obj) \
            and has_capability(user, "users.manage"):
        return True
    return False


async def can(db, user: Any, obj_type: str, verb: str, obj: Any) -> bool:
    """表 B 求值(完整版,含 ref 谓词)—— 对象级判定唯一入口。

    obj 需带 ``owner_id``;suite 另带 ``id``、场景系对象另带
    ``scenario_id``(ref 谓词按对象类型解析,见 ``_pred_ref``)。
    """
    if can_pure(user, obj_type, verb, obj):
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
    """403 unless ``user`` is the row owner —— 表 B 各 write/delete
    动词的属主单判投影(authz W3:admin 越属主旁路已删,私有区一律
    归属主;发布/下架的 steward 动词不经此函数,走 ``can_pure``)。

    ``detail`` is passed through verbatim to the HTTPException so each
    router keeps its existing error contract.
    """
    if not _user_matches(user, owner_id):
        raise HTTPException(status_code=403, detail=detail)


def can_read_scenario(
    user: Any,
    *,
    owner_id: int,
    visibility: str = "private",
) -> bool:
    """读侧纯判(表 B scenario.read):public 所有登录用户可读;
    private 仅属主可见。admin 不再有旁路(W3);引用分支由
    ``can_read_scenario_row`` 承担。
    """
    if visibility == "public":
        return True
    return _user_matches(user, owner_id)


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
) -> bool:
    """执行判定(表 B scenario.run):属主 ∨ 引用(public 不开执行,
    公共资源执行仍需先 fork —— 不变量 7;W3 起 admin 同样无旁路)。
    owner_id=None(公共化无主)时仅历史引用可跑。"""
    if owner_id is not None and _user_matches(user, owner_id):
        return True
    return await has_scenario_ref(db, user.id, scenario_id)


async def can_read_scenario_row(db, user: Any, row: Any) -> bool:
    """读判定(对象级,含引用):行对象须有 scenario_id/owner_id/
    visibility。纯判(owner/public)先行,引用分支只在前者不通过
    时查库。"""
    if can_read_scenario(
        user, owner_id=row.owner_id or -1,
        visibility=row.visibility or "private"):
        return True
    return await has_scenario_ref(db, user.id, row.scenario_id)


# (W3 收编后 suite 读写判定统一走 can()/can_pure() 查表 B;曾有的
# can_read_suite/can_run_suite 便捷包装零消费者,authz W6 review 删除)
