"""services/run_prepare.py — 执行装载准备(五执行链归一单源)。

「把平台场景变成可执行 case」的**准备段唯一实现**:凭证清单、凭证
解析、别名地址、carry 上下文、内置 users 基座、生效修订解析、
compose(数据行合入)。五个入口全部消费本模块:

  单场景执行 run_dispatcher._fanout          prepare_exec(single)
  Suite 编排   graph_dispatch.materialize_graph  graph_auth_aliases(逐单元
                                             并集)+ unit_carry_contexts
                                             (套件交集仍走 suite_version,
                                             本模块不重复)
  集成        integration_runner.run_instance  prepare_exec(strict/none)
  导出/预览   routers/scenarios._materialized_executable  prepare_exec
                                             (none,with_auth=仅 overlay)
  预检        run_precheck(地址链 run_materialize.service_url_resolved
                                             同源)+ suites validate
                                             (graph_auth_aliases 清单同源)

归一不变式:五个入口的差异只允许以参数表达(auth_policy /
resolve_mode),凭证清单算法、地址链、carry 不允许任何调用方自选
—— 各链自写编排会重开清单口径/降级语义漂移的口子,集成与导出链
也必须走 prepare_exec 全量编排,不得只调子函数「半归一」。

模块符号的分层位置:装载准备属 services 层单源(run_dispatcher/
suites 等消费方跨模块引用,私有名可达性曾致真实导入错误)。

签名约定:凭证解析只收**会话工厂**(独立短会话快照语义,与执行期
隔离);纯读助手(find_dataset_by_id)收活会话。resolve_mode="none"
供集成链与导出链使用:集成链的 meta.plate 声明域恒为完整钉修订(裸线
在声明域即 INVALID,working 被 working_preview 闸拒绝),/convert 按
钉修订取不可变快照,且集成不写执行台账(决策 3)—— 无 resolve+merge
必要;导出链按定义原样 convert(修订解析属执行链语义)。
"""
from __future__ import annotations

import copy
import dataclasses
from dataclasses import dataclass, field
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schema import AuthSession as RuntimeAuthSession  # noqa: E402

from ..models.auth_account import AuthAccount as DBAuthAccount
from ..models.composer_data_set import ComposerDataSet
from ..models.service import Service as DBService
from ..models.service_identity import ServiceIdentity as DBIdentity
from ..models.system_env_instance import SystemEnvInstance as DBInstance
from . import plate_client, service_aliases
from .run_semantics import INTEGRATION, PIN, record_category
from .data_set_store import get_row as get_dataset_row
from .scenario_store import definition_from_payload

__all__ = [
    "ResolvedAuth", "AuthResolveError", "MissingAuthAliases",
    "resolve_exec_auths", "compose_scenario", "coerce_row_value",
    "built_in_users", "built_in_user_aliases", "find_dataset_by_id", "ExecPrep", "prepare_exec",
    "graph_auth_aliases", "unit_carry_contexts",
]


# ResolvedAuth = 平台侧轻量值对象,内部委托标准 AuthSession。下游
# materialize_run_copy(_apply_users)消费 username/password/url/token_type/
# expires_in 这几个字段,与标准 AuthSession 完全对齐(后者字段更多但不影响注入
# 逻辑)。保留 ResolvedAuth 作为兼容 shim,免改下游的字段引用。
@dataclass(frozen=True, slots=True)
class ResolvedAuth:
    """解密后的执行认证(轻量值对象,保留兼容 shim)。

    明文凭证只存在于该对象的生命周期内,不落在 AuthSession ORM 行
    上 — 避免任何意外 commit 把明文写回数据库。

    内部委托给标准 RuntimeAuthSession,字段对齐下游消费者。
    """

    alias: str
    url: str
    username: str
    password: str
    token_type: str
    expires_in: int
    # S4:条目账号级字段(${slot.X.field} 派发前替换的数据源)
    account_fields: dict = field(default_factory=dict)
    # S5:取用绑定元数据(指纹/预览的绑定标识;不改注入行为)
    binding_id: int | None = None

    @classmethod
    def from_runtime(cls, runtime: "RuntimeAuthSession", alias: str,
                     account_fields: dict | None = None) -> "ResolvedAuth":
        """从标准 RuntimeAuthSession 构造,供 resolve_exec_auths 内部使用。"""
        return cls(
            alias=alias,
            url=runtime.url,
            username=runtime.username,
            password=runtime.password,
            token_type=runtime.token_type,
            expires_in=runtime.expires_in or 0,
            account_fields=account_fields or {},
        )


class AuthResolveError(RuntimeError):
    """执行认证解密失败 — fail-fast,同 V1 executor 的 ``_decrypt_auths``
    语义(解密失败上抛使整个 run 失败,而不是带着空/坏凭证静默打环境)。"""


class MissingAuthAliases(RuntimeError):
    """严格缺凭证策略(prepare_exec(auth_policy="strict"))下清单中
    有别名在执行身份名下解不到 —— 集成链据此暂停实例
    (paused/missing_credential),宽松链不抛(执行期步骤级报错)。"""

    def __init__(self, missing: list[str]):
        super().__init__(f"missing auth aliases: {missing}")
        self.missing = list(missing)


def _pool_clause(owner_id: int | None, cred_project_id: int | None):
    """账户池谓词(S8 口径沿用):``cred_project_id`` 非空 = 项目池,
    否则执行人个人池。两池互斥(CHECK 归属恰一)—— 不混取。"""
    if cred_project_id is not None:
        return DBAuthAccount.project_id == cred_project_id
    if owner_id is None:
        # 潜伏 fail-open 守卫:owner_id IS NULL
        # 会匹配**全部项目池行**(归属恰一 CHECK:owner NULL ⇔ project
        # 非空)—— 双 None 即「无主读全项目池」。现四调用面均不可达
        # 双 None,此处显式拒绝而非渲染恒真谓词,防止未来调用点静默
        # fail-open。
        raise ValueError(
            "pool_clause: owner_id 与 cred_project_id 均缺 —— "
            "拒绝渲染 IS NULL 全项目池谓词")
    return DBAuthAccount.owner_id == owner_id


def _pick_account_deterministic(
        cands: list[DBAuthAccount], tag: int) -> DBAuthAccount | None:
    """同标签优先 → 唯一命中;多行歧义由调用方归类(§8.3)。

    取用面**唯一实现**:token 范围复核(access_token.check_scope)同走本函数
    对齐执行口径 —— 候选集任一命中放行会在同引用多候选时可选
    中范围外账户(D1 越权窗口),禁用。"""
    same = [a for a in cands if a.env_id == tag]
    if len(same) == 1:
        return same[0]
    if len(cands) == 1:
        return cands[0]
    return None   # 0 行(None 外理)或多行歧义


