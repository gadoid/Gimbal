"""适配 op 纯引擎(spec §5.4):草案生成 + 收敛应用 + 步骤寻址校验。

本模块**不** import 任何 store/model/DB —— 纯函数,输入输出均为
dict/list,便于穷举测试;DB 编排(事务/存档/状态机)在
adaptation_service.py。op 形状即 §5.4 补丁契约的元素:
``{"op": <type>, "step"?: int, "from"?, "to"?, "field"?, "value"?,
"var"?, "map"?, "column"?, "datasetId"?}``。
"""
from __future__ import annotations

# step 寻址类 op(payload 带 step 索引;应用前须过 check_step_addressable)
STEP_OPS = ("renameField", "addField", "removeField", "rebindField", "mapValue")
# 仅数据集类 op(不触场景 definition;执行时 dataset_id 必填)
DATASET_OPS = ("renameDatasetColumn", "mapDatasetValues")
# 场景全局 op(改 definition 任意处 + 联动数据集列)
GLOBAL_OPS = ("renameVar",)
# carry 值表类 op(触 platform 两张值表;service 缺省 = 全局默认表)
CARRY_OPS = ("renameCarryPath", "addCarryBinding", "removeCarryBinding")
ALL_OPS = STEP_OPS + DATASET_OPS + GLOBAL_OPS + CARRY_OPS


def _field_map(spec: dict | None) -> dict[str, dict]:
    """full spec → {字段名: 字段绑定};request 缺失/形状不符 → {}。"""
    if not isinstance(spec, dict):
        return {}
    request = spec.get("request")
    fields = request.get("fields") if isinstance(request, dict) else None
    if not isinstance(fields, list):
        return {}
    return {
        str(f.get("name")): f
        for f in fields
        if isinstance(f, dict) and f.get("name")
    }


def _enum_set(field: dict) -> set[str] | None:
    """字段值域;None 或空列表视为不可枚举 → None(不足以建映射骨架)。"""
    enum = field.get("enum")
    if not isinstance(enum, list) or not enum:
        return None
    return {str(v) for v in enum}


def diff_field_specs(old_spec: dict | None, new_spec: dict | None) -> list[dict]:
    """形状 diff → 自动草案 op 列表(spec §5.4 收窄裁定)。

    只产三类:
    * ``addField``   —— 新增字段(值 = plate default,缺省 "");
    * ``removeField`` —— 字段消失;
    * ``mapValue`` 骨架 —— 同名字段两侧值域均可枚举且集合不同,
      map 留空人工补目标值。

    renameField 不可从形状 diff 推断(旧 {a,b,c} vs 新 {a,b,d} 无法区分
    "改名"与"删 c 增 d"),自动草案退化为 remove+add 对;其余 op
    (rebind/renameVar/renameDatasetColumn/mapDatasetValues)由人工经
    POST /adaptations/batches/{id}/ops 构造。
    old_spec 为 None(无旧形状缓存)→ 全部按新增处理。
    """
    old = _field_map(old_spec)
    new = _field_map(new_spec)
    drafts: list[dict] = []
    for name in sorted(set(new) - set(old)):
        default = new[name].get("default")
        drafts.append({
            "op": "addField", "field": name,
            "value": default if default is not None else "",
        })
    for name in sorted(set(old) - set(new)):
        drafts.append({"op": "removeField", "field": name})
    for name in sorted(set(old) & set(new)):
        oe, ne = _enum_set(old[name]), _enum_set(new[name])
        if oe is not None and ne is not None and oe != ne:
            drafts.append({"op": "mapValue", "field": name, "map": {}})
    return drafts


# ─── 步骤寻址与字段容器(spec §9 C5 / §3.2)─────────────────────
# 无 query 容器:plate Api schema 无此字段,引擎 GET 参数约定走 request.body。
_SOURCES = ("body", "headers")


def _containers(step: dict) -> dict[str, dict]:
    """step 的两个字段容器(可变引用):body 在 request 下,headers 在 api 下。"""
    request = step.get("request") if isinstance(step.get("request"), dict) else {}
    api = step.get("api") if isinstance(step.get("api"), dict) else {}
    out: dict[str, dict] = {}
    for source in _SOURCES:
        holder = request if source == "body" else api
        container = holder.get(source)
        out[source] = container if isinstance(container, dict) else {}
    return out


def check_step_addressable(definition: dict, op: dict, endpoint_id: str) -> str | None:
    """C5 应用期重验:op 寻址的 step 仍绑定目标 endpoint?

    返回 None = 可寻址;否则返回冲突原因(调用方写进 op.note)。
    清单生成到应用之间用户可能重排/删步骤 —— 这里挡住盲改。

    契约禁令(spec 2026-08-27 §1.6):任何 plate 目录驱动的回写(适配 ops、
    未来契约同步/导入)不得触碰 ``api.service`` —— 它是用户引用键(可為
    别名全串),``view_hints.endpoint_id`` 才是目录锚点,两权分立。
    """
    steps = definition.get("steps")
    if not isinstance(steps, list):
        return "step_missing: no steps"
    i = op.get("step")
    if not isinstance(i, int) or i < 0 or i >= len(steps):
        return f"step_missing: {i!r}"
    step = steps[i]
    api = step.get("api") if isinstance(step, dict) else None
    hints = api.get("view_hints") if isinstance(api, dict) else None
    bound = hints.get("endpoint_id") if isinstance(hints, dict) else None
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
    else:
        raise ValueError(f"not_a_scenario_op: {kind}")
    return definition


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
    else:  # pragma: no cover - STEP_OPS 已穷举
        raise ValueError(f"unknown_step_op: {kind}")


def _apply_rename_var(definition: dict, op: dict) -> None:
    """renameVar:definition 内全部 ``${var.from}`` → ``${var.to}``
    (深走字符串替换,body/headers/strategy 文本通吃)+ config.vars
    键改名。数据集列联动走 apply_to_rows(另一通路,由 service 编排)。"""
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
