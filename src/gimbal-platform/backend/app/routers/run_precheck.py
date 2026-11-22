"""POST /api/run/precheck — 执行器批量预检(执行设计 §1.6)。

入参是 ``{scenarioId, schemeId}`` **对**的列表 — 要检的本来就不是用例,
是"这条用例配上这个方案能不能跑"。每条返回::

    {scenarioId, schemeId, found, schemeValid,
     deadDatasetIds, danglingEntryIds, unboundServices}

两个收益(设计 §1.6):失效判定有**服务端唯一实现**(前端不用再抄一份;
悬空判定复用 run_dispatcher.filter_injection_entries — 与 dispatch 跳过
逻辑同一份代码),以及队列 N 条不必各装配一次(每条装配是 4 个并行请求
+ 凭证池)。方案引用的数据集被删的正确说法是「这个方案跑不了,换一个
方案就能跑」— 判定绑定在「用例 × 方案」上,不是用例状态(§1.4)。

读侧口径:场景按 ``can_read_scenario_row`` 收紧(authz W6 起含引用 ——
被分享人本就可跑;不可读 = ``found:false``,不泄露存在性);预检不产生
任何执行副作用。
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import principal_or_user
from ._ownership import can_read_scenario_row
from ..models import ComposerDataSet
from ..models.composer_scenario import ComposerScenario
from ..services import run_dispatcher, scenario_store, scheme_store
from ..services.access_token import Principal
from ..services.run_dispatcher import definition_from_payload
from ..services.run_materialize import referenced_services

router = APIRouter(prefix="/run", tags=["runs"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
PrincipalIn = Annotated[Principal, Depends(principal_or_user)]

_MAX_BATCH = 20

# ── M3 预检硬门(redesign §8.5,2026-11-17)────────────────────────
# 三条派发路径(UI/JWT、access token、webhook 定时)统一硬拦截:把
# 「告警不拦截」的缺项升级为派发前 409,错误时机从引擎步骤级报错前移。
# 判定与 ``_precheck_one`` 共享一套分类私有函数(本文件);唯一实现,
# 遵守 run_dispatcher「不开第二份」原则。

GATE_ENV_UNSPECIFIED = "env_unspecified"      # 标签不可解析(链全空)
GATE_ENV_MIXED = "env_mixed"                  # 多身份标签不一致(混拼)
GATE_ADDRESS_MISSING = "address_missing"      # 服务地址 ②③ 层双缺
GATE_LOGIN_MISSING = "login_missing"          # 账户可解但实例登录口缺
GATE_IDENTITY_MISSING = "identity_missing"    # 身份条目未登记/悬空
GATE_ACCOUNT_MISSING = "account_missing"      # 条目在、凭证池无账户
GATE_ACCOUNT_AMBIGUOUS = "account_ambiguous"  # 多候选账户无同标签唯一命中
# 决策 1 圈定即承诺(阶段 1):生效执行配置的圈定集非空 = 白名单生效,
# 换用后取用集 ⊄ 圈定集 → 硬拦(派发 409 / 定时 precheck_config 暂停)。
GATE_IDENTITY_NOT_CIRCLED = "identity_not_circled"

#: 凭证域码(定时路径暂停沿用 missing_credential —— 复活钩子自动恢复)
_GATE_CREDENTIAL_CODES = frozenset({
    GATE_IDENTITY_MISSING, GATE_ACCOUNT_MISSING,
    GATE_LOGIN_MISSING, GATE_ACCOUNT_AMBIGUOUS})


class PrecheckGateError(Exception):
    """硬门不通过(M3 §8.5)—— 派发路径映射 409 ``{code, message,
    ...detail}``;webhook 定时路径映射实例暂停(凭证域 missing_credential,
    其余 precheck_config)。detail 必带 标签名/服务/系统/身份 上下文。"""

    def __init__(self, code: str, message: str,
                 detail: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail or {}


class PrecheckItem(BaseModel):
    """「这条用例 × 这个方案」预检入参(执行设计 §1.6)。"""

    model_config = ConfigDict(populate_by_name=True)

    scenario_id: str = Field(alias="scenarioId", min_length=3, max_length=128)
    scheme_id: str = Field(alias="schemeId", min_length=1, max_length=128)
    # §8.5:按该执行配置的口径预检(换用 slot_map 折进有效身份集合,
    # 与派发同一折叠);缺省 None = 不按执行配置口径。不可加载 = 忽略
    #(执行配置自身的可用性在它的页面暴露,这里不连坐)。
    exec_config_id: "int | None" = Field(default=None, alias="execConfigId", ge=1)


class PrecheckResult(BaseModel):
    """单条预检结论。字段全部是「这条方案配置」的事实,不是用例状态。"""

    model_config = ConfigDict(populate_by_name=True)

    scenario_id: str = Field(alias="scenarioId")
    scheme_id: str = Field(alias="schemeId")
    # false = 场景不可读 / 不存在。此时其余字段无意义(不泄露存在性)。
    found: bool = True
    # 方案本体存在(方案被删 → 不可跑,前端提示去工作台重建)
    scheme_found: bool = Field(default=True, alias="schemeFound")
    # 以上任一不成立即 False — 「这个方案跑不了,换一个方案就能跑」
    scheme_valid: bool = Field(default=True, alias="schemeValid")
    # 方案引用但已删的数据集(换方案可解)
    dead_dataset_ids: list[str] = Field(default_factory=list, alias="deadDatasetIds")
    # dispatch 侧同口径判死的注入条目 id(执行时会被跳过)
    dangling_entry_ids: list[str] = Field(default_factory=list, alias="danglingEntryIds")
    # steps 引用了、但声明 URL 与绑定 URL 双缺的 service(引擎会显式报错)
    unbound_services: list[str] = Field(default_factory=list, alias="unboundServices")
    # webhook v4 §5.3:令牌范围缺项(按 §3.3 分类:未授权 / 已删除);
    # 令牌路径自动以当前令牌预检,JWT 可传 tokenId 预检自己可管理的令牌
    scope_missing: list[dict] = Field(default_factory=list, alias="scopeMissing")
    # S8 收口:身份条目在执行人**个人池**未装载(与派发 fail-fast 同源
    # pick_bindings 取用差集;空 = 全部可取用)。歧义单列(复核收口
    # 2026-11-22:同引用多候选无同标签唯一命中,执行将 409
    # account_ambiguous —— 混标「缺失」误导排障)
    missing_auths: list[str] = Field(default_factory=list, alias="missingAuths")
    ambiguous_auths: list[str] = Field(default_factory=list, alias="ambiguousAuths")
    # 项目凭证池的缺槽清单(None = 不适用:场景不属普通项目 / 执行人非
    # 成员;非空时前端提示可切「项目凭证」或去补登记)
    project_missing_auths: "list[str] | None" = Field(
        default=None, alias="projectMissingAuths")
    project_ambiguous_auths: "list[str] | None" = Field(
        default=None, alias="projectAmbiguousAuths")
    # §1.4 env 必填收紧 → §8.5 语义改写:执行标签不可解析(条目标签 >
    # 项目默认 > 平台默认 均未命中)且场景用到身份条目 —— 条目无从解析,
    # missingAuths 全数罗列只是表象;单列信号点名根因(派发侧 409)
    env_unspecified: bool = Field(default=False, alias="envUnspecified")
    # §8.5 契约扩展(全部可选、旧字段兼容):
    # envContext = 本次标签 {environmentId, environmentSource}(链空 =
    # None);envMixed = 多身份标签不一致(混拼,派发 409);envWarnings =
    # 跨标签凭证提示(账户标签 ≠ 执行标签 —— 凭证解耦,不拦截,执行期
    # 401 自然暴露)
    env_context: "dict | None" = Field(default=None, alias="envContext")
    env_mixed: bool = Field(default=False, alias="envMixed")
    env_warnings: list[str] = Field(default_factory=list, alias="envWarnings")
    # §7.1 范围外目标(直连地址/内置认证/白名单外策略,只记录不拦截)
    out_of_scope_targets: list[dict] = Field(
        default_factory=list, alias="outOfScopeTargets")
    # authz W6 预检告警(N9/E2):内置凭证主规则生效后,被分享人经
    # 引用执行不再带走作者凭证 —— 三条件同时满足才列出(钉「不吵」):
    # ① 执行人 ≠ 场景属主;② 场景 config.users 非空;③ 这些用户
    # (别名)在执行人自己的认证会话里解析不到。值为解析不到的别名
    # 清单;空 = 无告警
    builtin_auth_shadowed: list[str] = Field(
        default_factory=list, alias="builtinAuthShadowed")
    # 决策 1 圈定即承诺(阶段 1):按 PrecheckItem.execConfigId 口径,
    # 换用后取用集 ⊄ 该配置圈定集 的差集(真拒在派发 409
    # identity_not_circled,故非空时 scheme_valid=False 与 scope_missing
    # 同读法);未按执行配置口径预检 = 空清单(派发默认行口径时再拦)
    not_circled: list[str] = Field(
        default_factory=list, alias="notCircled")


@router.post("/precheck", response_model=list[PrecheckResult])
async def precheck_run(
    principal: PrincipalIn,
    db: DbSession,
    items: Annotated[list[PrecheckItem], Field(max_length=_MAX_BATCH)],
    token_id: Annotated[int | None, Query(alias="tokenId", ge=1)] = None,
) -> list[PrecheckResult]:
    """批量预检:队列 N 条一次发回判定面,逐条独立结论(一条 404 不连坐)。

    webhook v4 §5.3:``tokenId`` 查询参数把每条方案按**该令牌的范围**做
    预检(缺项 + 范围外目标);令牌路径(``Authorization: Bearer gtk_``)
    不传即自动以当前令牌预检。JWT 只能预检自己可管理的令牌
    (``can_manage``;user 角色仅限自己的个人令牌)。"""
    from ..services import access_token as at_svc

    user = principal.user
    token = principal.token if principal.is_token else None
    if token is None and token_id is not None:
        from ..models.access_token import AccessToken
        token = await db.get(AccessToken, token_id)
        if token is None or not at_svc.can_manage(user, token):
            token = None      # 不可管理 = 当作没传(不带范围预检,不 404 连坐;
                              # §5.3:JWT 只能预检自己可管理的令牌)
    out: list[PrecheckResult] = []
    for item in items:
        scen_row = await scenario_store.get_row(db, item.scenario_id)
        # authz W6:读闸升为 ref-aware(can_read_scenario_row)—— 引用
        # 被分享人本就可跑(§7.6),预检的 found 与内置凭证告警都应
        # 服务到他们;纯判会把 ref 读者当「不存在」。
        # M2b Q2:项目令牌区锁(调用面令牌;JWT 按 tokenId 预检不受锁)
        locked = (principal.is_token
                  and at_svc.zone_locked_out(principal, getattr(
                      scen_row, "project_id", None)))
        if scen_row is None or locked or not await can_read_scenario_row(
                db, user, scen_row):
            out.append(PrecheckResult(
                scenario_id=item.scenario_id, scheme_id=item.scheme_id, found=False,
                scheme_found=False, scheme_valid=False,
            ))
            continue
        _slot_map, _circled = await _item_slot_map(db, user, item)
        one = await _precheck_one(
            db, scen_row, item, token=token,
            user_id=user.id if user is not None else None,
            slot_map=_slot_map, circled=_circled)
        one.builtin_auth_shadowed = await builtin_auth_shadowed(
            user.id if user is not None else None, scen_row)
        out.append(one)
    return out


async def _item_slot_map(db, user, item: PrecheckItem) -> tuple[dict[str, str],
                                                                frozenset[str]]:
    """§8.5 ``PrecheckItem.execConfigId``:按执行配置口径预检 —— 换用
    slot_map 折进有效身份集合(与派发同一折叠);圈定集(决策 1 阶段 1)
    一并带回(advisory 差集在 ``_precheck_one`` 算)。不可加载 = 忽略
    (他人配置/已删:执行配置自身页面暴露,这里不连坐)。"""
    if item.exec_config_id is None or user is None:
        return {}, frozenset()
    try:
        from ..services.exec_config import load_choice
        cfg = await load_choice(db, user.id, item.exec_config_id)
    except Exception:  # noqa: BLE001 — 预检不因配置不可加载而连坐
        return {}, frozenset()
    if cfg is None:
        return {}, frozenset()
    circled = cfg.circled
    if not cfg.explicit or not cfg.bindings:
        return {}, circled
    from ..services.scenario_store import get_row as _get_scen
    scen = await _get_scen(db, item.scenario_id)
    if scen is None:
        return {}, circled
    from ..services.service_aliases import slot_lookup_overrides
    try:
        return await slot_lookup_overrides(
            db, (definition_from_payload(scen.payload or {})
                 ).get("steps") or [], None, cfg.bindings), circled
    except Exception:  # noqa: BLE001
        return {}, circled


async def builtin_auth_shadowed(executor_id: int | None,
                                scen_row) -> list[str]:
    """authz W6 预检告警(N9/E2):三条件同时满足才告警(防噪)。

    ① 执行人 ≠ 场景属主(内置凭证主规则生效面);② 场景 config.users
    非空;③ 这些用户(别名)在执行人自己的认证会话里解析不到 —— 主规则
    已把作者凭证当空,执行人自己又没有,跑起来必在认证段失败,提前说
    清。任一不满足 = 空清单。单场景预检与 suite 预检(validate)共用。
    """
    from ..core import db as _dbm
    from ..services import run_prepare as _rp

    if (executor_id is None or scen_row.owner_id is None
            or executor_id == scen_row.owner_id):
        return []                       # ① 不满足(含令牌匿名面兜底)
    users = _rp.built_in_user_aliases(scen_row.payload)
    if not users:
        return []                       # ② 不满足
    # 只收会话工厂(N1-6):开独立短会话做快照读,不与请求会话混。
    # §8.3:取用不校验标签 —— 无环境位
    resolved = await _rp.resolve_exec_auths(
        _dbm.SessionLocal, executor_id, sorted(users))
    return sorted(set(users) - {a.alias for a in resolved})   # ③


async def _precheck_one(
    db: AsyncSession, scen: ComposerScenario, item: PrecheckItem,
    *, token: "Any | None" = None, user_id: int | None = None,
    slot_map: dict[str, str] | None = None,
    circled: "frozenset[str] | None" = None,
) -> PrecheckResult:
    result = PrecheckResult(scenario_id=item.scenario_id, scheme_id=item.scheme_id)
    raw_payload = scen.payload or {}

    # ── 方案本体 ──────────────────────────────────────────────────
    try:
        scheme = await scheme_store.get_row(db, scen.scenario_id, item.scheme_id)
    except KeyError:
        result.scheme_found = False
        result.scheme_valid = False
        return result
    payload: dict[str, Any] = scheme_store.normalized(scheme.payload)
    selection = payload.get("dataSetSelection") or []
    entry_ids = payload.get("injectionEntryIds") or []
    bindings = payload.get("serviceBindings") or {}

    # ── 数据集存在性(方案引用 × 本场景名下)─────────────────────
    ds_ids = sorted({s.get("datasetId") for s in selection
                     if isinstance(s, dict) and s.get("datasetId")})
    if ds_ids:
        rows = (await db.execute(
            select(ComposerDataSet.dataset_id).where(
                ComposerDataSet.scenario_id == scen.scenario_id,
                ComposerDataSet.dataset_id.in_(ds_ids),
            )
        )).scalars().all()
        result.dead_dataset_ids = sorted(set(ds_ids) - set(rows))

    # ── 注入条目悬空判定(dispatch 唯一实现,§1.6)────────────────
    _, dangling, _degraded = await run_dispatcher.filter_injection_entries(
        raw_payload, [str(e) for e in entry_ids]
    )
    result.dangling_entry_ids = dangling

    # ── 有效身份清单(§8.2:标签解析的唯一输入)────────────────────
    # 先于地址/凭证判定 —— 标签 = 有效身份标签 > 项目默认 > 平台默认,
    # 一次解析向下复用(替换旧的三处独立环境解析,口径不可能再漂移)。
    from ..services import service_aliases as _sa
    _auth_aliases = await _sa.exec_auth_aliases_of_definition(
        db, definition_from_payload(raw_payload), bindings)
    _lookup = slot_map or {}
    _folded = [n for n in (_lookup.get(a, a) for a in _auth_aliases)
               if n]
    from ..services.env_chain import EnvMixed, resolve_execution_tag
    _env = None
    _env_mixed = False
    try:
        _env = await resolve_execution_tag(
            db, identity_names=_folded, project_id=scen.project_id)
    except EnvMixed as e:
        _env_mixed = True      # 混拼:派发侧 409(env_mixed);预检如实单列
        result.env_mixed = True
        result.env_warnings.append(str(e))
    if _env is not None and _env.env_id is not None:
        result.env_context = _env.snapshot()

    # ── 决策 1 圈定即承诺(阶段 1,advisory):按 PrecheckItem.
    # execConfigId 口径,换用后取用集 ⊄ 圈定集 → notCircled 差集
    # (真拒在派发 409 identity_not_circled,故与 scope_missing 同读法
    # 置 scheme_valid=False);未按执行配置口径预检 = 空清单。
    if _auth_aliases and circled:
        result.not_circled = sorted(set(_folded) - set(circled))
        if result.not_circled:
            result.scheme_valid = False

    # ── 未落点的服务引用(steps 引用 × 三层地址链皆缺)──────────
    result.unbound_services = await _gate_unbound_services(
        db, project_id=scen.project_id,
        definition=definition_from_payload(raw_payload), env=_env)

    # ── S8 收口:凭证缺槽(个人池差集 + 项目池差集)────────────────
    # 与派发 fail-fast 同源:exec_auth_aliases_of_definition 清单 ∪
    # pick_bindings 取用;§8.3 取用不校验标签。「标签不可解析」单列
    # 信号(env_unspecified 根因语义,§8.2)—— 全数 missing 是表象;
    # 混拼不连坐(根因已由 envMixed 点名)。
    if _auth_aliases:
        from ..services.run_prepare import pick_bindings_full
        if _env is None or _env.env_id is None:
            result.env_unspecified = not _env_mixed
        # 取用按换用后条目判(与派发漏斗同折叠;报告键回声明名)。
        # 复核收口(2026-11-22):missing/ambiguous 分类 —— 歧义条目
        # (同引用多候选,执行 409)不再混标「缺失」误导排障;闸面
        # 行为不变(两者均不可取用)。
        _picked, _pmiss, _pamb = await pick_bindings_full(
            db, user_id, _folded)
        result.ambiguous_auths = sorted(
            a for a in set(_auth_aliases)
            if _lookup.get(a, a) in set(_pamb))
        result.missing_auths = sorted(
            a for a in set(_auth_aliases)
            if _lookup.get(a, a) in set(_pmiss))
        from ..services.zone import can_use_project_credentials
        if user_id is not None and await can_use_project_credentials(
                db, user_id, scen.project_id):
            _pp, _ppmiss, _ppamb = await pick_bindings_full(
                db, None, _folded, cred_project_id=scen.project_id)
            result.project_ambiguous_auths = sorted(
                a for a in set(_auth_aliases)
                if _lookup.get(a, a) in set(_ppamb))
            result.project_missing_auths = sorted(
                a for a in set(_auth_aliases)
                if _lookup.get(a, a) in set(_ppmiss))

    # ── §8.5 跨标签凭证提示(不拦截):账户标签 ≠ 执行标签 ──────────
    if _auth_aliases and _env is not None and _env.env_id is not None:
        _cls = await _gate_classify_identities(
            db, auth_aliases=_auth_aliases, user_id=user_id,
            slot_map=slot_map, login_required=set())
        result.env_warnings.extend(
            f"身份 {w['alias']} 的账户标签 #{w['accountEnvId']} 与执行标签"
            f" #{_env.env_id} 不同(凭证解耦,不拦截;执行期 401 自然暴露)"
            for w in _cls["cross_tag"])

    # ── webhook v4 §5.3:令牌范围预检(缺项分类 + 范围外目标)─────
    if token is not None:
        from ..services import access_token as at_svc
        used = await at_svc.used_sets_for_definition(
            db, definition_from_payload(raw_payload), bindings,
            project_id=scen.project_id)
        missing = await at_svc.check_scope(db, token, token.user_id, used)
        if missing:
            result.scope_missing = [
                {"kind": m.kind, "name": m.name, "deleted": m.deleted}
                for m in missing]
            result.scheme_valid = False
        result.out_of_scope_targets = used.out_of_scope["targets"]

    result.scheme_valid = result.scheme_valid and not (
        result.dead_dataset_ids or result.dangling_entry_ids)
    return result



# ── M3 §8.5 共用分类私有函数(硬门与 _precheck_one 同一套判定)────


async def _gate_unbound_services(
    db: AsyncSession, *, project_id, definition: dict, env,
) -> list[str]:
    """未落点的服务引用(steps 引用 × 地址链皆缺)—— 与执行期地址链
    同口径:③ 标签部署地址 > ④ 缺口引擎报错(① 绑定 url 随 S6 退役;
    ② authored 声明随架构终态 2026-11-21 退役,场景不持有地址)。
    落点判定共用 ``run_materialize.service_url_resolved``(物化
    ``_apply_services`` 同一实现,规则不第二份重写);③ 层按需查询
    (不整表拉)。混拼/无标签时不给 ③(地址无从选,宁可多报缺)。"""
    from ..services.run_materialize import service_url_resolved

    steps = definition.get("steps") or []
    candidates = [
        svc for svc in referenced_services(steps)
        if not service_url_resolved(svc, alias_base_urls={})
    ]
    if candidates and env is not None and env.env_id is not None:
        try:
            from ..services import service_aliases
            alias_urls = await service_aliases.base_urls_for(
                db, candidates, env=env)
        except Exception:  # noqa: BLE001 — 查表失败保守多报(不误放行)
            alias_urls = {}
        candidates = [s for s in candidates if not service_url_resolved(
            s, alias_base_urls=alias_urls)]
    return candidates


async def _gate_classify_identities(
    db: AsyncSession, *, auth_aliases, user_id,
    cred_project_id: "int | None" = None,
    slot_map: "dict[str, str] | None" = None,
    login_required: "set[str] | None" = None,
) -> dict:
    """身份/账户/登录口分类(§8.3 + §8.5;_precheck_one 与硬门共用)。

    ``slot_map`` = 执行配置换用(取用名换算后分类,与派发同一折叠);
    池口径:``cred_project_id`` 非空 = 项目池。``login_required`` =
    引用登录态面的身份名集(auth_ref_scan.scan_token_faces;None =
    不做登录口判定)。返回:

    * ``identity_missing``:条目未登记/悬空(表里查无此名);
    * ``account_missing``:条目在、凭证池取用落空(无 ref 命中行);
    * ``account_ambiguous``:多候选且无同标签唯一命中(§8.3);
    * ``login_missing``:``{alias, system, envId}`` —— 登录态面身份的
      账户可解但 (system, 账户标签) 实例登录口缺(§4.3 口径:缺席
      明确报);**纯字段面(静态令牌形态)不在内** —— 引擎 PreToken
      (password 即 token)是合法配置,不硬拦;
    * ``cross_tag``:``{alias, accountEnvId}`` —— 可解账户的标签
      (调用方对比执行标签后生成「凭证解耦」提示,不拦截)。
    """
    from ..models.service_identity import ServiceIdentity
    from ..models.system_env_instance import SystemEnvInstance
    from ..services.run_prepare import _resolve_identities

    out: dict = {"identity_missing": [], "account_missing": [],
                 "account_ambiguous": [], "login_missing": [],
                 "cross_tag": []}
    lookup = slot_map or {}
    folded = [n for n in (lookup.get(a, a) for a in auth_aliases) if n]
    if not folded:
        return out
    picked, miss, amb = await _resolve_identities(
        db, user_id, folded, cred_project_id=cred_project_id)
    out["account_ambiguous"] = sorted(amb)
    # 缺失拆分:条目不存在 → identity_missing;条目在、取用落空 → account_missing
    if miss:
        known = set((await db.execute(
            select(ServiceIdentity.alias_name).where(
                ServiceIdentity.alias_name.in_(sorted(set(miss)))))).scalars())
        out["identity_missing"] = sorted(set(miss) - known)
        out["account_missing"] = sorted(set(miss) & known)
    if picked:
        _need_login = ({lookup.get(n, n) for n in (login_required or ())}
                       if login_required is not None else set(picked))
        inst_rows = (await db.execute(
            select(SystemEnvInstance.system, SystemEnvInstance.env_id,
                   SystemEnvInstance.login_url).where(
                SystemEnvInstance.system.in_(
                    {p.system for p in picked.values()})))).all()
        have = {(s, e): (u or "") for s, e, u in inst_rows}
        for name in sorted(picked):
            p = picked[name]
            if (name in _need_login
                    and not have.get((p.system, p.env_id))):
                out["login_missing"].append(
                    {"alias": name, "system": p.system, "envId": p.env_id})
            out["cross_tag"].append({"alias": name, "accountEnvId": p.env_id})
    return out


async def precheck_hard_gate(
    db: AsyncSession, *, project_id, definition: dict, user_id,
    bindings: "dict | None" = None,
    auth_aliases: "list[str] | None" = None,
    slot_map: "dict[str, str] | None" = None,
    cred_project_id: "int | None" = None,
    env=None,
    circled: "frozenset[str] | set[str] | None" = None,
) -> dict:
    """§8.5 预检硬门(三路径共用唯一实现;run_dispatcher「不开第二份」
    原则):UI/JWT、access token 经派发漏斗,webhook 定时路径在
    integration_runner 装载前。

    标签一次解析(``env`` 传入即复用 —— 派发侧已解析过,不二次解析);
    有效身份 = 绑定 + 执行配置换用(slot_map)后的取用集合。**硬拦截**
    (``PrecheckGateError`` → 派发 409 / 定时暂停):标签不可解析、混拼、
    身份/账户缺失、账户歧义、登录口缺、地址双缺。**提示不拦截**:
    跨标签凭证(envWarnings)、``out_of_scope_targets`` 只记录、
    ``scope_missing`` 仍置 ``scheme_valid=False``(真拒在 403 范围闸)、
    suites validate 保持 warn 聚合语义(离线校验面,HTTP 恒 200)。

    返回分类明细(预检端点填契约字段消费):``authAliases`` / ``env`` /
    ``unbound`` / ``identity_missing`` / ``account_missing`` /
    ``account_ambiguous`` / ``login_missing`` / ``cross_tag``。
    """
    from ..services import service_aliases as _sa

    if auth_aliases is None:   # 调用方已扫过(派发漏斗)即直传,不二扫
        auth_aliases = await _sa.exec_auth_aliases_of_definition(
            db, definition, bindings)
    lookup = slot_map or {}
    folded = [n for n in (lookup.get(a, a) for a in auth_aliases) if n]
    # ① 标签(悬空名不参与判定,§8.2 —— 其根因在 ② identity_missing)
    if env is None:
        from ..services.env_chain import EnvMixed, resolve_execution_tag
        try:
            env = await resolve_execution_tag(
                db, identity_names=folded, project_id=project_id)
        except EnvMixed as e:
            raise PrecheckGateError(GATE_ENV_MIXED, str(e),
                                    {"identities": e.entries}) from None
    # ② 身份/账户/登录口(先于 env_unspecified:悬空条目的根因是
    # 「条目未登记」而不是「标签不可解析」,错误码不给表象)。登录口
    # 判定收窄到登录态面(token 裸引/call.user)—— 静态令牌形态
    # (纯字段面引用,引擎 PreToken)是合法配置,不硬拦。
    from ..services.auth_ref_scan import scan_token_faces
    from ..services.service_aliases import setup_teardown_nodes
    cls = await _gate_classify_identities(
        db, auth_aliases=auth_aliases, user_id=user_id,
        cred_project_id=cred_project_id, slot_map=slot_map,
        # D2 收口(2026-11-22):setup/teardown 条目并入登录态面扫描 ——
        # 其 params 可含 ${auth.*} 裸引(经 setup_teardown_nodes 进
        # auth_aliases,却漏在 steps-only 的 login_required 外),登录口
        # 缺失预检绿、运行期才暴露(引擎静态令牌降级步骤级 401)。
        login_required=scan_token_faces(
            [*(definition.get("steps") or []),
             *setup_teardown_nodes(definition)]))
    if cls["identity_missing"]:
        raise PrecheckGateError(
            GATE_IDENTITY_MISSING,
            "以下身份条目未登记或已悬空,请先在服务注册页登记: "
            + "、".join(cls["identity_missing"]),
            {"aliases": cls["identity_missing"]})
    if folded and (env is None or env.env_id is None):
        raise PrecheckGateError(
            GATE_ENV_UNSPECIFIED,
            "执行标签不可解析:场景用到身份条目,但 条目标签 > 项目默认"
            " > 平台默认 均未命中 —— 请为条目设置标签,或建/设项目或"
            "平台默认环境", {"aliases": sorted(set(folded))})
    if cls["account_missing"]:
        _proj = cred_project_id is not None
        raise PrecheckGateError(
            GATE_ACCOUNT_MISSING,
            ("以下身份条目项目凭证未登记,请项目管理员在项目配置页登记,"
             "或改用个人凭证:" if _proj else
             "以下身份条目在你名下未装载,请先在凭证管理登记账户或换绑条目:")
            + "、".join(cls["account_missing"]),
            {"aliases": cls["account_missing"],
             "credentialSource": "project" if _proj else "personal"})
    if cls["account_ambiguous"]:
        raise PrecheckGateError(
            GATE_ACCOUNT_AMBIGUOUS,
            "以下身份条目命中多候选账户(同系统多标签且无同标签唯一"
            "命中),请补充同标签账户或改绑: "
            + "、".join(cls["account_ambiguous"]),
            {"aliases": cls["account_ambiguous"]})
    if cls["login_missing"]:
        raise PrecheckGateError(
            GATE_LOGIN_MISSING,
            "以下身份的账户已装载,但所属「系统 × 标签」实例未配置登录口"
            "(请在实例配置中维护登录地址): " + "、".join(
                f"{m['alias']}(系统 {m['system']} × 标签#{m['envId']})"
                for m in cls["login_missing"]),
            {"logins": cls["login_missing"]})
    # ②b 圈定即承诺(决策 1 §4,阶段 1):``circled`` = 生效执行配置行的
    # 圈定集(非空才生效;None/空 = 未圈定,存量兼容跳过)。比对集 =
    # 换用后取用集(folded,含 slot 换用目标);差集非空 → 硬拦。重跑按
    # 首发快照照查(调用方传入),单一规则不豁免;行级 @slot 绑定在派发
    # 侧同一码拦截(precheck_hard_gate 不见行引用)。
    if circled:
        _outside = sorted(set(folded) - set(circled))
        if _outside:
            raise PrecheckGateError(
                GATE_IDENTITY_NOT_CIRCLED,
                "以下身份条目不在本次生效执行配置的圈定集内,请到执行配置"
                "页「纳入」后重跑: " + "、".join(_outside),
                {"aliases": _outside})
    # ③ 地址
    unbound = await _gate_unbound_services(
        db, project_id=project_id, definition=definition, env=env)
    if unbound:
        raise PrecheckGateError(
            GATE_ADDRESS_MISSING,
            "以下服务未配置地址(声明与所选标签的部署表均缺),执行器"
            "无从落地址: " + "、".join(unbound),
            {"services": unbound,
             **({"environmentId": env.env_id}
                if env is not None and env.env_id is not None else {})})
    return {"authAliases": auth_aliases, "env": env, "unbound": unbound, **cls}