@dataclass(frozen=True, slots=True)
class PickedIdentity:
    """身份条目取用结果(轻量,不解密;消费方按 ``slot``(条目名)对账,
    指纹/预览按 ``account_id`` 标识绑定)。"""

    slot: str          # 条目名(引用键,${auth.X}/call.user=X 的 X)
    account_id: int    # 命中账户(绑定标识)
    env_id: int        # **账户标签**(登录口坐标;§8.3 不变式:密码与登录口同源)
    system: str        # 条目系统(base_service → services.system 派生)
    base_service: str
    # 条目标签(执行标签链 identity 位的取值依据;§8.2)
    identity_env_id: int
    # 命中账户是否默认位(预览 bindingId/isDefault 消费)
    is_default: bool = False


async def _resolve_identities(
    db: Any, owner_id: int | None, names: list[str], *,
    cred_project_id: int | None = None,
) -> tuple[dict[str, PickedIdentity], list[str], list[str]]:
    """身份条目解析单源(§4.1 + §8.3 凭证去 env 匹配;不解密):
    条目名 → 取用账户 id。

    链路:条目 → 服务主档(系统派生)→ 账户池。**引用不校验标签**:
    * ``ref_mode=username``:同标签(条目 env)账户优先 → system 内
      唯一命中 → 多行歧义(``ambiguous``,预检/派发硬拦截);
    * ``ref_mode=default``:system 唯一默认账户(0059 后索引钉死);
    返回 (命中, 缺失, 歧义)。缺失口径(**无回退分支**,决策 8):
    条目不存在 / 服务不在主档 / ref 账户缺席。
    """
    if not names:
        return {}, [], []
    uniq = list(dict.fromkeys(names))
    missing: set[str] = set()
    ambiguous: set[str] = set()
    cand: dict[str, DBIdentity] = {}
    idents = (await db.execute(select(DBIdentity).where(
        DBIdentity.alias_name.in_(uniq)))).scalars().all()
    for i in idents:
        cand[i.alias_name] = i
    missing.update(n for n in uniq if n not in cand)
    if not cand:
        return {}, sorted(missing), sorted(ambiguous)

    # 条目系统派生:base_service → services.system(悬空条目 → missing)
    svc_rows = (await db.execute(
        select(DBService.name, DBService.system).where(
            DBService.name.in_({i.base_service for i in cand.values()}))
    )).all()
    system_of = dict(svc_rows)

    # 账户目标收集(ref)并批量取(无标签过滤 —— 标签只做取用偏好)
    want_user: set[tuple[str, str]] = set()
    want_default: set[str] = set()
    for i in cand.values():
        sysname = system_of.get(i.base_service)
        if not sysname:
            continue
        if i.ref_mode == "username" and i.ref_username:
            want_user.add((sysname, i.ref_username))
        else:
            want_default.add(sysname)
    accs_by_key: dict[tuple[str, str], list[DBAuthAccount]] = {}
    accs_default: dict[str, list[DBAuthAccount]] = {}
    if want_user or want_default:
        conds: list[Any] = []
        for sysname, username in want_user:
            conds.append((DBAuthAccount.system == sysname)
                         & (DBAuthAccount.username == username))
        for sysname in want_default:
            conds.append((DBAuthAccount.system == sysname)
                         & DBAuthAccount.is_default.is_(True))
        from sqlalchemy import or_
        accs = (await db.execute(select(DBAuthAccount).where(
            _pool_clause(owner_id, cred_project_id),
            or_(*conds)))).scalars().all()
        for a in accs:
            accs_by_key.setdefault((a.system, a.username), []).append(a)
            if a.is_default:
                accs_default.setdefault(a.system, []).append(a)

    picked: dict[str, PickedIdentity] = {}
    for name, i in cand.items():
        sysname = system_of.get(i.base_service)
        if not sysname:
            missing.add(name)
            continue
        if i.ref_mode == "username" and i.ref_username:
            cands = accs_by_key.get((sysname, i.ref_username), [])
        else:
            cands = accs_default.get(sysname, [])
        acc = _pick_account_deterministic(cands, i.env_id)
        if acc is None:
            if cands:
                ambiguous.add(name)   # 多候选且无同标签唯一命中
            else:
                missing.add(name)
            continue
        picked[name] = PickedIdentity(
            slot=name, account_id=acc.id, env_id=acc.env_id,
            system=sysname, base_service=i.base_service,
            identity_env_id=i.env_id, is_default=acc.is_default)
    return picked, sorted(missing), sorted(ambiguous)


async def pick_bindings(
    db: Any, owner_id: int | None, slots: list[str],
    *, cred_project_id: int | None = None,
) -> list[PickedIdentity]:
    """条目取用单源(不解密;§4.4):条目名 → :class:`PickedIdentity`。
    ``resolve_exec_auths``(注入)与指纹/预览的绑定标识消费同一份裁决
    —— 取用口径结构上不可能漂移。

    S8:``cred_project_id`` 非空 → 从项目池取用(项目账户池),缺省 =
    ``owner_id`` 个人池。``slots`` 语义 = 身份条目名(旧槽名口径,
    规约延续)。"""
    picked, _missing, _ambiguous = await _resolve_identities(
        db, owner_id, slots, cred_project_id=cred_project_id)
    return sorted(picked.values(), key=lambda r: r.slot)


async def pick_bindings_full(
    db: Any, owner_id: int | None, slots: list[str],
    *, cred_project_id: int | None = None,
) -> "tuple[list[PickedIdentity], list[str], list[str]]":
    """同 :func:`pick_bindings`,带回 ``(picked, missing, ambiguous)``
    分类(fail-fast 差集把歧义条目统一报「未登记」
    误导排障 —— 消费方按类分道,歧义给 409/独立码)。同一单源
    ``_resolve_identities``,取用口径与 pick_bindings 结构上一致。"""
    picked, missing, ambiguous = await _resolve_identities(
        db, owner_id, slots, cred_project_id=cred_project_id)
    return (sorted(picked.values(), key=lambda r: r.slot),
            sorted(missing), sorted(ambiguous))


# ── 数据集按账号驱动:行级账号列 ``@slot.<槽名>`` = 绑定名 ─────
ROW_BINDING_PREFIX = "@slot."


