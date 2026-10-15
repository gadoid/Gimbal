"""场景导入流水线(场景导入 v2.3 方案,claude/scenario-import-design.md)。

precheck = 纯读析出分析(阻塞项/映射建议/认证引用);land = 一次性落库
(建别名 + 写 carry + 改写 definition + 建场景,单事务)。方案拍板在此
实现的落点:

* P5「有接管者才清除」—— 一致性判定先行(Codfish 规则 2026-10-15:
  同服务同路径各步骤取值不一致 → 不进 carry、不清除,保留各步字面
  值),清除计划粒度 = (step_index, path),只清该步骤自己 carry 面上
  的路径;body 字面值与 config.services URL 仅在本地有实际接管者时
  进清除集;
* P7-② 敏感路径(命名启发)不写 carry、不进清除集,字面值保留;
* P7-④ plate 调用(面/目录/convert)全部在事务外完成;
* P7-⑤ 复用判定路径级:文件面字面值路径集 vs 三层链解析值逐条比,
  本机缺值路径判"映射"并保留字面值;
* P2 config.users 清空(明文凭证不落库)。
"""
from __future__ import annotations

import json
import re
import secrets
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..models.composer_scenario import ComposerScenario
from ..models.service_alias import ServiceAlias
from ..schemas.scenario_composer import ScenarioDraft
from . import endpoint_anchoring, plate_client, scenario_store
from . import service_aliases as alias_svc
from . import service_names
from .carry_injection import build_carry_context
from .run_materialize import referenced_services

MAX_BODY_BYTES = 5 * 1024 * 1024
_SCENARIO_ID_RE = re.compile(r"^sc-[a-z0-9-]+$")
# 敏感路径命名启发(方案 §4:面无 ui_kind 类型信息时的退化判定,
# 漏检残余已拍板接受 —— 内网 + 当前面基本无密码类字段)
_SENSITIVE_RE = re.compile(r"(password|secret|token|key)", re.IGNORECASE)

_MISSING = object()


class ImportRejected(Exception):
    """可映射的导入错误(code + http + message),路由层统一转 HTTPException。"""

    def __init__(self, code: str, http: int, message: str):
        super().__init__(message)
        self.code, self.http, self.message = code, http, message


# ── 体积门 + 解析(方案 §1/§3.2-1:原始 Request,解析前拒绝)────────


async def read_bundle(request) -> dict:
    """读请求体并解析出 bundle dict:Content-Length 预检 + 限长流式读
    + len 复核。

    两个端点(precheck/import)共用;pydantic 不经手请求体,超大文件在
    json.loads 之前被拒(413 不做形式作用)。分块无 Content-Length 的
    请求按 ``request.stream()`` 累计,超限即弃读中止(不把整个请求体
    读进内存再判)。
    """
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > MAX_BODY_BYTES:
        raise ImportRejected("payload_too_large", 413, "请求体超 5MB 上限")
    buf = bytearray()
    async for chunk in request.stream():
        buf += chunk
        if len(buf) > MAX_BODY_BYTES:
            raise ImportRejected("payload_too_large", 413, "请求体超 5MB 上限")
    raw = bytes(buf)
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ImportRejected(
            "invalid_file", 422,
            f"文件不是合法 JSON(YAML 请先转存 JSON): {e}") from e
    if not isinstance(data, dict):
        raise ImportRejected("invalid_file", 422, "请求体顶层必须是 JSON 对象")
    return data


def bundle_definition(body: dict) -> dict:
    """请求体 → definition。可执行形态 ≡ definition 同 schema(方案 §1,
    无判别问题);结构底线 = scenarioId / meta / steps 三键。"""
    definition = body.get("bundle")
    if not isinstance(definition, dict):
        raise ImportRejected("invalid_file", 422, "请求体缺 bundle(场景文件)")
    for key in ("scenarioId", "meta", "steps"):
        if key not in definition:
            raise ImportRejected(
                "invalid_file", 422,
                f"bundle 缺 ``{key}`` 键 —— 不是场景可执行文件"
                "(请用「导出 JSON」产物;统一格式 = 可执行即导入)")
    return definition


# ── 纯工具 ──────────────────────────────────────────────────────────


