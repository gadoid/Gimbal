"""L1 序列化工具函数(PR-2.0 / PLATE_EVOLUTION §3)。

职责:
  * 端点/绑定/版本的 ``to_dict`` / ``from_dict`` 工具函数
  * byte-equal 保证(排序无关字段先排序)
  * BaseModel 引用处理(存"module.ClassName"字符串,反序列化留 None)

设计原则(对应 A2 不可变序列化):
  * 所有 list 输出用 ``sorted(...)`` 消除顺序漂移
  * 所有 dict 输出 ``sort_keys=True``
  * 反序列化严格不容错(契约不可容错)
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


def _model_ref(model: type[BaseModel] | None) -> str | None:
    """把 BaseModel 类转成可序列化字符串引用。

    格式:``"{module}.{qualname}"``,例如 ``"Plate.fin.models.AuditPageRequest"``。

    None → None(允许 None)。

    注:本 PR **不**反序列化此字段(留给 PR-2.1 协议 + PR-2.2 SDK 决定
    importlib 重建策略)。本函数只解决"to_dict 不挂"。
    """
    if model is None:
        return None
    return f"{model.__module__}.{model.__qualname__}"


def _hook_ref(hook: Any) -> str | None:
    """hook 是 Protocol 实例或 None。本 PR 范围:存引用名,反序列化留 None。"""
    if hook is None:
        return None
    cls = type(hook)
    return f"{cls.__module__}.{cls.__qualname__}"


def _sorted_responses(responses: dict[int, type[BaseModel] | None]) -> dict[str, str | None]:
    """responses 是 ``{status: BaseModel}``,序列化按 status 排序。"""
    return {str(k): _model_ref(v) for k, v in sorted(responses.items(), key=lambda kv: kv[0])}


def _sorted_response_union(
    response_union: dict[int, tuple[type[BaseModel], ...]],
) -> dict[str, list[str | None]]:
    """response_union 是 ``{status: (BaseModel, ...)}``。"""
    return {
        str(k): [_model_ref(m) for m in v]
        for k, v in sorted(response_union.items(), key=lambda kv: kv[0])
    }


__all__ = [
    "_model_ref",
    "_hook_ref",
    "_sorted_responses",
    "_sorted_response_union",
]