def row_binding_refs(row: dict | None) -> dict[str, str]:
    """行内账号列 → {槽名: 绑定名}(值为空 = 不覆盖,沿用执行级取用)。"""
    out: dict[str, str] = {}
    for k, v in (row or {}).items():
        if (isinstance(k, str) and k.startswith(ROW_BINDING_PREFIX)
                and len(k) > len(ROW_BINDING_PREFIX)
                and isinstance(v, str) and v.strip()):
            out[k[len(ROW_BINDING_PREFIX):]] = v.strip()
    return out


def strip_row_binding_columns(row: dict | None) -> dict:
    """行值并入 vars 前剔除账号列(账号列不是变量)。"""
    return {k: v for k, v in (row or {}).items()
            if not (isinstance(k, str) and k.startswith(ROW_BINDING_PREFIX))}


async def lookup_row_bindings(
    db: Any, owner_id: int | None, pairs: set[tuple[str, str]],
    *, cred_project_id: int | None = None,
) -> tuple[dict[tuple[str, str], PickedIdentity], list[tuple[str, str]],
           list[tuple[str, str]]]:
    """(引用位, 绑定名) → 池内取用结果(不解密)。返回 (命中, 缺失,
    歧义);绑定名 = 身份条目名。行级覆盖语义 = 该行把引用位换成
    指定身份(条目模型无槽,不做同名性校验 —— 跨身份覆盖是行级
    数据的本意);引用不校验标签(§8.3),歧义 = 同 system 多行候选
    且无同标签唯一命中。"""
    if not pairs:
        return {}, [], []
    names = list({a for _s, a in pairs})
    picked, miss_names, amb_names = await _resolve_identities(
        db, owner_id, names, cred_project_id=cred_project_id)
    miss_set, amb_set = set(miss_names), set(amb_names)
    hit: dict[tuple[str, str], PickedIdentity] = {}
    missing: list[tuple[str, str]] = []
    ambiguous: list[tuple[str, str]] = []
    for slot, alias in sorted(pairs):
        p = picked.get(alias)
        if p is not None:
            hit[(slot, alias)] = p
        elif alias in amb_set:
            ambiguous.append((slot, alias))
        else:
            missing.append((slot, alias))
    return hit, missing, ambiguous


async def resolve_row_bindings(
    db_factory: Any, owner_id: int | None, pairs: set[tuple[str, str]],
    *, cred_project_id: int | None = None,
) -> dict[tuple[str, str], ResolvedAuth]:
    """行级覆盖绑定解密(执行内每个 (引用位, 绑定名) 只解密一次)。
    缺失/歧义的已在派发 fail-fast 拦下 —— 这里只解析命中项;
    url 取实例登录口(按账户标签;缺席 = '' 走静态令牌路径)。"""
    if not pairs:
        return {}
    from ..core.security import fernet_decrypt

    async with db_factory() as session:
        hit, _m, _a = await lookup_row_bindings(
            session, owner_id, pairs, cred_project_id=cred_project_id)
        if not hit:
            return {}
        resolved = await _materialize_identities(session, hit)
    return resolved


async def _materialize_identities(
    db: Any, hit: dict[Any, PickedIdentity],
) -> dict[Any, ResolvedAuth]:
    """取用结果 → 解密值对象(共用:执行级 resolve_exec_auths 与行级
    resolve_row_bindings)。键原样保留(执行级 = 条目名,行级 = (引用位,
    绑定名));注入键(ResolvedAuth.alias)由调用方在 dataclasses.replace
    里覆写。"""
    from ..core.security import fernet_decrypt

    acc_ids = {p.account_id for p in hit.values()}
    accs = {a.id: a for a in (await db.execute(
        select(DBAuthAccount).where(DBAuthAccount.id.in_(acc_ids))
    )).scalars().all()}
    systems = {p.system for p in hit.values()}
    inst_urls: dict[tuple[str, int], str] = {}
    if systems:
        inst_urls = {(sys_, eid): url for sys_, eid, url in (await db.execute(
            select(DBInstance.system, DBInstance.env_id,
                   DBInstance.login_url).where(DBInstance.system.in_(systems))
        )).all()}
    out: dict[Any, ResolvedAuth] = {}
    for key, p in hit.items():
        a = accs.get(p.account_id)
        if a is None:
            continue
        try:
            runtime = RuntimeAuthSession(
                url=inst_urls.get((p.system, p.env_id), ""),
                username=a.username,  # 账户实体键为明文列(§1.4)
                password=fernet_decrypt(a.password_enc),
                token_type=a.token_type,
                expires_in=a.expires_in,
            )
        except ValueError as e:
            raise AuthResolveError(
                f"auth binding '{p.slot}' decrypt failed: {e}") from e
        out[key] = dataclasses.replace(
            ResolvedAuth.from_runtime(
                runtime, alias=p.slot, account_fields=a.account_fields),
            binding_id=a.id)
    return out


def apply_row_bindings(
    exec_auths: list["ResolvedAuth"], row: dict | None,
    resolved: dict[tuple[str, str], "ResolvedAuth"],
) -> list["ResolvedAuth"]:
    """按行覆盖执行级凭证组:行账号列命中的槽换成该行的绑定,其余不变。

    注入键保持**引用位标签**不变(场景步骤 ``call.user``/``${auth.*}``/
    ``${slot.*}`` 引用的是声明位;注入键必须覆写为 alias,
    users/fields_by_slot 才能按条目名落键、模板引用才可命中)。"""
    import dataclasses as _dc

    refs = row_binding_refs(row)
    if not refs:
        return exec_auths
    out = {a.alias: a for a in exec_auths}
    for slot, alias in refs.items():
        r = resolved.get((slot, alias))
        if r is not None:
            out[slot] = _dc.replace(r, alias=slot)
    return list(out.values())


async def binding_ids_for(
    db_factory: Any, owner_id: int | None, slots: list[str],
    *, cred_project_id: int | None = None,
    slot_map: dict[str, str] | None = None,
) -> dict[str, int]:
    """条目名 → 取用账户 id(轻量,不解密;指纹/预览消费)。分层②:
    ``slot_map`` 同 :func:`resolve_exec_auths`(键 = 声明引用标签)。"""
    if not slots:
        return {}
    lookup = slot_map or {}
    async with db_factory() as s:
        rows = await pick_bindings(
            s, owner_id, list(dict.fromkeys(
                lookup.get(x, x) for x in slots if lookup.get(x, x))),
            cred_project_id=cred_project_id)
    by_slot = {r.slot: r.account_id for r in rows}
    return {x: by_slot[lookup.get(x, x)]
            for x in dict.fromkeys(slots) if lookup.get(x, x) in by_slot}