def _is_template(v: Any) -> bool:
    return isinstance(v, str) and (v.startswith("${") or v.startswith("$."))


def _path_segs(path: str) -> list[str]:
    p = path[2:] if path.startswith("$.") else path.lstrip("$.")
    return [s for s in p.replace("[", ".").replace("]", "").split(".") if s]


def _walk(node: Any, segs: list[str]) -> Any:
    cur = node
    for s in segs:
        if isinstance(cur, dict) and s in cur:
            cur = cur[s]
        else:
            return _MISSING
    return cur


def _rev_id(item: Any) -> str | None:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for k in ("ref", "id", "revision", "name"):
            v = item.get(k)
            if isinstance(v, str) and v:
                return v
    return None


def _step_body(step: dict) -> Any:
    req = step.get("request")
    return req.get("body") if isinstance(req, dict) else None


class _Mark:
    """取值观测里的不可比标记(模板/未填),与原始 JSON 值区分类型。"""

    def __init__(self, label: str) -> None:
        self.label = label


def _json_equal(a: Any, b: Any) -> bool:
    """JSON 值相等(布尔与数字分型:JSON true ≠ 1)。"""
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    return a == b


def _obs_label(o: Any) -> str:
    if isinstance(o, _Mark):
        return o.label
    return json.dumps(o, ensure_ascii=False)


def _service_plan(ctx, raw_steps: list, svc: str, decision: str) -> dict:
    """单服务接管计划 —— 预检计数与落库清除/carry **共用的唯一计算函数**
    (合入评估 §1 修复:确认界面看到的必须就是落库要执行的)。

    一致性判定先行(Codfish 规则 2026-10-15):同服务同路径,只要各步骤
    最终取值不一致就**不进 carry、不进清除集**,所有步骤保留各自的字
    面值 —— 只有各步取值一致的路径才可交给别名接管。参与观测的步骤 =
    ``call.service`` 命中且自身 carry 面(``step_fields[i]``,原始索引)
    非空;字面值不等,或字面值与模板/未填混用(无请求体的步骤同样按
    「未填」观测 —— carry 可能给它注入源文件没有的字段)→ 判不一致。
    纯模板/未填(该路径无任何字面值观测)不参与计数 —— 文件本就没有
    可接管的取值,模板原样保留、不清除。无锚点步骤不在 ``step_fields``
    (没有面,谈不上接管),``ext:`` 锚点的面是 plate 404 降级的空面
    —— 两者天然不参与、也永不被清除。

    ``decision``:create=非敏感一致路径;reuse=本机有值且相等;map=本机
    有值(本机为准);suggest=本机有值(预检建议口径,与 reuse/map 同集)。
    """
    seen: dict[str, list[Any]] = {}
    for i, step in enumerate(raw_steps):
        if not isinstance(step, dict):
            continue
        call = step.get("call")
        if not (isinstance(call, dict) and call.get("service") == svc):
            continue
        face = ctx.step_fields.get(i) or {}
        body = _step_body(step)
        for path in face:
            if body is None:
                # 无请求体步骤按「未填」观测(复盘 2026-10-15):否则
                # 其他步骤的一致字面值会被接管,carry 可能为它注入源
                # 文件里没有的字段 —— 「最终取值不一致不接管」的口径
                obs: Any = _Mark("<未填>")
            else:
                v = _walk(body, _path_segs(path))
                if v is _MISSING:
                    obs = _Mark("<未填>")
                elif _is_template(v):
                    obs = _Mark("<模板>")
                else:
                    obs = v
            seen.setdefault(path, []).append(obs)

    consistent: dict[str, Any] = {}
    inconsistent: dict[str, list[str]] = {}
    for path, obs_list in seen.items():
        lits = [o for o in obs_list if not isinstance(o, _Mark)]
        if not lits:
            continue   # 纯模板/未填:无可接管取值,模板原样保留
        first = lits[0]
        if (any(isinstance(o, _Mark) for o in obs_list)
                or not all(_json_equal(o, first) for o in lits)):
            inconsistent[path] = [_obs_label(o) for o in obs_list]
        else:
            consistent[path] = first

    sensitive = {p for p in consistent if _SENSITIVE_RE.search(p)}
    if decision == "create":
        provider = {p for p in consistent if p not in sensitive}
    elif decision == "reuse":
        provider = {
            p for p, v in consistent.items()
            if _local_value(ctx, svc, p) is not _MISSING
            and _local_value(ctx, svc, p) == v}
    else:   # map / suggest:本机有值即接管(本机为准)
        provider = {p for p in consistent
                    if _local_value(ctx, svc, p) is not _MISSING}
    return {"consistent": consistent, "inconsistent": inconsistent,
            "provider": provider, "sensitive": sensitive}


