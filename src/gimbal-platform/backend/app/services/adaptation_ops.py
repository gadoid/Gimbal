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
ALL_OPS = STEP_OPS + DATASET_OPS + GLOBAL_OPS


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
