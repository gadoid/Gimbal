"""凭证治理 §3.3 手配落池(阶段 2;拍板 2026-11-20 方案 A)。

场景保存链的**同事务**手配落池:``ScenarioDraft.authDrafts`` →
① AuthAccount 本人池行(Fernet,掩码闸与 /auths 同单源)+ ②
ServiceIdentity(username-ref,指向该账户)。引用名 = 场景引用的
条目名 —— 与 identity_missing / 圈定 / 绑定 / 令牌范围全链天然一致
(``_resolve_identities`` 只认条目,裸账户名不解,方案 A 由此拍定)。

**权限面(方案 A 的代价,已入账待用户否决)**:普通用户随场景保存
自助建 username-ref 自用条目 —— 此前条目创建是 alias.write 能力面
(authz W7 导入门同款);目录/部署管理仍属 admin 面,手配条目的
base_service 必须取自主档既有服务(未知系统 422,指引服务注册)。

不 commit —— 事务边界在调用方(``create_in_transaction`` /
``update`` 的单事务里,场景保存失败整单回滚,池无孤儿行,行为
规则④)。冲突码(调用方映射):

* ``auth_draft_env_not_found`` / ``auth_draft_system_unknown`` → 422;
* ``auth_draft_account_not_found``(引用已有账户但四元组不在本人池)
  → 422(检索面「选用」通道,2026-11-21);
* ``auth_draft_alias_taken`` / ``auth_draft_account_exists`` → 409
  (行为规则①:提示「直接引用 / 去认证管理修改」,不静默覆盖);
* ``auth_draft_name_duplicated``(同一请求内重名)→ 422。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core._password_gate import require_maskable_password
from ..core.security import fernet_encrypt
from ..models import Environment, Service
from ..models.auth_account import AuthAccount
from ..models.service_identity import ServiceIdentity
from ..schemas.scenario_composer import AuthDraftIn


def _err(code: str, message: str) -> ValueError:
    """``ValueError("code: message")`` —— 调用方 value_error_http 映射。"""
    return ValueError(f"{code}: {message}")


async def base_overrides(
    db, drafts: list,
) -> dict[str, str]:
    """草稿名 → 落池后条目的 base_service(声明侧同 base 闸的 extra_bases
    叠层,2026-11-21 评审 P2-2):派生与 ``materialize`` 同款 —— 草稿
    system → 主档该系统字典序首个服务名(确定性;条目→系统派生只看
    system 字段)。system 不在主档的名字**不进**映射(闸无从裁;
    ``materialize`` 会以 ``auth_draft_system_unknown`` 422 拒整单,
    时序上闸先跑、落池后跑,坏草稿根本到不了库里)。

    闸在 materialize 之前跑、草稿名此刻未入库 —— ``same_base_
    violations`` 的「未登记跳过」会放走全部草稿引用,跨服务步骤引用
    手配草稿 = 首次保存双闸全过(TOK-07 泄漏形态,第二次 PUT 才拦)。
    本映射把草稿 base 显式带给闸,首存即裁。"""
    if not drafts:
        return {}
    svc_rows = (await db.execute(
        select(Service.name, Service.system).where(
            Service.system.in_({d.system for d in drafts})))).all()
    by_system: dict[str, list[str]] = {}
    for name, sysname in svc_rows:
        by_system.setdefault(sysname, []).append(name)
    return {d.name: sorted(by_system[d.system])[0]
            for d in drafts if by_system.get(d.system)}


async def materialize(
    db: AsyncSession, drafts: list[AuthDraftIn], *, owner_id: int,
) -> list[str]:
    """手配清单同事务落池;返回引用名清单(响应 newAuths 面)。

    先全量校验(环境/主档系统/条目名冲突/账户四元组冲突/掩码闸),
    任一不过 → 整单 ValueError,不落半截;校验全过才 add 行(flush 由
    调用方的事务边界统一,唯一索引兜并发)。
    """
    if not drafts:
        return []

    # 同一请求内引用名去重校验(重复 = 客户端错误,不静默合并)
    names = [d.name for d in drafts]
    if len(set(names)) != len(names):
        dup = sorted({n for n in names if names.count(n) > 1})
        raise _err(
            "auth_draft_name_duplicated",
            "手配凭证引用名重复:" + "、".join(dup))

    # 环境:一次性取全(缺任一 → 422)
    env_ids = {d.env_id for d in drafts}
    envs = set((await db.execute(
        select(Environment.id).where(Environment.id.in_(env_ids))))
        .scalars())
    _miss_env = sorted(env_ids - envs)
    if _miss_env:
        raise _err(
            "auth_draft_env_not_found",
            f"环境不存在:{_miss_env[0]}(手配凭证请选择已有环境)")

    # 系统 → 主档代表服务:手配条目的 base_service 必须落主档既有
    # 服务(目录管理属 admin 面);同名系统多服务时任取字典序首个
    # (确定性;条目→系统派生只看 system 字段)。
    systems = {d.system for d in drafts}
    svc_rows = (await db.execute(
        select(Service.name, Service.system).where(
            Service.system.in_(systems)))).all()
    by_system: dict[str, list[str]] = {}
    for name, sysname in svc_rows:
        by_system.setdefault(sysname, []).append(name)
    _miss_sys = sorted(s for s in systems if not by_system.get(s))
    if _miss_sys:
        raise _err(
            "auth_draft_system_unknown",
            "系统不在主档:" + "、".join(_miss_sys)
            + " —— 手配凭证的系统须已有登记服务,请先在服务注册页登记"
              "(或改选已有系统)")

    # 条目名冲突(全局唯一):行为规则① —— 提示直接引用,不覆盖
    taken = set((await db.execute(
        select(ServiceIdentity.alias_name).where(
            ServiceIdentity.alias_name.in_(names)))).scalars())
    if taken:
        raise _err(
            "auth_draft_alias_taken",
            "引用名已登记:" + "、".join(sorted(taken))
            + " —— 直接引用该条目,或去认证管理修改")

    # 账户四元组(owner × system × env × username):
    # * 新建账户(password 给定)撞四元组 → 409 不静默覆盖(规则①);
    # * 引用已有账户(password 缺省)四元组必须命中 → 否则 422
    #   (检索面「选用」通道:只建条目,账户须已在本人池)。
    for d in drafts:
        hit = (await db.execute(
            select(AuthAccount.id).where(
                AuthAccount.owner_id == owner_id,
                AuthAccount.system == d.system,
                AuthAccount.env_id == d.env_id,
                AuthAccount.username == d.username))).scalar_one_or_none()
        if d.password is None:
            if hit is None:
                raise _err(
                    "auth_draft_account_not_found",
                    f"账户 {d.username!r} 在系统 {d.system!r} × 环境"
                    f"#{d.env_id} 不在本人凭证池 —— 请先手配或去凭证管理添加")
        elif hit is not None:
            raise _err(
                "auth_draft_account_exists",
                f"账户 {d.username!r} 在系统 {d.system!r} × 环境"
                f"#{d.env_id} 已存在 —— 直接引用同名条目,或去认证管理修改")

    # 校验全过 → 掩码闸(仅新建账户)+ 落行(不 commit,事务归调用方)
    for d in drafts:
        if d.password is not None:
            require_maskable_password(d.password)
    for d in drafts:
        base = sorted(by_system[d.system])[0]
        db.add(ServiceIdentity(
            alias_name=d.name, base_service=base, env_id=d.env_id,
            ref_mode="username", ref_username=d.username))
        if d.password is None:
            continue    # 引用已有账户:只建条目,不碰账户行
        # 未显式置默认时与 /auths 同口径:该 system 首账户即默认
        has_default = (await db.execute(
            select(AuthAccount.id).where(
                AuthAccount.owner_id == owner_id,
                AuthAccount.system == d.system,
                AuthAccount.is_default.is_(True)))).scalar_one_or_none()
        db.add(AuthAccount(
            owner_id=owner_id, system=d.system, env_id=d.env_id,
            username=d.username, password_enc=fernet_encrypt(d.password),
            account_fields=d.account_fields, is_default=has_default is None))
    return names
