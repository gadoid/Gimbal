"""services/adhoc_run.py — 临时调用(设计 2026-11-02)的派发前校验链。

请求 ``steps`` 是配方,与入站调用同一原则收紧(§三):只能带锚点、服务别名、
值与取回声明;method / path / headers / 地址 / 凭证 / 版本全部由平台按
plate 定义、别名表、环境版本线补。校验全部在派发前完成(§四 2–6),
不通过即 4xx、不建执行行;顺序:结构 → 锚点存在 → 服务别名 → 地址落点
→ 版本 → 组装 → 干跑 convert。身份闸(§四.1,403)在路由层。

干跑 convert 的结果不缓存进执行:执行期按正常链路再 convert 一次,
「派发前校验」与「执行」走同一代码路径,不分叉。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.environment import Environment
from ..models.service import Service
from ..models.service_identity import ServiceIdentity
from . import plate_client
from .run_materialize import service_url_resolved
from .run_prepare import build_adhoc_payload, pick_bindings_full
from .run_semantics import PIN, ref_category

MAX_STEPS = 10
# 步骤白名单(§三 + 评审补项 pathParams):其余字段(含 call.* / config /
# headers 等)一律拒。pathParams 只是 plate 路径模板 {key} 占位的**值**
# (模板本身仍来自 plate 定义,执行器缺键报 PATH_PARAM_MISSING)—— 不补
# 它,带路径参数的接口临时调用永远调不了。
STEP_FIELDS = frozenset({"endpoint", "service", "body", "strategy", "pathParams"})
# 策略白名单(P3-D3)= 执行器 M2 StrategyUnion 全集(kind 判别);
# 结构按执行器 schema(extra='forbid')由干跑 convert 校验。
STRATEGY_KINDS = frozenset({"extract", "assertion", "assign"})
# RunRequest 上属「场景执行配方」的字段,临时调用一律拒收(§三):只留
# steps / release / clientRef / callbackPath。
RECIPE_FIELDS = (
    ("scheme_id", "schemeId"), ("scheme_name", "schemeName"),
    ("data_set_ids", "dataSetIds"), ("data_set_selection", "dataSetSelection"),
    ("service_bindings", "serviceBindings"),
    ("injection_entry_ids", "injectionEntryIds"), ("graph", "graph"),
    ("report_definition_id", "reportDefinitionId"), ("batch_id", "batchId"),
    ("run_options", "runOptions"),
)


class AdhocRejected(Exception):
    """派发前校验不通过 —— 路由映射为 HTTP ``status`` +
    ``{code, message, ...extra}``(错误码表见设计 §十一)。"""

    def __init__(self, code: str, message: str, *, status: int = 422,
                 extra: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.extra = extra or {}


def recipe_fields_present(req: Any) -> list[str]:
    """RunRequest 上被临时调用拒收的配方字段(非空即算携带,口径同
    M1 ``_reject_inbound_recipe``)。"""
    out: list[str] = []
    for attr, wire in RECIPE_FIELDS:
        val = getattr(req, attr, None)
        if val is None:
            continue
        if isinstance(val, (list, dict, str)) and not val:
            continue
        out.append(wire)
    return out


def _system_of(endpoint: str) -> str:
    return endpoint.split(".", 1)[0]


def check_structure(steps: Any, release: Any) -> None:
    """§四.2:步数 1..10、字段白名单、策略白名单、release 形状。

    白名单外字段 / 不允许的策略 / 步数越界 → 422 ``adhoc_field_not_allowed``
    (``fields`` 列全部违规路径);必填缺失或形状错(endpoint / service 非
    非空字符串、body 非 dict|list|str、strategy 非列表)→ 422
    ``adhoc_step_invalid``。
    """
    if not isinstance(steps, list) or not (1 <= len(steps) <= MAX_STEPS):
        raise AdhocRejected(
            "adhoc_field_not_allowed",
            f"steps 须为 1..{MAX_STEPS} 步的数组", extra={"fields": ["steps"]})
    not_allowed: list[str] = []
    invalid: list[str] = []
    systems: set[str] = set()
    for i, st in enumerate(steps):
        p = f"steps[{i}]"
        if not isinstance(st, dict):
            invalid.append(p)
            continue
        for k in st:
            if k in STEP_FIELDS:
                continue
            # call.method / call.path / call.headers … 逐键列出,错误可读
            if k == "call" and isinstance(st[k], dict) and st[k]:
                not_allowed.extend(f"{p}.call.{ck}" for ck in st[k])
            else:
                not_allowed.append(f"{p}.{k}")
        ep = st.get("endpoint")
        if not isinstance(ep, str) or not ep.strip() or "." not in ep:
            invalid.append(f"{p}.endpoint")
        else:
            systems.add(_system_of(ep.strip()))
        svc = st.get("service")
        if not isinstance(svc, str) or not svc.strip():
            invalid.append(f"{p}.service")
        if "body" in st and not isinstance(st["body"], (dict, list, str)):
            invalid.append(f"{p}.body")
        pp = st.get("pathParams")
        if pp is not None and not (
                isinstance(pp, dict)
                and all(isinstance(k, str) and k
                        and isinstance(v, (str, int, float)) and not isinstance(v, bool)
                        for k, v in pp.items())):
            invalid.append(f"{p}.pathParams")
        strat = st.get("strategy")
        if strat is not None:
            if not isinstance(strat, list):
                invalid.append(f"{p}.strategy")
            else:
                for j, entry in enumerate(strat):
                    kind = entry.get("kind") if isinstance(entry, dict) else None
                    if kind not in STRATEGY_KINDS:
                        not_allowed.append(f"{p}.strategy[{j}].kind")
    if release is not None:
        if not isinstance(release, dict):
            not_allowed.append("release")
        else:
            for sys_, ref in release.items():
                if sys_ not in systems or ref_category(str(ref)) != PIN:
                    not_allowed.append(f"release.{sys_}")
    if not_allowed:
        raise AdhocRejected(
            "adhoc_field_not_allowed",
            "临时调用只接受 steps[*].{endpoint, service, body, pathParams, "
            "strategy}、策略 kind ∈ extract|assertion|assign、release 只能钉"
            "步骤锚到的系统且形如 <线>#<修订>: " + "、".join(not_allowed),
            extra={"fields": not_allowed})
    if invalid:
        raise AdhocRejected(
            "adhoc_step_invalid",
            "步骤缺必填或形状不对(endpoint 为 <系统>.<接口>、service 为"
            "别名名、body 为对象/数组/字符串、pathParams 为 {占位: 标量}、"
            "strategy 为数组): " + "、".join(invalid),
            extra={"fields": invalid})


async def load_alias_rows(
    db: AsyncSession, names: list[str],
) -> dict[tuple[ServiceIdentity, str]]:
    """条目行 + 主档 kind 元组(重构:kind 自服务主档)。"""
    if not names:
        return {}
    rows = (await db.execute(
        select(ServiceIdentity, Service.kind).join(
            Service, Service.name == ServiceIdentity.base_service).where(
            ServiceIdentity.alias_name.in_(names)))).all()
    return {r.alias_name: (r, kind or "plate") for r, kind in rows}


def check_services(
    steps: list[dict], rows: dict, endpoint_services: dict[str, str],
) -> None:
    """§四.3:别名存在、``kind=plate``、``base_service`` = 锚点在 plate 中
    **声明的服务**(别名不能拿来调别的服务的接口)→ 否则 422
    ``adhoc_service_mismatch``。

    比较对象是端点的 ``service`` 字段,不是锚点首段的系统名 —— 两者是
    不同命名空间(``fin.account.query_balance`` 属系统 ``fin``,其端点
    声明的 service 是 ``fin-service``;别名 ``base_service`` 取自 plate
    服务目录,即后者)。``endpoint_services`` 由
    :func:`lookup_endpoint_services` 预取。
    """
    offenders: list[dict] = []
    bad_alias: set[str] = set()            # unknown / not_plate 每个别名只报一次
    seen: set[tuple[str, str]] = set()
    for st in steps:
        svc, ep = str(st["service"]).strip(), str(st["endpoint"]).strip()
        if (svc, ep) in seen or svc in bad_alias:
            continue
        seen.add((svc, ep))
        hit = rows.get(svc)
        if hit is None:
            bad_alias.add(svc)
            offenders.append({"service": svc, "reason": "unknown"})
        elif hit[1] != "plate":
            bad_alias.add(svc)
            offenders.append({"service": svc, "reason": "not_plate"})
        elif hit[0].base_service != endpoint_services.get(ep):
            offenders.append({"service": svc, "reason": "service_mismatch",
                              "endpoint": ep,
                              "endpointService": endpoint_services.get(ep),
                              "baseService": hit[0].base_service})
    if offenders:
        raise AdhocRejected(
            "adhoc_service_mismatch",
            "service 必须是已登记的 plate 别名,且其 base_service 与锚点在"
            "plate 中声明的服务一致: " + "、".join(
                f"{o['service']}({o['reason']})" for o in offenders),
            extra={"services": offenders})


async def lookup_endpoint_services(steps: list[dict]) -> dict[str, str]:
    """按锚点取 plate 当前定义的 ``service``(``/api/endpoint/{id}/full``,
    共用进程级 TTL 缓存)。锚点在 plate 中不存在(404)→ 422
    ``adhoc_invalid``(``errors`` 形状同干跑 convert 的逐字段错误,比等到
    干跑更早、更明确);其余取不到(连不上 / 非 404 / 信封坏)→
    ``PlateUnavailableError``(路由 503)。
    """
    out: dict[str, str] = {}
    errors: list[dict] = []
    for ep in dict.fromkeys(str(st["endpoint"]).strip() for st in steps):
        res = await plate_client.get_endpoint_full(ep)
        if res.item is None:
            if res.status == 404:
                errors.extend(
                    {"path": f"steps[{i}].endpoint",
                     "message": f"plate 中不存在锚点 {ep}"}
                    for i, st in enumerate(steps)
                    if str(st["endpoint"]).strip() == ep)
                continue
            raise plate_client.PlateUnavailableError(
                f"plate_unavailable: 取端点 {ep} 定义失败"
                f"(status {res.status}): {res.reason}")
        out[ep] = str(res.item.get("service") or "")
    if errors:
        raise AdhocRejected(
            "adhoc_invalid", "锚点在 plate 中不存在", extra={"errors": errors})
    return out


async def check_addresses(
    db, services: list[str], user_id: int,
    identity_names: list[str] | None = None,
) -> None:
    """§四.4 + §8.2:地址落点走执行同一条 ③ 层链(``base_urls_for``,
    标签 = 身份标签 > 平台默认 —— adhoc 无项目归属;``identity_names``
    = 本次临时调用的身份条目名集)。缺 422 ``adhoc_service_unresolved``。"""
    from . import env_chain, service_aliases as _sa
    from .run_materialize import service_url_resolved

    # M3 §8.5:EnvMixed 映射 409 env_mixed(此前裸冒 500 —— 路由 except
    # 清单只认 AdhocRejected/PlateUnavailableError)
    try:
        _env = await env_chain.resolve_execution_tag(
            db, identity_names=identity_names)
    except env_chain.EnvMixed as e:
        raise AdhocRejected("env_mixed", str(e), status=409,
                            extra={"identities": e.entries}) from None
    alias_base_urls = await _sa.base_urls_for(db, list(services), env=_env)
    missing = [s for s in services if not service_url_resolved(
        s, alias_base_urls=alias_base_urls)]
    if missing:
        raise AdhocRejected(
            "adhoc_service_unresolved",
            "以下服务未配置地址(所选标签的部署表均缺),"
            "执行器无从落地址: " + "、".join(missing),
            extra={"services": missing})


async def _latest_on_line(system: str, line: str) -> str | None:
    """线内最新修订 → ``<线>#<n>``;plate 无此系统/线 → None(调用方判
    422);plate 不可达上抛 PlateUnavailableError(路由映射 503)。"""
    try:
        items = await plate_client.list_lines(system)
    except plate_client.PlateRejectedError:
        return None
    for it in items or []:
        if not isinstance(it, dict) or str(it.get("line")) != line:
            continue
        latest = str(it.get("latest") or "")
        if ref_category(latest) == PIN:
            return latest
        break
    try:
        revs = await plate_client.list_line_revisions(system, line)
    except plate_client.PlateRejectedError:
        return None
    best = -1
    for r in revs or []:
        ref = str((r or {}).get("ref") or "") if isinstance(r, dict) else ""
        if ref_category(ref) == PIN:
            n = int(ref.rsplit("#", 1)[1])
            best = max(best, n)
    return f"{line}#{best}" if best >= 0 else None


async def resolve_versions(
    db: AsyncSession, steps: list[dict],
    release: dict[str, str] | None, *, user_id: int | None,
    identity_names: list[str] | None = None,
) -> dict[str, str]:
    """§四.5 / P3-D6 + §8.2:``release`` 指定的系统用它;否则**本次标签**
    (身份标签 > 平台默认;``identity_names`` = 临时调用的身份条目名集)
    的 ``lines[系统]`` → 线内最新修订。取不到(无标签 / 标签未声明该
    系统 / plate 无此线)→ 422 ``adhoc_version_unresolved``。
    """
    from . import env_chain

    systems = list(dict.fromkeys(
        _system_of(str(st["endpoint"]).strip()) for st in steps))
    # M3 §8.5:同 check_addresses,EnvMixed → 409(不裸冒 500)
    try:
        choice = await env_chain.resolve_execution_tag(
            db, identity_names=identity_names)
    except env_chain.EnvMixed as e:
        raise AdhocRejected("env_mixed", str(e), status=409,
                            extra={"identities": e.entries}) from None
    env = (await db.get(Environment, choice.env_id)
           if choice.env_id is not None else None)
    meta_plate: dict[str, str] = {}
    unresolved: list[dict] = []
    # 重构 §1.2:版本线在 system_env_instances(ADR-0003 #17)
    env_line_map = await env_chain.instance_lines(db, choice.env_id)
    for system in systems:
        if release and system in release:
            meta_plate[system] = str(release[system])
            continue
        line = env_line_map.get(system)
        if not line:
            unresolved.append({"system": system, "reason": "no_line"})
            continue
        line = str(line)
        ref = await _latest_on_line(system, line)
        if ref is None:
            unresolved.append({"system": system, "reason": "line_not_in_plate",
                               "line": line})
            continue
        meta_plate[system] = ref
    if unresolved:
        raise AdhocRejected(
            "adhoc_version_unresolved",
            "取不到版本:请在 release 显式指定 {系统: \"<线>#<修订>\"},或为别名"
            "配置声明了该系统版本线的环境: " + "、".join(
                f"{u['system']}({u['reason']})" for u in unresolved),
            extra={"systems": unresolved})
    return meta_plate


async def dry_run_convert(payload: dict) -> None:
    """§四.6:组装后调一次 plate /convert(与 preview-plate 同口径)——
    锚点不存在 / 未知字段 / 必填缺失 / 类型不符 → 422 ``adhoc_invalid``,
    ``errors`` 原样带回 plate 的逐字段错误;不可达上抛(路由 503)。"""
    try:
        data = await plate_client.convert(dict(payload["definition"]))
    except plate_client.PlateRejectedError as e:
        raise AdhocRejected(
            "adhoc_invalid", e.message or "plate 拒绝了该临时调用",
            extra={"errors": list(e.errors or [])}) from None
    converted = (data or {}).get("converted") or {}
    errors = converted.get("errors") if isinstance(converted, dict) else None
    if errors:
        raise AdhocRejected(
            "adhoc_invalid", "plate 字段校验不通过",
            extra={"errors": [e for e in errors if isinstance(e, dict)]})


def display_name(steps: list[dict]) -> str:
    first = steps[0]
    name = f"临时调用 · {first['service']} · {first['endpoint']}"
    if len(steps) > 1:
        name += f" 等 {len(steps)} 步"
    return name


async def prepare_adhoc(db: AsyncSession, req: Any, *, run_id: str,
                        user_id: int) -> dict:
    """§四 2–6 + §五:返回构造好、已干跑 convert 通过的容器 payload。

    不建行、不改库;任何一步不通过抛 :class:`AdhocRejected`(422)或
    ``plate_client.PlateUnavailableError``(路由 503)。
    """
    steps = req.steps
    check_structure(steps, req.release)
    steps = [dict(st) for st in steps]
    for st in steps:
        st["endpoint"] = str(st["endpoint"]).strip()
        st["service"] = str(st["service"]).strip()
    services = list(dict.fromkeys(st["service"] for st in steps))
    endpoint_services = await lookup_endpoint_services(steps)
    rows = await load_alias_rows(db, services)
    check_services(steps, rows, endpoint_services)
    # §8.2:标签 = 身份标签 > 平台默认(rows = 条目名;无项目归属)
    await check_addresses(db, services, user_id, identity_names=list(rows))
    meta_plate = await resolve_versions(db, steps, req.release,
                                        user_id=user_id,
                                        identity_names=list(rows))
    # 身份条目须在本人个人池可取用(adhoc 无
    # 项目归属)—— 此前缺账户静默漏到引擎层匿名调用;与场景派发
    # identity_missing 硬门同口径(422 是 adhoc 的拒发通道)。排在
    # 结构/地址/版本校验之后(未种条目的存量用例先吃 adhoc_* 422)。
    # missing/ambiguous 分类报 —— 差集统一报
    # 「未登记」会把 account_ambiguous 误标,排障指向错误修复面。
    _picked, _missing_ids, _ambig_ids = await pick_bindings_full(
        db, user_id, list(rows))
    if _missing_ids:
        raise AdhocRejected(
            "identity_missing",
            "以下身份条目在你的个人凭证池未登记,请先在「凭证管理」"
            "登记后再发起临时调用:" + "、".join(_missing_ids),
            extra={"aliases": _missing_ids})
    if _ambig_ids:
        raise AdhocRejected(
            "identity_ambiguous",
            "以下身份条目命中多个候选账户(同引用多行且无同标签唯一"
            "命中),请调整条目环境标签或清理同名账户后重试:"
            + "、".join(_ambig_ids),
            extra={"aliases": _ambig_ids})
    payload = build_adhoc_payload(
        steps, run_id=run_id, meta_plate=meta_plate,
        # 条目名即注入键(call.user = 条目名,users 按名注入;P1 缺陷
        # 修复:旧代码对 (identity, kind) 元组取 .slot → 每次成功调用
        # 必 AttributeError,该路径自 P1 起未被任何测试执行过)
        credential_by_service={n: n for n in rows},
        name=display_name(steps))
    await dry_run_convert(payload)
    return payload
