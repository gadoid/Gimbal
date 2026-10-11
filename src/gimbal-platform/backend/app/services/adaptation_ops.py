"""适配 op 纯引擎(spec §5.4):草案生成 + 收敛应用 + 步骤寻址校验。

本模块**不** import 任何 store/model/DB —— 纯函数,输入输出均为
dict/list,便于穷举测试;DB 编排(事务/存档/状态机)在
adaptation_service.py。op 形状即 §5.4 补丁契约的元素:
``{"op": <type>, "step"?: int, "from"?, "to"?, "field"?, "value"?,
"var"?, "map"?, "column"?, "datasetId"?}``。
"""
from __future__ import annotations

from .field_state_resolution import iter_flat

# step 寻址类 op(payload 带 step 索引;应用前须过 check_step_addressable)
STEP_OPS = ("renameField", "addField", "removeField", "rebindField", "mapValue",
            "renamePathParam")
# 仅数据集类 op(不触场景 definition;执行时 dataset_id 必填)
DATASET_OPS = ("renameDatasetColumn", "mapDatasetValues")
# 场景全局 op(改 definition 任意处 + 联动数据集列)
GLOBAL_OPS = ("renameVar",)
# carry 值表类 op(触 platform 两张值表;service 缺省 = 全局默认表)
CARRY_OPS = ("renameCarryPath", "addCarryBinding", "removeCarryBinding")
# 步骤结构级 op(RS4b,Release v4.4 §5.4):改 steps 数组长度/顺序,
# 同事务内联动改写场景内按步骤位置引用的数据(assertion_registry /
# ui.fieldStates / RunScheme stepTo,R30)
STRUCTURE_OPS = ("replaceEndpoint", "splitStep", "mergeSteps",
                 "insertStep", "removeStep")
ALL_OPS = (STEP_OPS + DATASET_OPS + GLOBAL_OPS + CARRY_OPS + STRUCTURE_OPS)


def _field_map(spec: dict | None) -> dict[str, dict]:
    """full spec → {字段名: 声明条目};request 缺失/形状不符 → {}。

    2026-09-05 目录化(§4.1(a)):全量目录,去通道过滤 —— iter_flat
    先序展开 children 树(容器先于子孙),diff 语义随之泛化:
    addField/removeField 对全目录生效,不再只盯 binding 面。
    旧 wire 的 ``fields`` 键不做兼容读(2026-09-02 剥离,清库重基线):
    归一化前落库的 CatalogVersion.spec_json 快照在此解析为空,
    diff 只产 addField、无 removeField —— 存量库须重跑 catalog 基线。
    """
    if not isinstance(spec, dict):
        return {}
    request = spec.get("request")
    if not isinstance(request, dict):
        return {}
    decls = request.get("declarations")
    if not isinstance(decls, list):
        return {}
    return {
        str(e["name"]): e
        for e in iter_flat(decls)
        if isinstance(e, dict) and e.get("name")
    }


def _enum_set(field: dict) -> set[str] | None:
    """字段值域;None 或空列表视为不可枚举 → None(不足以建映射骨架)。"""
    enum = field.get("enum")
    if not isinstance(enum, list) or not enum:
        return None
    return {str(v) for v in enum}


def spec_has_field_cache(spec: dict | None) -> bool:
    """旧戳是否携带可比对的字段形状(request/responses 声明树非空)。

    评审 N3:冷启动对旧 semver 戳重落基线前,须先跑字段 diff 防吞真实
    变更;但无形状缓存的旧戳(空 spec_json)没有可比对物——diff 会把
    全部字段判成 addField,因此这类戳按首见基线静默重落,不算漂移。
    """
    s = spec if isinstance(spec, dict) else None
    if not s:
        return False
    request = s.get("request")
    req_decls = (request.get("declarations") if isinstance(request, dict) else None) or []
    responses = s.get("responses")
    resp_decls = any(
        (isinstance(r, dict) and r.get("declarations"))
        for r in (responses.values() if isinstance(responses, dict) else [])
    )
    return bool(req_decls or resp_decls)