async def resolve_exec_auths(
    db_factory: Any, owner_id: int | None, aliases: list[str],
    *, cred_project_id: int | None = None,
    slot_map: dict[str, str] | None = None,
) -> list[ResolvedAuth]:
    """身份条目名 → ResolvedAuth(解密后的轻量值对象)。

    §4.1(条目→ref→账户)+ §8.3(引用不校验标签):``aliases`` = 身份
    条目名(场景 ``call.user``/``${auth.*}`` 引用键);取用经
    :func:`_resolve_identities`(owner/项目池过滤防跨池解错),解密经
    :func:`_materialize_identities`(url = 实例登录口,**按账户标签**
    —— 密码与登录口同源不变式;缺席 = '' 走静态令牌路径,配置缺失在
    预检期明确报,不回退业务地址)。

    分层② ``slot_map``(声明引用 → 池内取用条目):执行配置绑定的
    「换池内命中」—— 取用按映射后的条目,注入标签保持声明名
    (场景引用不变)。

    * 解密失败 → 抛 :class:`AuthResolveError`(V1 严格语义:
      凭证路径 fail-fast,不静默降级)。
    * 条目解不到(不存在/悬空/无账户)或账户歧义 → 告警后继续(与 V1
      一致:缺条目只是注入不到 users,该行 run 在 Gimbal 解析
      ``${auth.*}`` 时步骤级报错;歧义在预检/派发期硬拦截)。
    * 明文只存在于返回的值对象上 — 绝不写回 ORM 行。

    **只收会话工厂**:内部开独立短会话做快照读,与调用方的
    长事务隔离。
    """
    if not aliases:
        return []
    lookup = slot_map or {}
    pick_names = list(dict.fromkeys(
        lookup.get(a, a) for a in aliases if lookup.get(a, a)))
    resolved: list[ResolvedAuth] = []
    missing_names: set[str] = set()
    by_name: dict[str, "ResolvedAuth"] = {}
    async with db_factory() as session:
        picked, miss, amb = await _resolve_identities(
            session, owner_id, pick_names, cred_project_id=cred_project_id)
        missing_names.update(miss)
        if amb:
            logger.warning(
                "run_prepare: exec auth identities ambiguous "
                "(same system, multiple tag candidates): {}", amb)
        if picked:
            by_name = await _materialize_identities(session, picked)
    for label in dict.fromkeys(aliases):
        r = by_name.get(lookup.get(label, label))
        if r is None:
            continue
        # 分层②:注入标签 = 声明引用名(场景侧),取用行是覆盖条目
        resolved.append(dataclasses.replace(r, alias=label))
    if missing_names:
        logger.warning(
            "run_prepare: exec auth identities not found: {}",
            sorted(missing_names),
        )
    return resolved


def built_in_user_aliases(scenario_payload: dict | None) -> list[str]:
    """场景内置认证的别名清单(只给名字,不给凭证)—— 展示 / 预检告警
    用(§7.1 内置认证清单、builtin_auth_shadowed)。"""
    def_cfg = definition_from_payload(scenario_payload).get("config") or {}
    users = def_cfg.get("users") if isinstance(def_cfg.get("users"), dict) else {}
    return sorted(str(k) for k in (users or {}))


def zone_allows_direct(project_kind: str | None) -> bool:
    """场景内置凭证(``config.users``)的存量区判定 —— **仅剩导出面
    消费**(10-14 口径:属主导出携带自有明文)。v2.10 §11.1 起执行链
    一律不吃内置凭证(禁止资产内嵌秘密,改授权凭证引用):执行 /
    Suite 编排 / 集成 / 查询链不再传 ``built_in_users``。None =
    未知归属,fail-closed 不生效。"""
    return project_kind == "private"


async def project_kind_of(db: "Any", project_id: int | None) -> "str | None":
    """项目 kind 解析(UPC M2:built_in_users 的区轴数据源)。"""
    if project_id is None:
        return None
    from ..models.project import Project as _Proj

    proj = await db.get(_Proj, project_id)
    return proj.kind if proj is not None else None


def built_in_users(
    scenario_payload: dict | None, *,
    executor_id: int | None,
    scenario_owner_id: int | None,
    project_kind: str | None,
) -> dict[str, Any]:
    """场景 definition.config.users —— 仅当执行人 == 场景属主、且场景在
    私有区时返回。

    **v2.10 §11.1:执行链已退役** —— 执行 / Suite 编排 / 集成 / 查询
    链一律不传内置基座(users 唯一来源 = 凭证池解析);本函数仅剩
    **导出面**消费(10-14 口径:属主导出携带自有明文,数据可携性
    非执行语义)。其余(非属主导出等)一律当空。
    **fail-closed**:两参必填,任一为 None(属主已删的孤儿场景、
    调用方漏传)同样当空 —— None = 无主数据,不判直接放行会形成
    越权窗口。作者即席提供 payload 的路径(草稿预览、临时调用)
    由调用方显式传 ``scenario_owner_id = executor_id``。只要名字的展示面
    用 :func:`built_in_user_aliases`。

    ``project_id``(必填):项目 / 公共区场景当空(属主本人执行
    同样当空 —— 区规则不看人)。
    """
    if not zone_allows_direct(project_kind):
        return {}
    if executor_id is None or executor_id != scenario_owner_id:
        return {}
    def_cfg = definition_from_payload(scenario_payload).get("config") or {}
    users = def_cfg.get("users") if isinstance(def_cfg.get("users"), dict) else {}
    return dict(users or {})


async def find_dataset_by_id(
    db: AsyncSession, dataset_id: str
) -> ComposerDataSet | None:
    return await get_dataset_row(db, dataset_id)