def _local_value(ctx, svc: str, path: str) -> Any:
    """三层链解析后的本机最终值(精确别名∪base 合并 > 全局默认);
    本机无值返回 _MISSING。"""
    resolved = ctx.service_bindings.get(svc)
    if resolved is None:
        resolved = {}
    v = resolved.get(path, _MISSING)
    if v is _MISSING or v is None:
        v = (ctx.global_defaults or {}).get(path, _MISSING)
    return v


async def _available_revisions(meta_plate: dict) -> dict:
    """声明修订缺失时的可选集(提示是增强:任何查询失败降级跳过)。"""
    out: dict[str, list[str]] = {}
    for system, ref in meta_plate.items():
        if not isinstance(ref, str) or ref == "working":
            continue
        line = ref.split("#")[0]
        try:
            items = await plate_client.list_line_revisions(system, line)
        except Exception:  # noqa: BLE001 — 提示降级,不阻塞
            continue
        refs = sorted({r for r in (_rev_id(i) for i in items) if r})
        if refs:
            out.setdefault(line, refs)
    return out


async def _free_scenario_id(db) -> str:
    for _ in range(20):
        cand = f"sc-import-{secrets.token_hex(3)}"
        hit = (await db.execute(
            select(ComposerScenario.scenario_id).where(
                ComposerScenario.scenario_id == cand)
        )).scalar_one_or_none()
        if hit is None:
            return cand
    raise ImportRejected(
        "internal_error", 500, "无法生成可用场景 ID,请重试")


# ── precheck(纯读,方案 §3.1)──────────────────────────────────────


async def precheck(db, *, definition: dict, user) -> dict:
    out: dict = {
        "blocking": False, "formatError": None,
        "convert": {"ok": True, "errors": []},
        "metaPlate": {}, "availableRevisions": {},
        "idConflict": False, "suggestedId": None,
        "services": [], "authRefs": [], "workingDeclarations": [],
        "anchoring": {"anchored": [], "unresolved": []},
    }
    meta_plate = (definition.get("meta") or {}).get("plate") or {}
    if not isinstance(meta_plate, dict) or not meta_plate:
        raise ImportRejected(
            "meta_plate_required", 422, "文件缺 meta.plate(R19:须声明精确修订)")

    out["metaPlate"] = meta_plate
    # convert = 结构校验唯一权威;plate 不可达 → 502(方案 D6:导入无执行
    # 期兜底机会,比普通保存严是刻意的)
    try:
        await plate_client.convert(definition)
    except plate_client.PlateRejectedError as e:
        out["blocking"] = True
        out["convert"] = {"ok": False, "errors": [str(e)]}
        return out
    except plate_client.PlateUnavailableError as e:
        raise ImportRejected("plate_unavailable", 502, e.message) from e
    # refs 存在性:缺失 → 阻塞 + 可选修订集(方案 D4 的可操作性)。
    # 注意 validate_meta_plate_refs 的拒收形态是 ValueError(带
    # meta_plate_invalid_ref 前缀),plate 不可达抛 PlateUnavailableError。
    try:
        await plate_client.validate_meta_plate_refs(meta_plate)
    except ValueError as e:
        out["blocking"] = True
        out["convert"] = {"ok": False, "errors": [str(e)]}
        out["availableRevisions"] = await _available_revisions(meta_plate)
        return out
    except plate_client.PlateUnavailableError as e:
        raise ImportRejected("plate_unavailable", 502, e.message) from e

    out["workingDeclarations"] = sorted(
        s for s, ref in meta_plate.items() if ref == "working")

    # 重锚定(2026-10-15 #323):可执行形态的无锚点步骤回填 endpoint。
    # 之后的析出分析(services/authRefs)与 land 落库同源 —— 都在锚定
    # 后的形态上算;报告随信封返回,unresolved 步骤落库后执行将走
    # carry 降级门控(该服务绑定全表注入),确认界面应予提示。
    try:
        definition, anchor_report = (
            await endpoint_anchoring.reanchor_import_definition(definition))
    except plate_client.PlateUnavailableError as e:
        raise ImportRejected("plate_unavailable", 502, e.message) from e
    out["anchoring"] = {
        "anchored": [r for r in anchor_report
                     if endpoint_anchoring.is_anchored(r)],
        "unresolved": [r for r in anchor_report
                       if not endpoint_anchoring.is_anchored(r)],
    }

    sid = definition.get("scenarioId") or ""
    if sid and (await db.execute(
        select(ComposerScenario.scenario_id).where(
            ComposerScenario.scenario_id == sid)
    )).scalar_one_or_none() is not None:
        out["idConflict"] = True
        out["suggestedId"] = await _free_scenario_id(db)

    out["services"] = await analyze_services(db, definition)
    out["authRefs"] = await auth_refs(db, definition, user.id)
    return out