def field_match_names(field: str, path: str | None) -> tuple[str, ...]:
    """removeField/mapValue 的引用行匹配名集合:字段名 + 祖先容器名。

    倒排索引的 field_name 是 step body 的**顶层键**;契约声明是树
    (children),嵌套字段(如 ``$.address.city`` / name=city)变化时,
    step 里只有容器键 "address"。匹配集 = {字段名} ∪ {path 首段},
    使「改嵌套字段 → 引用容器的 step 也命中」;path 缺失或首段与
    字段名相同(平铺契约)时退化为精确匹配,行为与扩前逐字一致。
    """
    if not path:
        return (field,)
    seg = path[2:] if path.startswith("$.") else path
    top = seg.split(".", 1)[0].split("[", 1)[0]
    if top and top != field:
        return (field, top)
    return (field,)


# ─── 步骤寻址与字段容器(spec §9 C5 / §3.2)─────────────────────
# 无 query 容器:plate Api schema 无此字段,引擎 GET 参数约定走 request.body。
_SOURCES = ("body", "headers")


def _containers(step: dict) -> dict[str, dict]:
    """step 的两个字段容器(可变引用):body 在 request 下,headers 在 call 下。"""
    request = step.get("request") if isinstance(step.get("request"), dict) else {}
    call = step.get("call")
    call = call if isinstance(call, dict) else {}
    out: dict[str, dict] = {}
    for source in _SOURCES:
        holder = request if source == "body" else call
        container = holder.get(source)
        out[source] = container if isinstance(container, dict) else {}
    return out


def check_step_addressable(definition: dict, op: dict, endpoint_id: str) -> str | None:
    """C5 应用期重验:op 寻址的 step 仍绑定目标 endpoint?

    返回 None = 可寻址;否则返回冲突原因(调用方写进 op.note)。
    清单生成到应用之间用户可能重排/删步骤 —— 这里挡住盲改。

    契约禁令(spec 2026-08-27 §1.6):任何 plate 目录驱动的回写(适配 ops、
    未来契约同步/导入)不得触碰 ``call.service`` —— 它是用户引用键(可為
    别名全串),``step.endpoint`` 才是目录锚点,两权分立。
    """
    steps = definition.get("steps")
    if not isinstance(steps, list):
        return "step_missing: no steps"
    i = op.get("step")
    if not isinstance(i, int) or i < 0 or i >= len(steps):
        return f"step_missing: {i!r}"
    step = steps[i]
    # M3:锚点唯一 = step.endpoint(view_hints 双读已删)
    bound = step.get("endpoint") if isinstance(step, dict) else None
    if bound != endpoint_id:
        return (f"endpoint_mismatch: step bound to {bound!r}, "
                f"batch targets {endpoint_id!r}")
    return None


# ─── 收敛应用(spec §5.3:重复应用同 op 到达同一终态)───────────
def apply_to_definition(definition: dict, op: dict) -> dict:
    """把一条 op 收敛地应用到 definition(就地修改并返回同一对象)。

    调用方负责 deepcopy;step 寻址类 op 须先过 check_step_addressable。
    """
    kind = op.get("op")
    if kind in STEP_OPS:
        step = definition["steps"][op["step"]]
        _apply_step_op(step, op, definition)
    elif kind in GLOBAL_OPS:  # renameVar
        _apply_rename_var(definition, op)
    elif kind in STRUCTURE_OPS:  # RS4b 步骤结构级
        _apply_structure_op(definition, op)
    else:
        raise ValueError(f"not_a_scenario_op: {kind}")
    return definition


# ── RS4b：步骤结构级 op（Release v4.4 §5.4 / R30）──────────────────


