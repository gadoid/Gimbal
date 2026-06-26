"""逻辑 schema 路径解析器(PR-D1 / PLATE_DESIGN §2.2 + §3.4(d))。

职责:解析形如 ``"a.b.c"`` 的点分路径,在给定 Pydantic 模型树中找到终点类型。
本解析器是 ``FieldBinding`` 静态校验(PR-D2)的唯一复杂依赖,故独立 PR、单测锁死行为。

设计要点(对应 PLATE_DESIGN §2.2 + §3.4(d)):
  * **透明穿过 list[X]** — 进入 ``X``,不带下标(91% 真值血缘穿过 list)
  * **透明穿过 dict[str, V]** — 进入 ``V``,不带具体键(币种/业务维度键)
  * **透明穿过 Optional[T] / T | None** — 进入 ``T``
  * **透明穿过 Annotated[T, ...]** — 进入 ``T``
  * **Any 区域降级** — 遇 Any 标记 ``hit_any=True``,**不**报错(无法证伪)
  * **Union[A, B, ...] 多态** — 解析器无法静态选,返回 ``error``
  * **空路径** = 根类型本身

业务价值:
  * PR-D2 ``FieldBinding`` 静态校验:每条 ``field_path`` 必须能在本接口
    ``request`` 模型树中解析到
  * PR-D4 referential integrity check:``source_field_path`` 跨端点对照
  * Phase 3 Plate-MCP:binding 查询时验证路径
  * Phase 4 CT 主动保活:drift 检测对照 schema 变化
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel


# ════════════════════════════════════════════════════════════════════════════
# 解析结果
# ════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class Resolved:
    """逻辑路径解析结果。

    字段语义:
      target_type: 路径终点类型;None = 不可解析(Any 区域或出错)
      hit_any: 路径是否穿过 Any(软提示 — Any 区域无法证伪,降级放行)
      path: 原路径(诊断用)
      error: 不可解析原因(诊断用);None = 无错

    状态空间:
      (target_type=T,  hit_any=False, error=None)  → 严格解析成功
      (target_type=None, hit_any=True, error=None) → Any 区域软降级
      (target_type=None, hit_any=False, error="…")  → 硬错误(路径错/类型不支持)
    """

    target_type: type | None
    hit_any: bool
    path: str
    error: str | None


# ════════════════════════════════════════════════════════════════════════════
# 公开 API
# ════════════════════════════════════════════════════════════════════════════


def resolve_logical_path(
    root: type[BaseModel],
    path: str,
) -> Resolved:
    """在 ``root`` 模型树中按 ``path``(点分)解析终点类型。

    解析规则(对应 PLATE_DESIGN §2.2 表格):
      * 空路径 = 根类型本身
      * BaseModel 节点:进入 ``model_fields[name]``
      * ``list[T]`` / ``List[T]``:进入 ``T``
      * ``dict[str, V]`` / ``Dict[str, V]``:进入 ``V``
      * ``Optional[T]`` / ``T | None`` / ``Union[T, None]``:进入 ``T``
      * ``Annotated[T, ...]`` / ``Final[T]``:进入 ``T``
      * ``Union[A, B, ...]``(非 Optional):返回 ``error``(多态不可静态选)
      * ``Any``:标记 ``hit_any=True``,**不**报错(软降级)
      * 字段不存在 / 期望 BaseModel 收到非 BaseModel:返回 ``error``
    """
    # 1. 空路径 = 根
    if path == "":
        return Resolved(target_type=root, hit_any=False, path=path, error=None)

    # 2. 拆分
    parts = path.split(".")
    current: Any = root

    # 3. 逐步解析
    for part in parts:
        # 3a. 期望 BaseModel,实际不是 → 硬错
        if not _is_basemodel_subclass(current):
            return Resolved(
                target_type=None,
                hit_any=False,
                path=path,
                error=(
                    f"路径 {part!r} 处期望 BaseModel,"
                    f"实际 {type(current).__name__}"
                ),
            )
        # 3b. 字段不存在 → 硬错
        if part not in current.model_fields:  # type: ignore[attr-defined]
            return Resolved(
                target_type=None,
                hit_any=False,
                path=path,
                error=f"字段 {part!r} 不在 {current.__name__} 中",
            )
        # 3c. 进入字段
        annotation = current.model_fields[part].annotation  # type: ignore[attr-defined]
        current = _unwrap(annotation)
        # 3d. 遇 Any → 软降级
        if current is Any:
            return Resolved(
                target_type=None, hit_any=True, path=path, error=None
            )

    return Resolved(target_type=current, hit_any=False, path=path, error=None)


# ════════════════════════════════════════════════════════════════════════════
# 内部辅助
# ════════════════════════════════════════════════════════════════════════════


def _is_basemodel_subclass(obj: Any) -> bool:
    """判断 obj 是不是 BaseModel 子类(type 且 issubclass)。"""
    return isinstance(obj, type) and issubclass(obj, BaseModel)


def _unwrap(annotation: Any) -> Any:
    """透明解 ``Optional[T]`` / ``list[T]`` / ``dict[str, V]`` / ``Annotated[T, ...]``。

    业务规则(对应 PLATE_DESIGN §2.2 表格):
      * ``Union[T, None]`` (Optional):取 T(单值)
      * ``Union[A, B, ...]`` (多态):**原样返回**(解析器不会处理,留给上层)
      * ``list[T]`` / ``List[T]``:取 T(元素)
      * ``dict[str, V]`` / ``Dict[str, V]``:取 V(值)
      * ``Annotated[T, ...]`` / ``Final[T]``:取 T(忽略 metadata)

    边界:
      * 空参数(如 ``list`` 无 ``[T]``)原样返回
      * ``Any`` 不被解包 —— 由 ``resolve_logical_path`` 单独标记
    """
    origin = get_origin(annotation)
    args = get_args(annotation)

    # 1. Optional[T] / T | None / Union[T, None]
    if origin is Union:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _unwrap(non_none[0])
        # 多态 Union[A, B, ...] → 原样返回(不可静态选)
        return annotation

    # 2. list[T] / List[T](Python 3.8+ get_origin 统一返回 list)
    if origin is list:
        return _unwrap(args[0]) if args else annotation

    # 3. dict[str, V] / Dict[str, V](同上,统一返回 dict)
    if origin is dict:
        return _unwrap(args[1]) if len(args) > 1 else annotation

    # 4. Annotated[T, ...] / Final[T] / 其他带 origin 的泛型
    if origin is not None and args:
        return _unwrap(args[0])

    return annotation


__all__ = [
    "Resolved",
    "resolve_logical_path",
]