async def analyze_services(db, definition: dict) -> list[dict]:
    """按服务键析出分析(方案 §3.1 组装表;plate 依赖在事务外取完)。

    计数与落库共用 :func:`_service_plan`(§1 修复:预检看到的 = 落库
    要执行的)。顶层 ``fieldsToAlias``/``fieldsKeptLiteral`` 是**建议
    决策**下的计数;``countsByDecision`` 给出 create/map/reuse 三套
    (复盘 2026-10-15:用户切换决策后接管面不同 —— 本机无值时 map 接
    管 0 条、create 却会写 N 条 —— 确认界面按当前选择显示,确认的
    内容与实际执行保持一致)。``fieldsKeptLiteral`` 含两类:接管判定
    后保留的(敏感/本机缺值)+ 一致性判定不过的(各步取值不一致,
    ``inconsistentPaths`` 逐条列出供确认界面展示)。
    """
    raw_steps = list(definition.get("steps") or [])
    if not raw_steps:
        return []
    ctx = await build_carry_context(db, definition, ui_field_states={})
    catalog = await service_names.catalog_service_names()
    alias_names = set((await db.execute(
        select(ServiceAlias.alias_name))).scalars().all())

    def _counts(plan: dict) -> dict:
        return {
            "fieldsToAlias": len(plan["provider"]),
            "fieldsKeptLiteral": (len(plan["consistent"])
                                  - len(plan["provider"])
                                  + len(plan["inconsistent"])),
        }

    out: list[dict] = []
    for svc in referenced_services(
            [s for s in raw_steps if isinstance(s, dict)]):
        exists = svc in alias_names or svc in catalog
        plans = {d: _service_plan(ctx, raw_steps, svc, d)
                 for d in ("create", "map", "reuse")}
        if exists:
            # P7-⑤ 路径级复用判定(一致集上,consistent 与决策无关):
            # 全部路径本机有值且相等 → 复用;否则映射(本机为准),
            # 缺值路径保留字面值
            consistent = plans["map"]["consistent"]
            matched = {
                p for p, v in consistent.items()
                if _local_value(ctx, svc, p) is not _MISSING
                and _local_value(ctx, svc, p) == v}
            suggestion = ("reuse"
                          if consistent and matched == set(consistent)
                          else "map")
        else:
            suggestion = "create"
        provider = plans[suggestion]["provider"]
        out.append({
            "serviceKey": svc,
            "suggestion": suggestion,
            "localAlias": svc if exists else None,
            "fieldsToAlias": len(provider),
            "fieldsKeptLiteral": _counts(plans[suggestion])["fieldsKeptLiteral"],
            "countsByDecision": {d: _counts(plans[d])
                                 for d in ("create", "map", "reuse")},
            "inconsistentPaths": sorted(plans[suggestion]["inconsistent"]),
            "createNameAvailable": (
                svc not in alias_names
                and service_names.derive_base(svc, catalog) is not None),
            "sensitivePaths": sorted(plans[suggestion]["sensitive"]),
        })
    return out


