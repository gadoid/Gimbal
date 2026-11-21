"""调用身份草稿(保存期通道;架构一致性轮 2026-11-21 收窄)。

场景保存链的**同事务**身份创建:``ScenarioDraft.authDrafts`` →
``ServiceIdentity(username-ref)``。**不再创建账户** —— 凭证是独立
资产,由 ``POST /auths``(本人池)/ 项目凭证端点(项目池)即时写入;
本通道只解决「非 Admin 作者需要在保存场景时登记一条 username-ref
条目」这一个权限例外。

``baseService`` 是服务实例的服务锚(不再是 ``system``):同系统多
服务时由用户选中的实例决定,不再取字典序第一个服务。账户校验覆盖
**本人池 + 场景项目池**,env 只作执行偏好、不作账户门槛(§8.3:
登录口按账户 env,身份 env 是执行标签)。

不 commit —— 事务边界在调用方(``create_in_transaction`` /
``update`` 的单事务里,场景保存失败整单回滚)。冲突码(调用方映射):

* ``auth_draft_env_not_found`` / ``auth_draft_service_unknown`` → 422;
* ``auth_draft_account_not_found``(账号不在本人池/项目池)→ 422;
* ``auth_draft_alias_taken`` → 409(行为规则①:直接引用,不覆盖);
* ``auth_draft_name_duplicated``(同一请求内重名)→ 422。
"""
from __future__ import annotations

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Environment, Service
from ..models.auth_account import AuthAccount
from ..models.service_identity import ServiceIdentity
from ..schemas.scenario_composer import AuthDraftIn


def _err(code: str, message: str) -> ValueError:
    """``ValueError("code: message")`` —— 调用方 value_error_http 映射。"""
    return ValueError(f"{code}: {message}")


async def base_overrides(
    db: AsyncSession, drafts: list[AuthDraftIn],
) -> dict[str, str]:
    """草稿名 → 条目的 ``base_service``(声明侧同 base 闸的 extra_bases 叠层)。

    闸在 materialize 之前跑、草稿名此刻未入库 —— ``same_base_
    violations`` 的「未登记跳过」会放走全部草稿引用。本映射把草稿
    base 显式带给闸,首存即裁。baseService 不在主档的名字不进映射
    (``materialize`` 会以 ``auth_draft_service_unknown`` 422 拒整单)。
    """
    if not drafts:
        return {}
    services = {d.base_service for d in drafts}
    known = set((await db.execute(
        select(Service.name).where(Service.name.in_(services)))).scalars())
    return {d.name: d.base_service
            for d in drafts if d.base_service in known}


async def materialize(
    db: AsyncSession, drafts: list[AuthDraftIn], *,
    owner_id: int, project_id: int | None = None,
) -> list[str]:
    """身份草稿同事务落库;返回引用名清单(响应 ``newAuths`` 面)。

    先全量校验(环境/服务主档/条目名冲突/账户可见性),任一不过 →
    整单 ValueError,不落半截;校验全过才 add 行(flush 由调用方的
    事务边界统一,唯一索引兜并发)。
    """
    if not drafts:
        return []

    # 同一请求内引用名去重校验(重复 = 客户端错误,不静默合并)
    names = [d.name for d in drafts]
    if len(set(names)) != len(names):
        dup = sorted({n for n in names if names.count(n) > 1})
        raise _err(
            "auth_draft_name_duplicated",
            "调用身份引用名重复:" + "、".join(dup))

    # 环境:一次性取全(缺任一 → 422)
    env_ids = {d.env_id for d in drafts}
    envs = set((await db.execute(
        select(Environment.id).where(Environment.id.in_(env_ids))))
        .scalars())
    _miss_env = sorted(env_ids - envs)
    if _miss_env:
        raise _err(
            "auth_draft_env_not_found",
            f"环境不存在:{_miss_env[0]}(调用身份请选择已有环境)")

    # 服务主档:baseService 必须已登记(同系统多服务由实例决定)
    bases = {d.base_service for d in drafts}
    svc_system = dict((await db.execute(
        select(Service.name, Service.system).where(
            Service.name.in_(bases)))).all())
    _miss_base = sorted(b for b in bases if b not in svc_system)
    if _miss_base:
        raise _err(
            "auth_draft_service_unknown",
            "服务不在主档:" + "、".join(_miss_base)
            + " —— 请先在服务注册页登记服务(或改选已有服务实例)")

    # 条目名冲突(全局唯一):行为规则① —— 提示直接引用,不覆盖
    taken = set((await db.execute(
        select(ServiceIdentity.alias_name).where(
            ServiceIdentity.alias_name.in_(names)))).scalars())
    if taken:
        raise _err(
            "auth_draft_alias_taken",
            "引用名已登记:" + "、".join(sorted(taken))
            + " —— 直接引用该条目,或去认证管理修改")

    # 账户可见性:本人池(owner_id) ∪ 场景项目池(project_id)。
    # env 不参与匹配(§8.3:身份 env = 执行标签,账户 env = 归档/登录口);
    # 同名多 env 账户存在即算命中,执行时按身份 env 优先挑选。
    pool_clauses = [
        and_(AuthAccount.owner_id == owner_id,
             AuthAccount.project_id.is_(None)),
    ]
    if project_id is not None:
        pool_clauses.append(
            and_(AuthAccount.project_id == project_id,
                 AuthAccount.owner_id.is_(None)))
    for d in drafts:
        system = svc_system[d.base_service]
        hit = (await db.execute(
            select(AuthAccount.id).where(
                or_(*pool_clauses),
                AuthAccount.system == system,
                AuthAccount.username == d.username).limit(1)
        )).scalar_one_or_none()
        if hit is None:
            raise _err(
                "auth_draft_account_not_found",
                f"账户 {d.username!r} 在系统 {system!r} 不在本人池或"
                "场景项目池 —— 先在凭证池创建/选用该账户,再建引用条目")

    for d in drafts:
        db.add(ServiceIdentity(
            alias_name=d.name, base_service=d.base_service,
            env_id=d.env_id, ref_mode="username",
            ref_username=d.username, display=d.display or ""))
    return names
