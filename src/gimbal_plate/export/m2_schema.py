"""M2 交换形态导出（M2 方案 v2.4 §4.2 规则 E1–E7；开发计划 T1.3）。

定义形态（``schema/_next``）→ 语言中立的 JSON Schema（消费投影）：

- **E1 缺省值显式化**：``default_factory=list/dict`` 的字段写出
  ``default: [] / {}``（pydantic 不为 factory 输出 default，生成侧会
  落成 None）；
- **E2 封闭性**：除 Call 外 ``additionalProperties: false``（生成侧据此
  产出 ``extra='forbid'``）；
- **E3 枚举成员名**：每个枚举写出 ``x-enum-varnames``（JSON Schema 只
  携带值；执行器代码按成员名引用，共 47 处）；
- **E4 判别联合**：保留 ``discriminator``；
- **E5 只导出消费投影**：评审信封等 plate 内部字段不进（``_next`` 定义
  本就不含）；
- **E6 规范序列化**：剥 ``title`` 等纯展示字段、键排序后计算
  ``m2_hash``（无语义改动不改变 hash）；
- **E7 内联 Literal 清单**：多值 ``Literal`` 字段与枚举同形，输出字段
  名清单供生成侧 G6 还原。

根类型（§9.3）：``RunUnion`` / ``RunOptions`` / ``ReportDefinition`` /
``SubscribeRule`` 导出进同一份 Schema 的 ``$defs``，供各消费方一次生成。
"""
from __future__ import annotations

import hashlib
import json
import typing
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, TypeAdapter

from gimbal_plate import schema as _next
from gimbal_plate.schema import (
    M2_GENERATION,
    ReportDefinition,
    RunOptions,
    RunUnion,
    SubscribeRule,
)


class _M2Root(BaseModel):
    """导出壳：把四个根类型拉进同一份 Schema 的 ``$defs``。不进消费面。"""

    run: RunUnion
    options: RunOptions | None = None
    report: ReportDefinition | None = None
    subscribe: SubscribeRule | None = None


@dataclass(frozen=True)
class M2Export:
    schema: dict                 # 交换形态（E1–E5 已应用）
    m2_hash: str                 # E6 规范序列化后的 sha256
    m2_generation: int           # 取自 gimbal_plate.schema._next.M2_GENERATION
    literal_fields: list[str]    # E7


def _strip_titles(node: Any, *, in_properties: bool = False) -> Any:
    """E6：递归剥掉纯展示字段（JSON Schema 的 title 键；description 保留）。
    ``properties`` 内的 ``title`` 是**字段名**（如 ReportPresentation.title），
    不得剥除——只处理 properties 值的子树。"""
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k == "title" and not in_properties:
                continue          # JSON Schema 的展示 title
            out[k] = _strip_titles(v, in_properties=(k == "properties"))
        return out
    if isinstance(node, list):
        return [_strip_titles(x) for x in node]
    return node


def _jsonable(v: Any) -> Any:
    """default 值归一为 JSON 可序列化形态（嵌套模型 → dict、枚举 → 值）。"""
    if isinstance(v, BaseModel):
        return v.model_dump(mode="json")
    if isinstance(v, __import__("enum").Enum):
        return v.value
    return v


def _apply_e1_defaults(schema: dict) -> None:
    """E1：default_factory 字段显式写 default。$defs[模型名] ↔ 类名。"""
    for def_name, spec in schema.get("$defs", {}).items():
        cls = getattr(_next, def_name, None)
        if cls is None or not hasattr(cls, "model_fields"):
            continue
        props = spec.get("properties") or {}
        for fname, field in cls.model_fields.items():
            if fname in props and "default" not in props[fname]:
                if field.default_factory is not None:
                    try:
                        default = _jsonable(
                            field.get_default(call_default_factory=True))
                    except Exception:  # noqa: BLE001 — 工厂失败保守跳过
                        continue
                    props[fname]["default"] = default


def _apply_e2_closedness(schema: dict) -> None:
    """E2：除 Call（唯一开放模型）外全部 additionalProperties: false。"""
    for def_name, spec in schema.get("$defs", {}).items():
        if def_name == "Call":
            continue
        if spec.get("type") == "object" or "properties" in spec:
            spec.setdefault("additionalProperties", False)


def _enum_registry() -> dict[tuple, list[str]]:
    """(成员值元组) → [成员名]（定义序）。值集合唯一的枚举可直接匹配。"""
    out: dict[tuple, list[str]] = {}
    for name in dir(_next):
        obj = getattr(_next, name)
        if isinstance(obj, type) and issubclass(obj, __import__("enum").Enum):
            values = tuple(m.value for m in obj)
            out.setdefault(values, [m.name for m in obj])
    return out


def _apply_e3_varnames(schema: dict, enums: dict[tuple, list[str]]) -> None:
    """E3：枚举值处补 x-enum-varnames（生成侧还原成员名）。"""

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("enum"), list):
                key = tuple(node["enum"])
                if key in enums:
                    node["x-enum-varnames"] = enums[key]
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for x in node:
                walk(x)

    walk(schema)


def _literal_fields() -> list[str]:
    """E7：多值 Literal 字段名清单（与枚举在 Schema 中同形，G6 据此还原
    为 Literal 而非 Enum）。"""
    out: set[str] = set()
    for name in dir(_next):
        cls = getattr(_next, name)
        if not (isinstance(cls, type) and issubclass(cls, BaseModel)):
            continue
        for fname, field in cls.model_fields.items():
            ann = field.annotation
            # Optional[Literal[...]] 先解包（bracket 类字段）
            if typing.get_origin(ann) is typing.Union:
                non_none = [a for a in typing.get_args(ann)
                            if a is not type(None)]
                if len(non_none) == 1:
                    ann = non_none[0]
            origin = typing.get_origin(ann)
            if origin is typing.Literal or (origin is not None and
                                            str(origin) == "typing.Literal"):
                args = [a for a in typing.get_args(ann)
                        if isinstance(a, str)]
                if len(args) > 1:
                    out.add(fname)
    return sorted(out)


def export_m2() -> M2Export:
    """定义形态 → 交换形态（E1–E7 全应用，内容寻址 hash）。"""
    schema = TypeAdapter(_M2Root).json_schema()
    _apply_e1_defaults(schema)
    _apply_e2_closedness(schema)
    _apply_e3_varnames(schema, _enum_registry())
    schema = _strip_titles(schema)          # E6：剥展示字段后再算 hash
    canonical = json.dumps(schema, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode("utf-8")
    return M2Export(
        schema=schema,
        m2_hash=hashlib.sha256(canonical).hexdigest(),
        m2_generation=M2_GENERATION,
        literal_fields=_literal_fields(),
    )


__all__ = ["M2Export", "export_m2"]