def coerce_row_value(base_val: Any, row_val: Any) -> Any:
    """行值按基线类型还原(新数据集编辑器把所有值存成字符串)。

    转置表格/CSV 导入统一 ``String(v)`` 落库,直接合入会把整型基线
    覆盖成字符串,破坏 ``Assertion{expected: 0}`` 这类强类型断言
    ("int 还是 int"的类型强制语义)。规则:

    * 基线是 bool  → ``"true"/"false"``(大小写不敏感)还原,其余原样;
    * 基线是 int   → ``int(row_val)`` 可解析则还原(int("2.0") 会抛
      ValueError,正好保留原串);
    * 基线是 float → ``float(row_val)`` 可解析则还原;
    * 其余(str/生成式 dict/基线不存在)→ 原样合入 —— 空串仍是显式
      空覆盖,生成式 spec 不受行值影响。
    """
    if not isinstance(row_val, str) or not isinstance(base_val, (bool, int, float)):
        return row_val
    if isinstance(base_val, bool):
        lowered = row_val.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        return row_val
    try:
        if isinstance(base_val, int):
            return int(row_val)
        return float(row_val)
    except ValueError:
        return row_val


def compose_scenario(
    scenario_payload: dict, row_dict: dict
) -> dict[str, Any]:
    """配置器:把存储的 Scenario + 一行数据 变换成 Plate 输入。

    源存果算 — 这里是唯一的变换点:存储里只有场景定义(源)与
    数据行(纯值),每个 run 的形态由本函数即时计算:

    * deep-copy 场景定义,行键值合入 ``config.vars``(行值覆盖同名
      场景级 var)。行值按基线类型还原(新数据集编辑器全字符串落库,
      ``coerce_row_value`` 恢复"int 还是 int"的旧语义,断言
      ``expected: 0`` 不会被字符串化破坏)。
    * 数据集行是稀疏覆盖(缺键 = 继承基线,即场景级 vars 原值;
      ``""`` = 显式空覆盖),与行 0 基线虚行/三态单元格的编辑器
      契约一致 —— 基线行本身不落库,由场景 vars 承担。
    * ``scenario_payload`` 是持久化的 ``ComposerScenario.payload``。
      容器化重构后为 ``{definition, orchestration}``;plate 只吃
      ``definition``(orchestration 是平台侧投影,绝不外发)。
    * 定义即纯 M2,Meta 只 name 必填,不补 plate 默认值(缺省语义
      在引擎侧,ADR-0003 #15)。
    """
    raw = scenario_payload or {}
    # Unwrap the container: plate must never see orchestration.
    out = copy.deepcopy(definition_from_payload(raw))
    cfg = out.setdefault("config", {})
    if not isinstance(cfg, dict):
        cfg = {}
        out["config"] = cfg
    vars_map = dict(cfg.get("vars") or {})
    # Row wins: a row's `qty` overrides a scenario-level `vars.qty`.
    for k, v in (row_dict or {}).items():
        vars_map[k] = coerce_row_value(vars_map.get(k), v)
    cfg["vars"] = vars_map
    return out


# ─── 准备段统一入口 ────────────────────────────────────────────────

@dataclass
class ExecPrep:
    """一次执行(或一次导出)的准备产物。

    除 meta_plate 外为纯值;meta_plate **引用**调用方 payload 的
    ``definition.meta.plate`` 且在 resolve_mode="single" 时被原地修订
    (生效修订回写,compose/convert 输入依赖该回写 —— 见 prepare_exec
    签名说明的副作用;不落库)。

    单场景/集成/导出链经 :func:`prepare_exec` 产出;Suite 编排按单元
    组合(graph_auth_aliases + unit_carry_contexts + 套件交集)。
    """
    aliases: list[str] = field(default_factory=list)        # 注入清单(三源并集)
    resolved_auths: list[ResolvedAuth] = field(default_factory=list)
    missing_aliases: list[str] = field(default_factory=list)
    alias_base_urls: dict[str, str] = field(default_factory=dict)   # 地址③层数据源
    carry_ctx: Any = None                                    # CarryContext | None
    built_in_users: dict[str, Any] = field(default_factory=dict)
    meta_plate: dict[str, str] = field(default_factory=dict)  # 生效修订(已写回 definition)
    plate_pins: dict[str, str] = field(default_factory=dict)
    # 台账输入(resolve_mode="single" 时随修订解析一并产出,供执行侧
    # 入库标准判定与 pins 落库 —— 不属装载,但同源免二次遍历):
    endpoints_used: dict[str, set[str]] = field(default_factory=dict)
    unanchored_services: list[str] = field(default_factory=list)


