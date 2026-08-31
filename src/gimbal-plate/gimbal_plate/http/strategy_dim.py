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

from gimbal_plate.schema.strategy import Assertion, Assign, Extract, StrategyBase

# kind 清单: 显式枚举三个可编排策略。
# strategy_ref 是预埋字段(待重新设计,用户 2026-08-17 拍板),整条排除 ——
# union 定义原样保留;后续重设计后去掉排除即自动进菜单。
_KIND_MODELS: dict[str, type] = {
    "extract": Extract,
    "assign": Assign,
    "assertion": Assertion,
}

# kind 元数据: (中文 label, phase 归属)。schema 未编码这两者,在此单一维护;
# 后续想精致可给 strategy.py 的 Field 加 description=,由内省自动带出。
_KIND_LABELS: dict[str, tuple[str, str]] = {
    "extract": ("从响应提取变量", "after_request"),
    "assign": ("准备入参赋值", "before_request"),
    "assertion": ("响应断言", "verifying"),
}

# StrategyBase 公共字段名集 —— 用于 base_fields / fields 拆分。
_BASE_FIELD_NAMES: frozenset[str] = frozenset(StrategyBase.model_fields.keys())


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
    / array|object→json / else unknown。接受现成 schema 而非 model 内省 ——
    Enum 字段的 ``$ref`` 必须先展开(见 ``_resolve_enum_refs``),从 model
    现生成会重新拿到未解析的原始形态(2026-08-17 实测踩坑;原
    ``_bindings_from_model`` 内省路线已随 model 机制退役,2026-08-31)。
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
        self._descriptors: dict[str, _KindDescriptor] = {
            k: d for k in (_KIND_MODELS) if (d := _descriptor_for(k)) is not None
        }

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


# strategy_ref 有意不在 _KIND_MODELS 中 —— 见模块 docstring(预埋,待重设计)。

__all__ = ["StrategyIndex", "_KindDescriptor", "_descriptor_for", "_KIND_LABELS"]