async def auth_refs(db, definition: dict, owner_id: int) -> list[dict]:
    """认证引用栏数据(P7-③):${auth.*} tag × 导入人凭证池(有/无)。"""
    from ..models import AuthSession
    from .auth_ref_scan import scan_auth_aliases

    tags = scan_auth_aliases(definition.get("steps") or [])
    if not tags:
        return []
    pool = set((await db.execute(
        select(AuthSession.alias).where(AuthSession.owner_id == owner_id)
    )).scalars().all())
    return [{"tag": t, "inMyPool": t in pool} for t in tags]


# ── land(单事务落库,方案 §3.3)────────────────────────────────────


async def land(
    db, *, definition: dict, mappings: list[dict] | None,
    id_mode: str, new_id: str | None, user,
) -> dict:
    """一次性落库。plate 依赖(面/目录/convert)在事务外取完(P7-④),
    事务内只做本地读写;任何冲突整体回滚。

    mappings 项:{serviceKey, decision: reuse|map|create, createName?,
    credentialAlias?}——**无值覆盖字段**(P7-⑥:非敏感值照文件、敏感值
    不进 carry,均无用户改写)。
    """
    by_key: dict[str, dict] = {}
    for m in mappings or []:
        if (not isinstance(m, dict) or m.get("decision") not in
                ("reuse", "map", "create") or not m.get("serviceKey")):
            raise ImportRejected("invalid_file", 422, f"非法映射项: {m!r}")
        by_key[m["serviceKey"]] = m

    # ── 事务外:plate 调用(P7-④)──────────────────────────────────
    try:
        await plate_client.convert(definition)
    except plate_client.PlateRejectedError as e:
        raise ImportRejected(
            "convert_rejected", 422, f"按声明修订校验失败: {e}") from e
    except plate_client.PlateUnavailableError as e:
        raise ImportRejected("plate_unavailable", 502, e.message) from e
    meta_plate = (definition.get("meta") or {}).get("plate") or {}
    if isinstance(meta_plate, dict) and meta_plate:
        try:
            await plate_client.validate_meta_plate_refs(meta_plate)
        except plate_client.PlateUnavailableError:
            pass  # 导入路径 plate 不可达已在 convert 处 502,这里不会走到
        except ValueError as e:
            raise ImportRejected("meta_plate_invalid_ref", 422, str(e)) from e
    # 注:create_in_transaction 内的 enforce_meta_plate 会再验一次 refs
    # (与常规创建同路径,store 唯一写入口收口⑥ 的既有契约,幂等读)。

    # 重锚定(2026-10-15 #323):无锚点可执行步骤按 (service, method,
    # path) 反查回填 endpoint —— 不锚则 dispatch 的 carry 降级门控会把
    # 服务绑定全表灌进每个请求体。剥离 binding 派生字段由
    # create_in_transaction 的 strip_binding_fields 收口,此处只加锚;
    # 下方 carry 析出/清除计划随之自然在锚定形态上工作(无锚点步骤
    # 本就"没有面,谈不上接管",两条路径口径一致)。plate 不可达上抛
    # 502(convert 同口径 — 静默不锚 = 落库后必踩降级门控)。
    try:
        definition, _anchor_report = (
            await endpoint_anchoring.reanchor_import_definition(definition))
    except plate_client.PlateUnavailableError as e:
        raise ImportRejected("plate_unavailable", 502, e.message) from e

    steps = [s for s in (definition.get("steps") or []) if isinstance(s, dict)]
    raw_steps = list(definition.get("steps") or [])
    ctx = await build_carry_context(db, definition, ui_field_states={})
    catalog = await service_names.catalog_service_names()

    # ── 本地重算(不信任预检快照;方案 §3.3)───────────────────────
    alias_names = set((await db.execute(
        select(ServiceAlias.alias_name))).scalars().all())

    sid = definition.get("scenarioId") or ""
    if id_mode == "new":
        if not new_id or not _SCENARIO_ID_RE.match(new_id):
            raise ImportRejected(
                "invalid_file", 422, "newId 不合法(须 ^sc-[a-z0-9-]+$)")
        sid = new_id
    if (await db.execute(
        select(ComposerScenario.scenario_id).where(
            ComposerScenario.scenario_id == sid)
    )).scalar_one_or_none() is not None:
        raise ImportRejected(
            "scenario_id_exists", 409, f"场景 ID {sid} 已存在")

    eff_key: dict[str, str] = {}      # 原服务键 → 生效键(create 换名时变)
    for key, m in by_key.items():
        if m["decision"] == "create":
            name = m.get("createName") or key
            if name in alias_names:
                raise ImportRejected(
                    "alias_name_taken", 409, f"别名 {name} 已存在(重预检)")
            if service_names.derive_base(name, catalog) is None:
                raise ImportRejected(
                    "mapping_stale", 409,
                    f"别名 {name!r} 不落在 plate 服务目录内(重预检)")
            eff_key[key] = name
        else:
            if key not in alias_names and key not in catalog:
                raise ImportRejected(
                    "mapping_stale", 409, f"服务 {key} 本机已不存在(重预检)")
            eff_key[key] = key

    # ── 清除计划(P5:有接管者才清除;§1 修复:一致性先行 + 按步骤)──
    # 接管集与预检计数共用 _service_plan(唯一真源)。粒度 =
    # (step_index, path):只清该步骤**自己 carry 面**上、且在接管集内
    # 的路径 —— 取值不一致的路径不进接管集(三种决策一致,保留字面
    # 值),无锚点/ext: 步骤没有面,永不被清。
    plan_by_key: dict[str, dict] = {}
    provider_by_key: dict[str, set[str]] = {}
    for key, m in by_key.items():
        plan = _service_plan(ctx, raw_steps, key, m["decision"])
        plan_by_key[key] = plan
        provider_by_key[key] = plan["provider"]
    clear_by_step: dict[int, set[str]] = {}
    for i, step in enumerate(raw_steps):
        if not isinstance(step, dict):
            continue
        call = step.get("call")
        svc = call.get("service") if isinstance(call, dict) else None
        if svc not in provider_by_key:
            continue
        face = ctx.step_fields.get(i) or {}
        hit = provider_by_key[svc] & set(face)
        if hit:
            clear_by_step[i] = hit

    # ── definition 改写(纯内存)──────────────────────────────────
    defn = json.loads(json.dumps(definition))  # 深拷贝,不碰请求原对象
    defn["scenarioId"] = sid
    meta = dict(defn.get("meta") or {})
    meta["scenarioId"] = sid
    defn["meta"] = meta
    config = dict(defn.get("config") or {})
    # config.users 清空(P2:明文凭证不落库)
    config.pop("users", None)
    services_cfg = dict(config.get("services") or {})
    # body 字面值清除(P5:仅清除集内路径)—— 按 (step_index, path) 计
    # 划执行,索引与 step_fields 同一原始列表(T8 对齐);先于
    # call.service 改写(接管集按原服务键索引)
    for i, step in enumerate(defn.get("steps") or []):
        hit = clear_by_step.get(i)
        if not hit:
            continue
        body = _step_body(step)
        if body is None:
            continue
        for path in hit:
            _delete_path(body, _path_segs(path))
    for key, new_name in eff_key.items():
        if new_name == key:
            continue
        # create 换名:call.service 与 config.services 键同步改写
        if key in services_cfg:
            services_cfg[new_name] = services_cfg.pop(key)
        for step in defn.get("steps") or []:
            call = step.get("call") if isinstance(step, dict) else None
            if isinstance(call, dict) and call.get("service") == key:
                call["service"] = new_name
    # URL 清除同一不变量:本机别名有 base_url 才清,否则保留源 URL
    # (扫全部被引用服务键,不限映射集 —— 本机别名接管 URL 与 carry 析出
    # 的映射决策是两件事)
    base_urls = {row[0]: row[1] for row in (await db.execute(
        select(ServiceAlias.alias_name, ServiceAlias.base_url))).all()}
    for key in referenced_services(steps):
        if base_urls.get(key):
            services_cfg.pop(key, None)
    config["services"] = services_cfg
    defn["config"] = config

    # ── 复验:改写后的 definition 再过一次 convert(合入评估 §3)──
    # 首次 convert 验的是原始文件;落库的是改写后的形态(剥 config.users/
    # 清字面值/换服务名)。校验输入镜像 create_in_transaction 的存储管线
    # (剥平台 meta.scenarioId 等非 M2 键与 binding 派生字段)—— 真
    # plate 的 Scenario 禁 meta extra 键,不剥会把落库前的过渡形态误报
    # 为拒收(回环测试真 plate 面抓到过)。仍在事务外(P7-④)。
    check_defn = scenario_store._strip_user_view_keys(
        scenario_store.strip_binding_fields({
            **defn,
            "meta": scenario_store._strip_platform_meta(
                defn.get("meta") or {}),
        }))
    try:
        await plate_client.convert(check_defn)
    except plate_client.PlateRejectedError as e:
        raise ImportRejected(
            "convert_rejected", 422,
            f"接管改写后校验失败: {e}") from e
    except plate_client.PlateUnavailableError as e:
        raise ImportRejected("plate_unavailable", 502, e.message) from e

    # ── 单事务本地写(P7-④ 之后:无 plate 调用)───────────────────
    created_aliases: list[str] = []
    try:
        for key, m in by_key.items():
            if m["decision"] != "create":
                continue
            name = eff_key[key]
            await alias_svc.create_alias_in_transaction(
                db, alias_name=name, owner_user_id=user.id,
                credential_alias=m.get("credentialAlias"),
                catalog_names=catalog)
            alias_names.add(name)
            created_aliases.append(name)
            # carry 写接管集内的一致字面值(P7-②:敏感/不一致路径不落)
            entries = {p: v for p, v in plan_by_key[key]["consistent"].items()
                       if p in provider_by_key[key]}
            if entries:
                await carry_store_put(db, name, entries, user)
    except IntegrityError as e:
        # 预检后到落库前的建名竞态:主键撞车映射 409(前端自愈链自动
        # 重预检);回滚保证部分写入的别名/carry 不残留
        await db.rollback()
        raise ImportRejected(
            "alias_name_taken", 409,
            f"别名 {eff_key.get(key, '')!r} 已被占用(重预检)") from e

    draft = ScenarioDraft(definition=defn)
    try:
        row = await scenario_store.create_in_transaction(
            db, draft, owner=user.display_name or user.username,
            owner_id=user.id)
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise ImportRejected(
            "scenario_id_exists", 409,
            f"场景 ID {sid} 已存在") from e

    # ── 事务后:默认方案自愈 + 审计(T2:best-effort,不回滚业务)──
    from . import scheme_store
    await scheme_store.ensure_default_scheme(db, sid)
    await _write_audit(db, user=user, created_aliases=created_aliases,
                       entries_count={
                           eff_key[k]: len(v) for k, v in provider_by_key.items()
                           if by_key[k]["decision"] == "create" and v})
    await db.refresh(row)
    return {"scenarioId": row.scenario_id, "idMode": id_mode}