async def prepare_exec(
    db_factory: Any, scenario_payload: dict | None, *, owner_id: int | None = None,
    bindings: dict[str, dict] | None = None,
    ui_field_states: dict | None = None,
    auth_policy: str = "lenient",
    resolve_mode: str = "single",
    with_auth: bool = True,
    scenario_owner_id: int | None = None,
    environment: Any = None,
    project_id: int | None = None,
    cred_project_id: int | None = None,
    slot_overrides: dict[str, str] | None = None,
    exec_carry_overrides: dict[str, dict[str, str | None]] | None = None,
    exec_carry_removals: "dict[str, list[str]] | None" = None,
    skip_carry: bool = False,
) -> ExecPrep:
    """准备段统一入口(每次执行一次;逐 case 段保持
    compose → convert → materialize_run_copy 不变)。

    * 凭证清单:``service_aliases.exec_auth_aliases``(模板扫描 ∪
      步骤服务条目)—— 算法单源,调用方不可自选;
    * 凭证解析:``resolve_exec_auths``(owner 级;S8 ``cred_project_id``
      非空 = 项目凭证池);``strict`` 下缺别名
      抛 :class:`MissingAuthAliases`(集成链捕获 → 暂停实例),
      ``lenient`` 仅记录(执行期步骤级报错);``with_auth=False``
      供调用方在更早处已用同一函数做过 fail-fast 解析(单场景链的
      认证先行序),跳过重复解密;
      分层②:``slot_overrides``({别名全名: 条目名},显式选定配置的
      绑定)→ ``slot_lookup_overrides`` 换池取用,注入标签不变;
    * 别名地址:``base_urls_for``(③层数据源;查表失败降级空表);
      ``environment``(``env_chain.EnvChoice``)= 派发时已解析的
      环境选择,并入部署表地址(缺省 = 旧 ③ 行为);
    * carry:``build_carry_context``(独立短会话;任何故障降级 None,
      carry 是增强不是前置条件);分层②:``exec_carry_overrides``
      ({目录服务: {字段: 值}})作为配置覆盖层,位次在场景显式之下、
      层序之上(区规则由调用方裁:项目区仅显式选定,决策 9);
    * 修订解析 ``resolve_mode``:
      ``single`` = plate resolve + merge_resolve_effective(PIN 写执行
      副本 / INTEGRATION 只写 pins;plate 拒绝/不可用原样上抛
      plate_rejected/plate_unavailable);
      ``none`` = 原样透传(集成/导出链,见模块 docstring 的定案理由)。

    **副作用**(§3.1 附注):``resolve_mode="single"`` 时**原地
    修订**入参 payload 的 ``definition.meta.plate``(merge_resolve_
    effective 的生效修订回写 —— compose/convert 的输入依赖该回写才能
    拿到生效修订;`_fanout` 在调用前 deepcopy 正是为了承接它)。调用
    方若不希望写穿存储/草稿对象,须自备副本;其余模式不改入参。
    """
    from .carry_injection import build_carry_context
    from .run_materialize import referenced_services

    definition = definition_from_payload(scenario_payload)
    steps = definition.get("steps") or []
    # 内置凭证基座(v2.10 §11.1):执行链不再消费 —— 唯一读者是导出
    # 物化面(10-14 口径,属主自有数据可携带);此处仍随 prep 产出。
    # UPC M2:区判定 = 私有空间 kind 轴,经 db_factory 短会话
    async with db_factory() as _s:
        _proj_kind = await project_kind_of(_s, project_id)
    prep = ExecPrep(
        built_in_users=built_in_users(
            scenario_payload, executor_id=owner_id,
            scenario_owner_id=scenario_owner_id,
            project_kind=_proj_kind))

    # 分层②:显式选定配置的绑定 → {声明条目: 池取用条目}(换池内
    # 命中哪条;注入标签不变)。解析失败不阻塞(缺条目由既有 fail-fast
    # 判定给出可读错误,覆盖层只是增强)。
    slot_map: dict[str, str] = {}
    if slot_overrides:
        try:
            async with db_factory() as s:
                slot_map = await service_aliases.slot_lookup_overrides(
                    s, steps, bindings, slot_overrides)
        except Exception:  # noqa: BLE001
            logger.opt(exception=True).warning(
                "run_prepare: exec-config slot overrides lookup failed")
            slot_map = {}

    # ①② 凭证清单 + 解析(owner 级短会话);清单扫描源含 config.setup/
    # teardown(webhook v4 §3.2 —— setup 引用的凭证同时进清单与注入)
    if with_auth:
        async with db_factory() as s:
            prep.aliases = await service_aliases.exec_auth_aliases_of_definition(
                s, definition, bindings)
        # §8.3:取用不校验标签 —— 环境位只驱动地址 ③,不进凭证解析
        prep.resolved_auths = await resolve_exec_auths(
            db_factory, owner_id, prep.aliases,
            cred_project_id=cred_project_id, slot_map=slot_map or None)
        got = {a.alias for a in prep.resolved_auths}
        prep.missing_aliases = sorted(set(prep.aliases) - got)
        if prep.missing_aliases and auth_policy == "strict":
            raise MissingAuthAliases(prep.missing_aliases)

    # ③ 别名地址(③层数据源;失败降级空表,绝不阻塞)
    try:
        async with db_factory() as s:
            prep.alias_base_urls = await service_aliases.base_urls_for(
                s, referenced_services(steps), env=environment)
    except Exception:  # noqa: BLE001
        logger.opt(exception=True).warning(
            "run_prepare: alias base_url lookup failed; skipped")
        prep.alias_base_urls = {}

    # ④ 修订解析(台账输入 endpoints_used/unanchored_services 一并产出)
    prep.meta_plate = (definition.get("meta") or {}).get("plate") or {}
    if resolve_mode == "single":
        for step in steps:
            if not isinstance(step, dict):
                continue
            ep_id = step.get("endpoint")
            if ep_id:
                system = str(ep_id).split(".")[0]
                prep.endpoints_used.setdefault(system, set()).add(str(ep_id))
            else:
                call = step.get("call")
                svc = call.get("service") if isinstance(call, dict) else None
                if isinstance(svc, str) and svc:
                    prep.unanchored_services.append(svc)
        if prep.meta_plate and any(   # b2-3/b2-4:追溯类 = PIN ∪ INTEGRATION
                record_category(v) in (PIN, INTEGRATION)
                for v in prep.meta_plate.values()):
            try:
                resolve_result = await plate_client.resolve(
                    prep.meta_plate,
                    {sys_: sorted(ids)
                     for sys_, ids in prep.endpoints_used.items()})
            except plate_client.PlateRejectedError as exc:
                # plate 的 4xx 是对**声明**的裁决(修订不存在/
                # 线不存在等)—— 归 plate_rejected,不冒充 plate_unavailable
                # 把运维引去查一个并不存在的目录故障。
                raise RuntimeError(
                    f'plate_rejected: 生效修订解析被拒: {exc}') from exc
            except Exception as exc:  # noqa: BLE001 — plate 不可用时执行失败
                raise RuntimeError(
                    f'plate_unavailable: 生效修订解析失败: {exc}') from exc
            # b2-4/b2.5(归一 v1.0 §1.5):回写分流抽为 run_semantics
            # .merge_resolve_effective(可测;PIN 写副本/INTEGRATION 只写 pins)
            from . import run_semantics as _rs
            _rs.merge_resolve_effective(
                prep.meta_plate, prep.plate_pins, resolve_result)

    # ⑤ carry(独立短会话;故障降级 None)
    if skip_carry:
        # 入站参数设计(决策 3):raw 保留字虚拟裸方案 → carry
        # 关闭。materialize 的 None 分支既有(异常降级同款),零新机制。
        prep.carry_ctx = None
    else:
        try:
            async with db_factory() as s:
                # §11.4:carry 层序 = 公共项目层 < 当前项目层 < 选定执行
                # 配置覆盖(exec_overrides;个人层已退役 —— §11.2 个人
                # 默认仅 UI 预选,后端不解析)。
                # §8.9 实例档:执行标签 env(与地址③同一 EnvChoice;
                # env_id=None = 标签链全空 → 实例档跳过)
                prep.carry_ctx = await build_carry_context(
                    s, definition, ui_field_states=ui_field_states,
                    project_id=project_id,
                    user_id=(owner_id if project_id is None else None),
                    bindings=bindings,
                    exec_overrides=exec_carry_overrides,
                    exec_removals=exec_carry_removals,
                    env_id=(getattr(environment, "env_id", None)
                            if environment is not None else None))
        except Exception:  # noqa: BLE001 — carry 绝不阻塞执行
            logger.opt(exception=True).warning(
                "run_prepare: carry context build failed; skipped")
            prep.carry_ctx = None
    return prep


