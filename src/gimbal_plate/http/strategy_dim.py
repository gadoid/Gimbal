"""strategy dim —— 策略语法的服务化(第 8 个 M6 dim,语法级)。

设计: docs/superpowers/specs/2026-08-17-strategy-syntax-service-design.md

与现有 7 个数据 dim 的唯一概念差异: 本 dim 的 items **不是数据实例**,
而是从 ``StrategyUnion`` 内省出的 kind 描述符 —— 回答"策略有哪些 kind、
每个 kind 有哪些字段"。策略*实例*照旧存在 scenario 的
``steps[*].strategy`` 里,归平台管;plate 只暴露语法(结构权威源)。

依赖方向: http → schema(只读内省),与 views.py 同向,
不触碰 test_v3_no_reverse_import 锁的反向依赖。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gimbal_plate.selfdescribe import ext_snapshot

# kind 清单（§2.1 C 类快照统一出数——含 sleep 等 M2 之外的扩展策略;
# 原内省实现只见 3 个 kind、漏 sleep,是 M2 方案 §2.1 点名的缺口）
_KIND_LABELS: dict[str, tuple[str, str]] = {
    "extract": ("从响应提取变量", "after_request"),
    "assign": ("请求前赋值", "before_request"),
    "assertion": ("断言响应", "after_request"),
    "sleep": ("等待", "before_request"),
}

_KIND_MODELS: dict[str, type] = {}
# 快照表有 params_schema 的策略填入 M2 模型（extract/assign/assertion）;
# sleep 等执行器扩展策略 params_schema 由快照出（结构权威在执行器）
from gimbal_plate.schema.strategy import Assertion, Assign, Extract
_KIND_MODELS.update({
    "extract": Extract, "assign": Assign, "assertion": Assertion,
})

# StrategyBase 公共字段名集 —— 用于 base_fields / fields 拆分。
from gimbal_plate.schema.strategy import StrategyBase as _SB
_BASE_FIELD_NAMES: frozenset[str] = frozenset(_SB.model_fields.keys())


@dataclass(frozen=True)
class _KindDescriptor:
    """一个策略 kind 的完整描述符(StrategyIndex 的 item 类型)。"""

    kind: str
    label: str
    phase: str
    fields: list[dict[str, Any]]
    base_fields: list[dict[str, Any]]


def _resolve_enum_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """把属性级的 ``$ref`` 展开为内联 enum,使 ``_bindings_from_schema`` 可消费。

    Pydantic v2 对 Enum 字段(Scope / AssertOperator / FailurePolicy)在属性级
    输出 ``{"$ref": "#/$defs/X"}`` 而非内联 ``enum``(2026-08-17 实测);
    不解析会被 ``_bindings_from_schema`` 误判为 ``ui_kind=unknown``。
    ``default`` 与 ``$ref`` 是 schema sibling,展开时保留不受影响。
    """
    defs = schema.get("$defs") or {}
    props = schema.get("properties") or {}

    def _resolve(prop: dict[str, Any]) -> dict[str, Any]:
        ref = prop.get("$ref")
        if not isinstance(ref, str) or not ref.startswith("#/$defs/"):
            return prop
        name = ref[len("#/$defs/"):]
        target = defs.get(name)
        if not isinstance(target, dict):
            return prop
        merged = dict(target)
        # sibling 元数据(default / description)不被 $defs 条目覆盖
        for key in ("default", "description"):
            if key in prop:
                merged[key] = prop[key]
        return merged

    return {
        **schema,
        "properties": {k: _resolve(v) for k, v in props.items()},
    }


def _bindings_from_schema(schema: dict[str, Any]) -> list[dict[str, Any]]:
    """从(已解析 ref 的)JSON Schema 派生字段描述符 dict 列表。

    映射规则:enum→select / number→number / boolean→boolean / string→text
    / array|object→json / else unknown。入参是已解析 ref 的 schema_
    (唯一结构真源):Enum 字段的 ``$ref`` 必须先展开(见
    ``_resolve_enum_refs``)再传入,否则拿到的是未解析的原始形态。
    """
    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    out: list[dict[str, Any]] = []
    for name, prop in props.items():
        if not isinstance(prop, dict):
            continue
        t = prop.get("type")
        if "enum" in prop:
            ui = "select"
        elif t in ("integer", "number"):
            ui = "number"
        elif t == "boolean":
            ui = "boolean"
        elif t == "string":
            ui = "text"
        elif t in ("array", "object"):
            ui = "json"
        else:
            ui = "unknown"
        out.append({
            "name": name,
            "path": f"$.{name}",
            "required": name in required,
            "default": prop.get("default"),
            "description": str(prop.get("description") or ""),
            "enum": prop["enum"] if "enum" in prop else None,
            "ui_kind": ui,
        })
    return out


def _descriptor_for(kind: str) -> _KindDescriptor | None:
    model = _KIND_MODELS.get(kind)
    if model is None:
        return None
    label, phase = _KIND_LABELS[kind]
    schema = _resolve_enum_refs(model.model_json_schema())
    all_fields = _bindings_from_schema(schema)
    # 拆分: 判别字段剔除;StrategyBase 继承字段收进 base_fields(第一版前端不渲染)
    fields = [
        f for f in all_fields
        if f["name"] != "kind" and f["name"] not in _BASE_FIELD_NAMES
    ]
    base_fields = [
        f for f in all_fields
        if f["name"] != "kind" and f["name"] in _BASE_FIELD_NAMES
    ]
    return _KindDescriptor(
        kind=kind, label=label, phase=phase,
        fields=fields, base_fields=base_fields,
    )


class StrategyIndex:
    """BaseIndex 实现 —— items 是 kind 描述符(语法级 dim,非数据)。

    ``list_for_system`` 无视 system 参数返回全量: 语法是全局的,跟着 plate
    版本走而不是跟着某个系统走(config/meta/resource 已有 flat 先例)。
    registry 字段仅为对齐 BaseIndex 构造约定,不被使用。
    """

    def __init__(self, registry: Any = None) -> None:  # noqa: ARG002
        # §2.1 C 类:策略清单以快照为准——内省模型只答字段面,kind 覆盖
        # （含 sleep 等执行器扩展策略）从 executor_ext.json 的 strategy 表出
        self._descriptors: dict[str, _KindDescriptor] = {
            k: d for k in (_KIND_MODELS) if (d := _descriptor_for(k)) is not None
        }
        for entry in ext_snapshot.strategy_kinds():
            kind = str(entry.get("kind") or "")
            if kind and kind not in self._descriptors:
                # 快照独有（M2 之外的扩展策略,如 sleep）: 由 params_schema
                # 组装最小描述符（label/phase 用 _KIND_LABELS 或 kind 名）
                label, phase = _KIND_LABELS.get(kind, (kind, "before_request"))
                params_schema = entry.get("params_schema") or {}
                props = (params_schema.get("properties") or {})
                fields = [
                    {"name": str(pk), "type": str(pv.get("type") or "string"),
                     "required": pk in (params_schema.get("required") or []),
                     "default": pv.get("default"),
                     "description": str(pv.get("description") or ""),
                     "enum": pv.get("enum"),
                     "ui_kind": str(pv.get("ui_kind") or "text")}
                    for pk, pv in props.items()
                ]
                self._descriptors[kind] = _KindDescriptor(
                    kind=kind, label=label, phase=phase,
                    fields=fields, base_fields=[])

    # ── BaseIndex 契约 ──────────────────────────────────────────────

    def list_global(self, *, filters: dict[str, Any] | None = None) -> list[_KindDescriptor]:
        _ = filters
        return list(self._descriptors.values())

    def list_for_system(
        self, system: str, *, filters: dict[str, Any] | None = None
    ) -> list[_KindDescriptor]:
        _ = system, filters
        return self.list_global()

    def get(self, item_id: str) -> _KindDescriptor | None:
        return self._descriptors.get(item_id)

    def to_view(self, item: _KindDescriptor) -> dict[str, Any]:
        return {"kind": item.kind, "label": item.label, "phase": item.phase}


__all__ = ["StrategyIndex", "_KindDescriptor", "_descriptor_for", "_KIND_LABELS"]
