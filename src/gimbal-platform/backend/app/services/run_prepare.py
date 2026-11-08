"""services/run_prepare.py — 执行装载准备(N1 归一,2026-11-01 清单)。

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

整改背景:此前五份平行实现 —— graph 链凭证清单缺模板扫描与别名默认
两层(方案级 authAlias 甚至不进清单)、Suite 无 carry(显式 None 是
防崩权宜)、导出缺别名默认层、预检地址链漏第③层。归一后差异只允许
以参数表达(auth_policy / resolve_mode),凭证清单算法、地址链、
carry 不允许任何调用方自选。评审(2026-11-01 §3.1A)收口:集成与
导出亦改调 prepare_exec,不再各自手写编排(只调子函数的「半归一」
留有编排顺序/降级口径各自漂移的口子)。

迁入符号自 run_dispatcher(原 _compose_scenario/_resolve_exec_auths/
_built_in_users/_find_dataset_by_id/_AuthResolveError):已有四个跨模块
消费方 + 一处因私有名可达性写错的导入路径(suites.py from .
run_dispatcher → ModuleNotFoundError)—— 分层错位已造成真实 bug,
故搬迁而非原地公开。

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

from ..models.auth_session import AuthSession as DBAuthSession
from ..models.composer_data_set import ComposerDataSet
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


# 物理迁移自 gimbal 后:用平台侧标准 AuthSession 替代自创 ResolvedAuth dataclass。
# 下游 materialize_run_copy(_apply_users)仍消费 username/password/url/token_type/
# expires_in 这几个字段,与标准 AuthSession 完全对齐(后者字段更多但不影响注入
# 逻辑)。保留 ResolvedAuth 作为兼容 shim,免改下游的字段引用。
@dataclass(frozen=True, slots=True)
class ResolvedAuth:
    """解密后的执行认证(轻量值对象,保留兼容 shim)。

    明文凭证只存在于该对象的生命周期内,不落在 AuthSession ORM 行
    上 — 避免任何意外 commit 把明文写回数据库。

    内部委托给标准 RuntimeAuthSession(物理迁移自 gimbal),字段对齐下游消费者。
    """

    alias: str
    url: str
    username: str
    password: str
    token_type: str
    expires_in: int
    # S4:槽位账号级字段(${slot.X.field} 派发前替换的数据源)
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


def _slot_tier(row: DBAuthSession, env_id: int | None) -> tuple:
    """槽位绑定取用分层(S3):环境命中 > env 空且默认 > env 空 >
    默认 > 首行(id 序)。存量行(每槽恰一行、env 空、默认)恒取
    tier 1 —— 与旧按名解析逐行相同。"""
    if env_id is not None and row.env_id == env_id:
        tier = 0
    elif row.env_id is None:
        tier = 1 if row.is_default else 2
    elif row.is_default:
        tier = 3
    else:
        tier = 4
    return (tier, row.id)


async def pick_bindings(
    db: Any, owner_id: int, slots: list[str],
    *, env_id: int | None = None,
) -> list["DBAuthSession"]:
    """S5 槽位取用单源(不解密):同槽多绑定按 :func:`_slot_tier` 分层
    取一行。``resolve_exec_auths``(注入)与指纹/预览的绑定标识消费同一
    份裁决 —— 取用口径结构上不可能漂移。"""
    if not slots:
        return []
    rows = (await db.execute(
        select(DBAuthSession).where(
            DBAuthSession.owner_id == owner_id,
            DBAuthSession.slot.in_(slots)))).scalars().all()
    picked: dict[str, DBAuthSession] = {}
    for a in rows:
        cur = picked.get(a.slot)
        if cur is None or _slot_tier(a, env_id) < _slot_tier(cur, env_id):
            picked[a.slot] = a
    return sorted(picked.values(), key=lambda r: r.slot)


async def binding_ids_for(
    db_factory: Any, owner_id: int, slots: list[str],
    *, env_id: int | None = None,
) -> dict[str, int]:
    """槽名 → 取用绑定 id(轻量,不解密;指纹/预览消费)。"""
    if not slots:
        return {}
    async with db_factory() as s:
        rows = await pick_bindings(s, owner_id, slots, env_id=env_id)
    return {r.slot: r.id for r in rows}


async def resolve_exec_auths(
    db_factory: Any, owner_id: int, aliases: list[str],
    *, env_id: int | None = None,
) -> list[ResolvedAuth]:
    """Owner 级槽名 → ResolvedAuth(解密后的轻量值对象)。owner 过滤
    防跨 owner 同名 slot 解错凭证。

    S3 槽位绑定:按 ``slot`` 解析(注入键/模板名);同槽多绑定时按
    :func:`_slot_tier` 分层取一行(``env_id`` = 本次执行环境,S2.1)。
    存量行 slot=alias 恒一对一 → 行为与旧链逐行相同。

    * 解密失败 → 抛 :class:`AuthResolveError`(V1 严格语义:
      凭证路径 fail-fast,不静默降级)。
    * alias 不属于该 owner 时解不到 → 告警后继续(与 V1 一致:
      缺 alias 只是注入不到 users,该行 run 在 Gimbal 解析
      ``${auth.*}`` 时步骤级报错)。
    * 明文只存在于返回的值对象上 — 绝不写回 ORM 行(此前
      ``a.username = ...`` 会把明文挂到 session 里的 AuthSession
      实例上,任何一次意外 commit 都会把明文持久化进库)。

    **只收会话工厂**(N1-6):内部开独立短会话做快照读,与调用方的
    长事务隔离 —— 传活会话是 N0 修掉的缺陷形态(AsyncSession 不可
    调用,别名非空即 TypeError)。

    Phase 3 改造:内部先用平台侧标准 RuntimeAuthSession(物理迁移自 gimbal)
    接收解密后的字段,然后通过 ``ResolvedAuth.from_runtime`` 转为兼容 shim。
    这样下游 materialize_run_copy(_apply_users)不动,未来可直接消费
    ``RuntimeAuthSession``。
    """
    if not aliases:
        return []
    from ..core.security import fernet_decrypt

    resolved: list[ResolvedAuth] = []
    async with db_factory() as session:
        # S5:取用裁决单源(pick_bindings;同槽多绑定分层取一行)
        rows = await pick_bindings(session, owner_id, aliases,
                                   env_id=env_id)
    for a in rows:
        try:
            runtime = RuntimeAuthSession(
                url=a.url,
                username=fernet_decrypt(a.username_enc),
                password=fernet_decrypt(a.password_enc),
                token_type=a.token_type,
                expires_in=a.expires_in,
            )
            # frozen dataclass:用 replace 补绑定标识(S5)
            resolved.append(dataclasses.replace(
                ResolvedAuth.from_runtime(
                    runtime, alias=a.slot, account_fields=a.account_fields),
                binding_id=a.id))
        except ValueError as e:
            raise AuthResolveError(
                f"auth slot '{a.slot}' decrypt failed: {e}"
            ) from e
    missing = set(aliases) - {a.alias for a in resolved}
    if missing:
        logger.warning(
            "run_prepare: exec auth aliases not found: {}", sorted(missing)
        )
    return resolved


def built_in_user_aliases(scenario_payload: dict | None) -> list[str]:
    """场景内置认证的别名清单(只给名字,不给凭证)—— 展示 / 预检告警
    用(§7.1 内置认证清单、builtin_auth_shadowed)。"""
    def_cfg = definition_from_payload(scenario_payload).get("config") or {}
    users = def_cfg.get("users") if isinstance(def_cfg.get("users"), dict) else {}
    return sorted(str(k) for k in (users or {}))


def zone_allows_direct(project_id: int | None) -> bool:
    """原 5(authz M2a S6):场景内的直连地址(``config.services``)与内置
    凭证(``config.users``)只在**私有区**生效;项目区 / 公共区(场景
    ``project_id`` 非空)一律不生效 —— 地址只来自环境部署表,凭证只来自
    执行人的槽位绑定。执行 / 导出 / 预检 / 生效预览 / 令牌范围同口径。"""
    return project_id is None


def built_in_users(
    scenario_payload: dict | None, *,
    executor_id: int | None,
    scenario_owner_id: int | None,
    project_id: int | None,
) -> dict[str, Any]:
    """场景 definition.config.users —— 仅当执行人 == 场景属主、且场景在
    私有区时返回。

    authz W6 主规则(评审 R3):其余(share_ref 引用执行 / 订阅执行 /
    非属主导出 / suite 跑他人成员)一律当空。**fail-closed**:两参必填,
    任一为 None(属主已删的孤儿场景、调用方漏传)同样当空 —— 此前 None
    = 不判直接放行。作者即席提供 payload 的路径(草稿预览、临时调用)
    由调用方显式传 ``scenario_owner_id = executor_id``。只要名字的展示面
    用 :func:`built_in_user_aliases`。

    ``project_id``(必填,原 5):项目 / 公共区场景当空(属主本人执行
    同样当空 —— 区规则不看人)。
    """
    if not zone_allows_direct(project_id):
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
    (旧链路"int 还是 int"的语义)。规则:

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
    * M2 步骤 4(Q18):定义即纯 M2,Meta 只 name 必填(M6),不再补
      plate 默认值 —— fill_plate_defaults 已删除。
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
    # 原 5:场景直连地址(authored)是否生效 —— 私有区 True,项目/公共区 False
    direct_addresses: bool = True
    meta_plate: dict[str, str] = field(default_factory=dict)  # 生效修订(已写回 definition)
    plate_pins: dict[str, str] = field(default_factory=dict)
    # 台账输入(resolve_mode="single" 时随修订解析一并产出,供执行侧
    # A-3/W7 入库标准判定与 pins 落库 —— 不属装载,但同源免二次遍历):
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
) -> ExecPrep:
    """准备段统一入口(每次执行一次;逐 case 段保持
    compose → convert → materialize_run_copy 不变)。

    * 凭证清单:``service_aliases.exec_auth_aliases``(模板扫描 ∪
      生效别名声明槽位)—— 算法单源,调用方不可自选;
    * 凭证解析:``resolve_exec_auths``(owner 级);``strict`` 下缺别名
      抛 :class:`MissingAuthAliases`(集成链捕获 → 暂停实例),
      ``lenient`` 仅记录(执行期步骤级报错);``with_auth=False``
      供调用方在更早处已用同一函数做过 fail-fast 解析(单场景链的
      认证先行序),跳过重复解密;
    * 别名地址:``base_urls_for``(③层数据源;查表失败降级空表);
      ``environment``(S2.1,``env_chain.EnvChoice``)= 派发时已解析的
      环境选择,并入部署表地址(缺省 = 旧 ③ 行为);
    * carry:``build_carry_context``(独立短会话;任何故障降级 None,
      carry 是增强不是前置条件);
    * 修订解析 ``resolve_mode``:
      ``single`` = plate resolve + merge_resolve_effective(PIN 写执行
      副本 / INTEGRATION 只写 pins;plate 拒绝/不可用原样上抛
      plate_rejected/plate_unavailable);
      ``none`` = 原样透传(集成/导出链,见模块 docstring 的定案理由)。

    **副作用**(评审 §3.1 附注):``resolve_mode="single"`` 时**原地
    修订**入参 payload 的 ``definition.meta.plate``(merge_resolve_
    effective 的生效修订回写 —— compose/convert 的输入依赖该回写才能
    拿到生效修订;`_fanout` 在调用前 deepcopy 正是为了承接它)。调用
    方若不希望写穿存储/草稿对象,须自备副本;其余模式不改入参。
    """
    from .carry_injection import build_carry_context
    from .run_materialize import referenced_services

    definition = definition_from_payload(scenario_payload)
    steps = definition.get("steps") or []
    # authz W6 主规则:executor(owner_id = 凭证池归属,即执行人)≠
    # 场景属主 ⇒ 内置 users 基座当空(R3)
    prep = ExecPrep(
        built_in_users=built_in_users(
            scenario_payload, executor_id=owner_id,
            scenario_owner_id=scenario_owner_id, project_id=project_id),
        direct_addresses=zone_allows_direct(project_id))

    # ①② 凭证清单 + 解析(owner 级短会话);清单扫描源含 config.setup/
    # teardown(webhook v4 §3.2 —— setup 引用的凭证同时进清单与注入)
    if with_auth:
        async with db_factory() as s:
            prep.aliases = await service_aliases.exec_auth_aliases_of_definition(
                s, definition, bindings)
        prep.resolved_auths = await resolve_exec_auths(
            db_factory, owner_id, prep.aliases,
            env_id=getattr(environment, "env_id", None))
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
                # ⑥(2026-10-13):plate 的 4xx 是对**声明**的裁决(修订不存在/
                # 线不存在等)—— 归 plate_rejected,不再冒充 plate_unavailable
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
    try:
        async with db_factory() as s:
            # S4:carry 作用域 = 公共项目层 < (项目层 ∨ 执行人个人层;
            # 项目区不吃个人层 —— 区模型收敛裁定)
            prep.carry_ctx = await build_carry_context(
                s, definition, ui_field_states=ui_field_states,
                project_id=project_id,
                user_id=(owner_id if project_id is None else None),
                bindings=bindings)
    except Exception:  # noqa: BLE001 — carry 绝不阻塞执行
        logger.opt(exception=True).warning(
            "run_prepare: carry context build failed; skipped")
        prep.carry_ctx = None
    return prep


# ── S5:统一解析入口(只读,生效预览面)──────────────────────────────
@dataclass(frozen=True)
class EffectiveConfig:
    """一次执行的**将生效**配置(逐值带来源;不含任何明文凭证)。

    与执行链复用同一份子构建器(注入清单/取用绑定/地址③/carry tier)
    —— 预览与执行结构上不可能漂移。"""
    env: dict | None                       # {environmentId, environmentSource}
    services: dict[str, dict]              # svc → {url, source, alias?}
    auths: dict[str, dict]                 # 槽名 → {bindingId, system, envId, isDefault}
    missing_auths: list[str]
    carry: dict[str, dict[str, dict]]      # raw svc → path → {value, source}
    carry_defaults: dict[str, dict]        # path → {value, source}


async def resolve_effective_config(
    db: Any, definition: dict, *,
    bindings: dict[str, dict] | None = None,
    user_id: int | None = None,
    project_id: int | None = None,
    environment: Any = None,
) -> EffectiveConfig:
    """组合环境/地址/槽位绑定/carry(预览与执行同源;见类注释)。"""
    from . import carry_store, service_aliases
    from .carry_injection import _step_service
    from .env_chain import EnvChoice
    from .run_materialize import (referenced_services,
                                  resolve_service_sources)

    steps = definition.get("steps") or []
    declared = (definition.get("config") or {}).get("services")
    declared = declared if isinstance(declared, dict) else {}
    if not zone_allows_direct(project_id):
        declared = {}        # 原 5:项目/公共区不吃直连地址
    env = environment if isinstance(environment, EnvChoice) else None

    # 地址:② authored(私有区)> ③ 环境部署表(S6 起唯一 ③ 来源)
    svcs = referenced_services(steps)
    full = await service_aliases.base_urls_for(db, svcs, env=env)
    sources = resolve_service_sources(
        steps, declared=declared, alias_base_urls=full)
    services_out: dict[str, dict] = {}
    for svc, info in sources.items():
        out = dict(info)
        if info.get("source") == "alias":
            out["source"] = "deployment"
        services_out[svc] = out

    # 槽位绑定:注入清单 + 取用(单源 pick_bindings)
    injection = await service_aliases.exec_auth_aliases_of_definition(
        db, definition, bindings or {})
    auths_out: dict[str, dict] = {}
    missing: list[str] = []
    if injection and user_id is not None:
        rows = await pick_bindings(
            db, user_id, injection,
            env_id=getattr(env, "env_id", None))
        got = {r.slot for r in rows}
        for r in rows:
            auths_out[r.slot] = {
                "bindingId": r.id, "system": r.system,
                "envId": r.env_id, "isDefault": r.is_default}
        missing = sorted(set(injection) - got)
    elif injection:
        missing = sorted(injection)

    # carry:tier 序逐层归并,逐 path 标注来源(作用域:键层级)
    from .service_names import resolve_base_with_aliases
    tiers: list[tuple[str, int]] = [await carry_store.public_scope(db)]
    if project_id is not None:
        tiers.append(("project", project_id))
    elif user_id is not None:
        tiers.append(("user", user_id))
    raw_svcs: list[str] = []
    for st in steps:
        svc = _step_service(st) if isinstance(st, dict) else None
        if isinstance(svc, str) and svc:
            raw_svcs.append(svc)
    carry_out: dict[str, dict[str, dict]] = {}
    for raw in dict.fromkeys(raw_svcs):
        base = await resolve_base_with_aliases(db, raw)
        if base is None:
            continue
        alias_key = service_aliases.effective_alias(raw, bindings)
        merged: dict[str, dict] = {}
        for t in tiers:
            t_base = await carry_store.get_bindings(db, base, t)
            t_alias = (await carry_store.get_bindings(db, alias_key, t)
                       if base != alias_key else {})
            for path in set(t_base) | set(t_alias):
                if path in t_alias:
                    merged[path] = {"value": t_alias[path],
                                    "source": f"{t[0]}:{t[1]}:alias"}
                else:
                    merged[path] = {"value": t_base[path],
                                    "source": f"{t[0]}:{t[1]}:base"}
        carry_out[raw] = merged
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
    扫描 ∪ 生效别名声明槽位 —— 每单元用它自己合并后的绑定),再对
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
    ({project_id, user_id};;缺省 = 无第二层,只吃公共项目层)。
    Suite 单元规格今日无 fieldStates 面(ui.fieldStates 是单场景
    执行链的 payload 面);后续编排单元带面时在此透传。
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
                    bindings=meta.get("bindings"))
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
    * ``call.user`` = 别名声明槽位 ``slot``(执行器编译期:
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