def _rewrite_position_refs(
    definition: dict, payload: dict, *, index_map: dict[int, int | None],
) -> None:
    """步骤位置变化后改写场景内按步骤位置引用的数据（R30）。

    index_map: 旧步骤索引 → 新索引（None = 已删除/无法映射 → 标记悬空）。
    覆盖：``assertion_registry``（{stepIndex, jsonpath}）、
    ``ui.fieldStates``（按步骤位置索引）；RunScheme ``stepTo`` 由
    调用方（adaptation_service）在事务内清空（5.4）。
    """
    # 1. assertion_registry
    reg = payload.get("assertion_registry") or {}
    if isinstance(reg, dict):
        new_reg = {}
        for key, entries in reg.items():
            if not isinstance(entries, list):
                new_reg[key] = entries
                continue
            new_entries = []
            for e in entries:
                if not isinstance(e, dict):
                    continue
                loc = e.get("path")   # 条目形状:{path:{stepIndex,source,jsonpath}}
                if not isinstance(loc, dict):
                    new_entries.append(e)
                    continue
                old_idx = loc.get("stepIndex")
                if isinstance(old_idx, int):
                    new_idx = index_map.get(old_idx, old_idx)
                    if new_idx is None:
                        # 悬空——保留条目,标记 _dangling(执行预检显示)
                        e["_dangling"] = True
                    else:
                        loc["stepIndex"] = new_idx
                        e.pop("_dangling", None)
                new_entries.append(e)
            new_reg[key] = new_entries
        payload["assertion_registry"] = new_reg

    # 2. ui.fieldStates（按步骤位置索引的 dict）
    ui = payload.get("ui") or {}
    fs = ui.get("fieldStates") or {}
    if isinstance(fs, dict):
        new_fs = {}
        for key, states in fs.items():
            try:
                old_idx = int(key)
            except (ValueError, TypeError):
                new_fs[key] = states
                continue
            new_idx = index_map.get(old_idx, old_idx)
            if new_idx is not None:
                new_fs[str(new_idx)] = states
            # None → 丢弃（步骤已删）
        ui["fieldStates"] = new_fs
        payload["ui"] = ui