# ── S5:统一解析入口(只读,生效预览面)──────────────────────────────
@dataclass(frozen=True)
class EffectiveConfig:
    """一次执行的**将生效**配置(逐值带来源;不含任何明文凭证)。

    与执行链复用同一份子构建器(注入清单/取用绑定/地址③;carry 键序
    同走 ``carry_injection.merge_carry_tiers`` 单源函数)—— 预览与
    执行结构上不可能漂移。"""
    env: dict | None                       # {environmentId, environmentSource}
    services: dict[str, dict]              # svc → {url, source, alias?}
    auths: dict[str, dict]                 # 槽名 → {bindingId, system, envId, isDefault, source}
    missing_auths: list[str]
    carry: dict[str, dict[str, dict]]      # raw svc → path → {value, source}
    carry_defaults: dict[str, dict]        # path → {value, source}


async def resolve_effective_config(
    db: Any, definition: dict, *,
    bindings: dict[str, dict] | None = None,
    user_id: int | None = None,
    project_id: int | None = None,
    environment: Any = None,
    cred_project_id: int | None = None,
    slot_map: dict[str, str] | None = None,
    exec_carry_overrides: dict[str, dict[str, str | None]] | None = None,
    exec_carry_removals: "dict[str, list[str]] | None" = None,
) -> EffectiveConfig:
    """组合环境/地址/条目装载/carry(预览与执行同源;见类注释)。

    S8:``cred_project_id`` 非空 = 本次选用项目凭证 —— 条目从项目池取用,
    逐槽来源 ``source='project'``(缺省 ``'personal'``)。

    分层②:``slot_map``({声明条目: 池取用条目},执行配置绑定)与
    ``exec_carry_overrides``({目录服务: {字段: 值}},区规则已由调用方
    裁)—— 预览逐值带来源:被覆盖条目标 ``slotSource='exec_config'``,
    carry 覆盖值标 ``source='exec_config'``(§5 守则「自证每个值的来路」)。"""
    from . import carry_store, service_aliases
    from .carry_injection import _step_service, merge_carry_tiers
    from .env_chain import EnvChoice
    from .run_materialize import (referenced_services,
                                  resolve_service_sources)

    steps = definition.get("steps") or []
    env = environment if isinstance(environment, EnvChoice) else None

    # 地址:③ 环境部署表(架构终态:② authored 退役,全区域一态)
    svcs = referenced_services(steps)
    full = await service_aliases.base_urls_for(db, svcs, env=env)
    sources = resolve_service_sources(steps, alias_base_urls=full)
    services_out: dict[str, dict] = {}
    for svc, info in sources.items():
        out = dict(info)
        if info.get("source") == "alias":
            out["source"] = "deployment"
        services_out[svc] = out

    # 条目装载:注入清单 + 取用(单源 pick_bindings);分层②:取用按
    # 覆盖条目,展示键 = 声明条目(与执行注入标签同形)
    injection = await service_aliases.exec_auth_aliases_of_definition(
        db, definition, bindings or {})
    lookup = slot_map or {}
    auths_out: dict[str, dict] = {}
    missing: list[str] = []
    if injection and (user_id is not None or cred_project_id is not None):
        rows = await pick_bindings(
            db, user_id, list(dict.fromkeys(
                lookup.get(a, a) for a in injection if lookup.get(a, a))),
            cred_project_id=cred_project_id)
        by_slot = {r.slot: r for r in rows}
        src = "project" if cred_project_id is not None else "personal"
        for label in dict.fromkeys(injection):
            r = by_slot.get(lookup.get(label, label))
            if r is None:
                continue
            auths_out[label] = {
                "bindingId": r.account_id, "system": r.system,
                "envId": r.env_id, "isDefault": r.is_default,
                "source": src,
                **({"slotSource": "exec_config",
                    "configuredSlot": lookup[label]}
                   if label in lookup else {})}
        missing = sorted(
            a for a in set(injection)
            if lookup.get(a, a) not in by_slot)
    elif injection:
        missing = sorted(injection)

    # carry:tier 序逐层归并,逐 path 标注来源(作用域:键层级);
    # 分层②:执行配置覆盖层压在层序之上(场景显式在 carry_face 已先行);
    # 分层:个人层已收编为默认执行配置,user_id 不构成 tier。
    # §8.9 实例档:键序 条目 > 实例(system, 执行标签 env) > 服务 >
    # 层默认 —— 与执行链**同一函数**(carry_injection.merge_carry_tiers,
    # 单源不漂移);来源标注:`...:instance:{envId}` / `exec_config`
    from sqlalchemy import select as sa_select

    from ..models.service import Service as DBService
    from .service_names import resolve_base_with_aliases
    tiers: list[tuple[str, int]] = [await carry_store.public_scope(db)]
    if project_id is not None:
        tiers.append(("project", project_id))
    raw_svcs: list[str] = []
    for st in steps:
        svc = _step_service(st) if isinstance(st, dict) else None
        if isinstance(svc, str) and svc:
            raw_svcs.append(svc)
    carry_out: dict[str, dict[str, dict]] = {}
    base_of: dict[str, str | None] = {
        raw: await resolve_base_with_aliases(db, raw)
        for raw in dict.fromkeys(raw_svcs)}
    system_of: dict[str, str] = {}
    bases_known = {b for b in base_of.values() if b}
    if bases_known:
        system_of = dict((await db.execute(
            sa_select(DBService.name, DBService.system).where(
                DBService.name.in_(bases_known)))).all())
    carry_env = env.env_id if env is not None else None
    for raw, base in base_of.items():
        if base is None:
            continue
        carry_out[raw] = await merge_carry_tiers(
            db, tiers, base=base,
            alias_key=service_aliases.effective_alias(raw, bindings),
            instance_key=system_of.get(base) or None,
            env_id=carry_env,
            exec_overrides=(exec_carry_overrides or {}).get(base),
            exec_removals=(exec_carry_removals or {}).get(base))
    defaults_out: dict[str, dict] = {}
    for t in tiers:
        t_rows = await carry_store.get_defaults(db, t)
        for path, value in t_rows.items():
            defaults_out[path] = {"value": value,
                                  "source": f"{t[0]}:{t[1]}"}

    return EffectiveConfig(
        env=(env.snapshot() if env and env.env_id is not None else None),
        services=services_out, auths=auths_out, missing_auths=missing,
        carry=carry_out, carry_defaults=defaults_out)


