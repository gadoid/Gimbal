"""services/adhoc_run.py — 临时调用(P3,设计 2026-11-02)的派发前校验链。

请求 ``steps`` 是配方,按 M1 同一原则收紧(§三):只能带锚点、服务别名、
值与取回声明;method / path / headers / 地址 / 凭证 / 版本全部由平台按
plate 定义、别名表、环境版本线补。校验全部在派发前完成(§四 2–6),
不通过即 4xx、不建执行行;顺序:结构 → 服务别名 → 地址落点 → 版本 →
组装 → 干跑 convert。身份闸(§四.1,403)在路由层。

干跑 convert 的结果不缓存进执行:执行期按正常链路再 convert 一次,
「派发前校验」与「执行」走同一代码路径,不分叉。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.environment import Environment
from ..models.service_alias import ServiceAlias
from . import plate_client
from .run_materialize import service_url_resolved
from .run_prepare import build_adhoc_payload
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
) -> dict[str, ServiceAlias]:
    if not names:
        return {}
    rows = (await db.execute(select(ServiceAlias).where(
        ServiceAlias.alias_name.in_(names)))).scalars().all()
    return {r.alias_name: r for r in rows}


def check_services(steps: list[dict], rows: dict[str, ServiceAlias]) -> None:
    """§四.3:别名存在、``kind=plate``、``base_service`` = 锚点系统
    (别名不能拿来调别的系统的接口)→ 否则 422 ``adhoc_service_mismatch``。"""
    offenders: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for st in steps:
        svc, system = str(st["service"]).strip(), _system_of(str(st["endpoint"]).strip())
        if (svc, system) in seen:
            continue
        seen.add((svc, system))
        row = rows.get(svc)
        if row is None:
            offenders.append({"service": svc, "reason": "unknown"})
        elif row.kind != "plate":
            offenders.append({"service": svc, "reason": "not_plate"})
        elif row.base_service != system:
            offenders.append({"service": svc, "reason": "system_mismatch",
                              "system": system, "baseService": row.base_service})
    if offenders:
        raise AdhocRejected(
            "adhoc_service_mismatch",
            "service 必须是已登记的 plate 别名,且其 base_service 与锚点"
            "系统一致: " + "、".join(
                f"{o['service']}({o['reason']})" for o in offenders),
            extra={"services": offenders})


def check_addresses(services: list[str], rows: dict[str, ServiceAlias]) -> None:
    """§四.4:地址落点按三层链唯一实现判定(临时调用无显式绑定、无
    authored 声明,只剩第③层别名 base_url)→ 缺 422 ``adhoc_service_unresolved``。"""
    alias_base_urls = {n: r.base_url for n, r in rows.items() if r.base_url}
    missing = [s for s in services if not service_url_resolved(
        s, declared={}, bindings={}, alias_base_urls=alias_base_urls)]
    if missing:
        raise AdhocRejected(
            "adhoc_service_unresolved",
            "以下别名未配置 base_url,执行器无从落地址: " + "、".join(missing),
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
    db: AsyncSession, steps: list[dict], rows: dict[str, ServiceAlias],
    release: dict[str, str] | None,
) -> dict[str, str]:
    """§四.5 / P3-D6:``release`` 指定的系统用它;否则别名所属环境的
    ``lines[系统]`` → 线内最新修订。取不到(别名无环境 / 环境未声明该系统
    / 同系统别名分属不同线 / plate 无此线)→ 422 ``adhoc_version_unresolved``。
    """
    systems_services: dict[str, list[str]] = {}
    for st in steps:
        systems_services.setdefault(
            _system_of(str(st["endpoint"]).strip()), []
        ).append(str(st["service"]).strip())
    env_ids = sorted({r.environment_id for r in rows.values() if r.environment_id})
    envs: dict[int, Environment] = {}
    if env_ids:
        envs = {e.id: e for e in (await db.execute(select(Environment).where(
            Environment.id.in_(env_ids)))).scalars().all()}
    meta_plate: dict[str, str] = {}
    unresolved: list[dict] = []
    for system, services in systems_services.items():
        if release and system in release:
            meta_plate[system] = str(release[system])
            continue
        lines: set[str] = set()
        for svc in dict.fromkeys(services):
            row = rows.get(svc)
            env = envs.get(row.environment_id) if row and row.environment_id else None
            line = ((env.lines or {}).get(system) if env else None)
            if line:
                lines.add(str(line))
        if not lines:
            unresolved.append({"system": system, "reason": "no_line"})
            continue
        if len(lines) > 1:
            unresolved.append({"system": system, "reason": "conflicting_lines",
                               "lines": sorted(lines)})
            continue
        line = lines.pop()
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


async def prepare_adhoc(db: AsyncSession, req: Any, *, run_id: str) -> dict:
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
    rows = await load_alias_rows(db, services)
    check_services(steps, rows)
    check_addresses(services, rows)
    meta_plate = await resolve_versions(db, steps, rows, req.release)
    payload = build_adhoc_payload(
        steps, run_id=run_id, meta_plate=meta_plate,
        credential_by_service={n: r.credential_alias for n, r in rows.items()
                               if r.credential_alias},
        name=display_name(steps))
    await dry_run_convert(payload)
    return payload