def _apply_structure_op(definition: dict, op: dict) -> None:
    """步骤结构级 op 的应用（改 steps 数组 + 联动引用改写）。"""
    kind = op["op"]
    steps = definition.setdefault("steps", [])
    # payload 引用（assertion_registry / ui 在 definition 外层）
    # 调用方（adaptation_service.apply_to_definition 收到的是 definition，
    # payload 在外层——此处通过 op["_payload"] 传递（service 层注入）。
    payload = op.get("_payload") or {}

    if kind == "replaceEndpoint":
        # 步骤改指向另一个接口（可以属于另一个系统）。
        # 旧步骤的场景面全部保留（request/strategy/description —— 丢掉
        # 请求体/提取变量会让下游引用断链）；call 只留场景自有字段
        # （6.2：service 引用 / 追加 headers / path_params / user），
        # 派生字段由新接口的投影提供。字段映射（fieldMapping：旧字段 →
        # 新字段）由 service 层经 renameField 管道应用（body 容器 +
        # 注入条目 + 字段状态同源改写）。
        idx = op["step"]
        new_endpoint = op["endpoint"]           # 目标接口 id
        if 0 <= idx < len(steps):
            old = steps[idx]
            old_call = old.get("call") or {}
            keep_call = {k: v for k, v in old_call.items()
                         if k in ("kind", "service", "headers",
                                  "path_params", "user")}
            new_call = (op.get("newStep") or {}).get("call") or {}
            if new_call.get("service"):
                keep_call["service"] = new_call["service"]  # 显式选的服务优先
            steps[idx] = {
                **old,
                "kind": "step",
                "endpoint": new_endpoint,
                "call": keep_call,
            }
            # meta.plate 更新（新系统加入时）：修订由 op 显式携带；
            # 不默认 working —— 未声明会在保存检查被 version_undeclared
            # 拦下（宁缺毋滥，working 会让锁定场景跟着 working 树漂移）
            system = str(new_endpoint).split(".")[0]
            meta_plate = (definition.get("meta") or {}).setdefault("plate", {})
            if system not in meta_plate and op.get("targetRevision"):
                meta_plate[system] = op["targetRevision"]

    elif kind == "splitStep":
        # 一个步骤替换为 N 个有序步骤。新步骤继承旧步骤 call 的场景
        # 自有字段（同一服务引用是最常见意图；用户可逐字段改）。
        idx = op["step"]
        new_steps = op.get("newSteps") or []
        if 0 <= idx < len(steps) and new_steps:
            old = steps[idx]
            old_call = {k: v for k, v in (old.get("call") or {}).items()
                        if k in ("kind", "service", "headers",
                                 "path_params", "user")}
            for i, ns in enumerate(new_steps):
                ns_call = dict(old_call)
                if ns.get("service"):
                    ns_call["service"] = ns["service"]
                body = ns.pop("body", None)
                if body is not None and "request" not in ns:
                    ns["request"] = {
                        "kind": "request",
                        "body": body if body != "" else {},
                    }
                ns.setdefault("request", {"kind": "request", "body": {}})
                ns.setdefault("strategy", [])
                ns["call"] = ns_call
                ns.setdefault("kind", "step")
            steps[idx:idx + 1] = new_steps
            # 引用改写:旧 idx → 新的第一步;后续步骤为新索引
            shift = len(new_steps) - 1
            index_map = {i: i + shift for i in range(idx + 1, len(steps))}
            index_map[idx] = idx  # 旧步骤映射到第一个新步骤
            _rewrite_position_refs(definition, payload, index_map=index_map)

    elif kind == "mergeSteps":
        # N 个步骤合并为一个（索引可不相邻）。合并结果占据最小索引的
        # 位置，其余被合并项删除，中间未被合并的步骤保留并相应前移。
        indices = sorted({int(i) for i in (op.get("steps") or [])})
        if indices and all(0 <= i < len(steps) for i in indices):
            merged = dict(op.get("mergedStep") or {})
            if op.get("endpoint"):
                merged["endpoint"] = op["endpoint"]    # 合并后的接口指向
            old_call = steps[indices[0]].get("call") or {}
            merged_call = {k: v for k, v in old_call.items()
                           if k in ("kind", "service", "headers",
                                    "path_params", "user")}
            if merged.get("service"):
                merged_call["service"] = merged["service"]
            merged.setdefault("kind", "step")
            merged.setdefault("strategy", [])
            merged.setdefault(
                "request", steps[indices[0]].get("request")
                or {"kind": "request", "body": {}})
            merged["call"] = merged_call
            merged.pop("service", None)
            first = indices[0]
            idx_set = set(indices)
            steps[:] = [merged if i == first else s
                        for i, s in enumerate(steps) if i == first or i not in idx_set]
            # 引用改写:被合并的 → first;first 之后每步前移
            # (移除数 = 命中数,但 first 位置保留一个合并步)
            removed_count = len(indices) - 1
            index_map = {}
            for i in range(len(steps) + removed_count):
                if i in idx_set:
                    index_map[i] = first  # 被合并的都指向合并后的步骤
                elif i > first:
                    before = sum(1 for x in indices if x < i)
                    index_map[i] = i - before + 1
                else:
                    index_map[i] = i
            _rewrite_position_refs(definition, payload, index_map=index_map)

    elif kind == "insertStep":
        # 在指定位置插入一个步骤。call 只接场景自有字段（service 由
        # 目录选择的接口带出）；派生字段由投影提供（6.2）。
        idx = op.get("at", len(steps))
        new_step = op.get("newStep") or {}
        call = {"kind": "call", "headers": {}}
        if new_step.get("service"):
            call["service"] = new_step["service"]
        new_step = {
            **{k: v for k, v in new_step.items()
               if k not in ("call", "kind")},
            "kind": "step",
            "call": call,
        }
        new_step.setdefault("request", {"kind": "request", "body": {}})
        new_step.setdefault("strategy", [])
        steps.insert(idx, new_step)
        # 引用改写:idx 及之后全部 +1
        index_map = {i: i + 1 for i in range(idx, len(steps) - 1)}
        _rewrite_position_refs(definition, payload, index_map=index_map)

    elif kind == "removeStep":
        # 删除步骤
        idx = op["step"]
        if 0 <= idx < len(steps):
            del steps[idx]
            # 引用改写:idx → None(悬空);之后全部 -1
            index_map = {idx: None}
            for i in range(idx + 1, len(steps) + 1):
                index_map[i] = i - 1
            _rewrite_position_refs(definition, payload, index_map=index_map)