async def graph_auth_aliases(
    db_factory: Any, units: list[tuple[dict, dict]],
) -> list[str]:
    """Suite 编排的凭证清单:**逐单元**走 ``exec_auth_aliases``(模板
    扫描 ∪ 步骤服务条目 —— 每单元用它自己合并后的绑定),再对
    结果取并集(去重保序)。

    N1-2 整改:此前 materialize_graph 只收 graph_req 单元级显式
    ``serviceBindings.authAlias``(方案级绑定不进清单、无模板扫描、
    无别名默认)—— 与单场景链/预检(预检看得到方案级)口径漂移。

    逐单元而非按服务压平(评审 2026-11-01 §2 回归):两个单元给同一
    服务绑不同别名(qa1/qa2)时,``{服务: 别名}`` 压平会后写覆盖先写
    丢凭证;``credential_alias_hits`` 的「显式绑定排除默认」也会因压平
    键全局生效 —— 单元 A 显式绑定的服务,单元 B 的别名默认被误排除。

    ``units``:每单元 ``(definition, merged_bindings)``;绑定合并与
    materialize_run_copy 同一份(见 graph_dispatch.unit_merged_bindings)。
    """
    aliases: dict[str, None] = {}
    async with db_factory() as s:
        for definition, bindings in units:
            steps = (definition or {}).get("steps") or []
            for a in await service_aliases.exec_auth_aliases(
                    s, steps, bindings or {},
                    extra_scan_nodes=service_aliases.setup_teardown_nodes(
                        definition or {})):
                aliases.setdefault(a, None)
    return list(aliases)


async def unit_carry_contexts(
    db_factory: Any, composed_units: list[dict],
    unit_metas: "list[dict] | None" = None,
) -> list[Any]:
    """Suite 编排的 carry:**按单元**构建(carry 上下文按步骤下标
    索引,不能跨单元共用 —— 全图共用一份会把单元 A 的步骤面错配到
    单元 B)。单单元失败降 None,不阻塞其它单元(N1-2)。

    ``unit_metas``(S4):与 composed_units 同序的作用域上下文
    ({project_id, user_id, bindings};缺省 = 无第二层,只吃公共项目层)。
    §8.9 实例档:``env_id`` 键 = 该单元解析出的执行标签(env_mixed 已在
    派发前拦,单元级恒单值;缺省/None → 实例档跳过)。
    Suite 单元规格今日无 fieldStates 面(ui.fieldStates 是单场景执行链
    的 payload 面);后续编排单元带面时在此透传。
    """
    from .carry_injection import build_carry_context

    metas = unit_metas or [{} for _ in composed_units]

    async def _one(d: dict, meta: dict) -> Any:
        try:
            async with db_factory() as s:
                return await build_carry_context(
                    s, d, ui_field_states=None,
                    project_id=meta.get("project_id"),
                    user_id=meta.get("user_id"),
                    bindings=meta.get("bindings"),
                    env_id=meta.get("env_id"))
        except Exception:  # noqa: BLE001 — 单单元降级,不阻塞全图
            logger.opt(exception=True).warning(
                "run_prepare: unit carry build failed; unit skips carry")
            return None

    import asyncio as _aio
    return list(await _aio.gather(
        *[_one(d, m) for d, m in zip(composed_units, metas)]))


# ─── P3 临时调用:请求 steps → 标准场景 payload(纯函数)───────────

ADHOC_SCENARIO_PREFIX = "adhoc"


def adhoc_placeholder_id(run_id: str) -> str:
    """临时调用执行行的占位 scenario_id(models.execution 非场景形态
    ``<形态前缀>-<id>`` 约定,与 ``suite-<id>`` 同款)。"""
    return f"{ADHOC_SCENARIO_PREFIX}-{run_id}"


def build_adhoc_payload(
    steps: list[dict], *, run_id: str, meta_plate: dict[str, str],
    credential_by_service: dict[str, str], name: str,
) -> dict:
    """临时调用请求 → 与库中场景同形的容器 payload(设计 2026-11-02 §五)。

    纯函数:输入已过 :mod:`adhoc_run` 的结构/别名/版本校验。产物进
    :func:`prepare_exec`(resolve_mode="single")→ convert → 物化,与单场景
    执行同一条装载链;快照即本产物。

    * ``method / path`` **不写入**:锚点步骤由 plate convert 按定义补全
      (Release 6.2 存储形态:call 只存 service / user / path_params);
    * ``config`` 留空:服务地址由装载链第③层别名 base_url 补、凭证由
      注入清单(别名默认层)落 ``config.users`` —— 请求体钉不了任何 URL;
    * ``call.user`` = 条目名 ``slot``(执行器编译期:
      ``call.auth≠none`` 的步骤必须带 call.user,且标签须在 config.users
      —— 别名默认层正好注入该标签);别名未配凭证则省略,接口若需认证由
      执行器步骤级报错(方案 §五);
    * definition 级 ``scenarioId`` 只为满足 plate/执行器形状(前缀 sc),
      执行行挂载的是 :func:`adhoc_placeholder_id`。
    """
    systems = sorted({str(st["endpoint"]).split(".")[0] for st in steps})
    out_steps: list[dict] = []
    for i, st in enumerate(steps):
        svc = str(st["service"])
        call: dict[str, Any] = {"service": svc}
        cred = credential_by_service.get(svc)
        if cred:
            call["user"] = cred
        if st.get("pathParams"):
            # plate 路径模板 {key} 占位的值(存储形态字段 call.path_params;
            # 执行器 call.py 缺键报 PATH_PARAM_MISSING)
            call["path_params"] = {str(k): v for k, v in st["pathParams"].items()}
        step: dict[str, Any] = {
            "kind": "step", "id": f"s{i + 1}",
            "endpoint": str(st["endpoint"]),
            "call": call,
            "request": {"kind": "request", "body": st.get("body", {})},
            "strategy": [dict(s) for s in (st.get("strategy") or [])],
        }
        out_steps.append(step)
    return {
        "definition": {
            "kind": "scenario",
            "scenarioId": f"sc-{adhoc_placeholder_id(run_id)}",
            "meta": {
                "name": name[:64],
                "module": "",
                "priority": 0,
                "system": systems,
                "plate": dict(meta_plate),
                "tags": ["adhoc"],
            },
            "config": {},
            "resource": {},
            "steps": out_steps,
        },
        "orchestration": {
            "steps": [{"enabled": True, "name": ""} for _ in out_steps],
            "resourceMeta": {},
        },
        "ui": {},
    }