async def carry_store_put(db, service_name: str, entries: dict, user) -> None:
    from . import carry_store
    await carry_store.put_bindings(
        db, service_name, entries,
        updated_by_id=user.id,
        updated_by_name=user.display_name or user.username)


async def _write_audit(db, *, user, created_aliases: list[str],
                       entries_count: dict[str, int]) -> None:
    """审计后置(事务提交后写;P1 权限口径与既有别名/carry 路由一致)。"""
    from . import audit as audit_svc
    label = user.display_name or user.username
    for name in created_aliases:
        await audit_svc.record(
            db, actor_id=user.id, actor_name=label,
            action="alias.write", resource_type="alias",
            resource_id=name, resource_name=name,
            detail={"fn": "create", "source": "scenario_import"})
        if entries_count.get(name):
            await audit_svc.record(
                db, actor_id=user.id, actor_name=label,
                action="carry.write", resource_type="carry",
                resource_id=name, resource_name=name,
                detail={"service": name,
                        "source": "scenario_import"})


def _delete_path(node: Any, segs: list[str]) -> None:
    """按路径删除字面值节点(清除集专用;中间缺失 = 已无可清)。"""
    if not segs:
        return
    cur = node
    for s in segs[:-1]:
        if isinstance(cur, dict) and s in cur:
            cur = cur[s]
        else:
            return
    if isinstance(cur, dict):
        cur.pop(segs[-1], None)