# ── renamePathParam（Release v4.4 §5.4 新增字段级 op）──────────────


def _apply_step_op(step: dict, op: dict, definition: dict) -> None:
    kind = op["op"]
    containers = _containers(step)
    if kind == "renameField":
        for c in containers.values():
            if op["from"] in c and op["to"] not in c:
                c[op["to"]] = c.pop(op["from"])
    elif kind == "addField":
        # 默认落 body(请求字段主体场景);需落 headers 由人工改 op payload
        body = step.setdefault("request", {}).setdefault("body", {})
        if isinstance(body, dict) and op["field"] not in body:
            body[op["field"]] = op.get("value", "")
    elif kind == "removeField":
        for c in containers.values():
            c.pop(op["field"], None)
    elif kind == "rebindField":
        template = f"${{var.{op['var']}}}"
        for c in containers.values():
            if op["field"] in c and c[op["field"]] != template:
                original = c[op["field"]]
                c[op["field"]] = template
                vars_map = definition.setdefault("config", {}).setdefault("vars", {})
                if isinstance(vars_map, dict) and op["var"] not in vars_map:
                    vars_map[op["var"]] = original  # 原值落 vars(D8)
    elif kind == "mapValue":
        mapping = op.get("map") or {}
        for c in containers.values():
            if op["field"] in c and str(c[op["field"]]) in mapping:
                c[op["field"]] = mapping[str(c[op["field"]])]
    elif kind == "renamePathParam":
        call = step.get("call") or {}
        pp = call.get("path_params") or {}
        if op["from"] in pp and op["to"] not in pp:
            pp[op["to"]] = pp.pop(op["from"])
    else:  # pragma: no cover - STEP_OPS 已穷举
        raise ValueError(f"unknown_step_op: {kind}")


def rename_in_list(names: list, src: str, dst: str) -> list:
    """清单改名(收敛):src 在场且 dst 缺席才改;就地修改并返回同一列表。
    var_locks / var_unlocks 都按名存储,renameVar 双清单迁移共用。"""
    if src in names and dst not in names:
        names[names.index(src)] = dst
    return names


def _apply_rename_var(definition: dict, op: dict) -> None:
    """renameVar:definition 内全部 ``${var.from}`` → ``${var.to}``
    (深走字符串替换,body/headers/strategy 文本通吃)+ config.vars
    键改名 + config.var_locks 清单改名(按名存储,否则锁语义陈旧)。
    数据集列联动走 apply_to_rows(另一通路,由 service 编排)。"""
    src, dst = op["from"], op["to"]
    pattern = f"${{var.{src}}}"
    replacement = f"${{var.{dst}}}"

    def walk(node) -> None:
        if isinstance(node, dict):
            for key in list(node):
                value = node[key]
                if isinstance(value, str) and pattern in value:
                    node[key] = value.replace(pattern, replacement)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(definition)
    vars_map = (definition.get("config") or {}).get("vars")
    if isinstance(vars_map, dict) and src in vars_map and dst not in vars_map:
        vars_map[dst] = vars_map.pop(src)
    locks = (definition.get("config") or {}).get("var_locks")
    if isinstance(locks, list):
        rename_in_list(locks, src, dst)


def apply_to_rows(rows: list[dict], op: dict) -> list[dict]:
    """数据集侧 op(收敛):renameVar/renameDatasetColumn 改列名,
    mapDatasetValues 按列做值映射。就地修改并返回同一列表;调用方负责 deepcopy。"""
    kind = op.get("op")
    if kind in ("renameVar", "renameDatasetColumn"):
        src, dst = op["from"], op["to"]
        for row in rows:
            if isinstance(row, dict) and src in row and dst not in row:
                row[dst] = row.pop(src)
    elif kind == "mapDatasetValues":
        mapping = op.get("map") or {}
        column = op.get("column")
        for row in rows:
            if isinstance(row, dict) and column in row:
                key = str(row[column])
                if key in mapping:
                    row[column] = mapping[key]
    else:
        raise ValueError(f"not_a_dataset_op: {kind}")
    return rows
