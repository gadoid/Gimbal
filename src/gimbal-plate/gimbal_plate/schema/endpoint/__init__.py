"""gimbal_plate.schema.endpoint —— 接口契约模型的兼容门面（A2 后真源在方言层）。

M2 真源：``gimbal_plate.dialect.models``（EndpointSpec 修订版 + Binding 联合）。
方言层反向依赖本包的 io_spec / metadata / query_view 子模块,故门面用
PEP 562 惰性导出断环;``ApiSpec`` 已删除（6.2：binding 取代,全局无
ApiSpec 残留为验收项）。
"""
from __future__ import annotations

from typing import Any

from gimbal_plate.schema.endpoint.io_spec import DeclarationEntry
from gimbal_plate.schema.endpoint.metadata import EndpointMetadata
from gimbal_plate.schema.endpoint.query_view import QueryView, ValueSource

_LAZY_FROM_DIALECT = (
    "Binding", "EndpointSpec", "HttpBinding", "RequestSpec", "ResponseSpec",
)


def __getattr__(name: str) -> Any:
    if name in _LAZY_FROM_DIALECT:
        # 子模块直导(父包可能正处于部分初始化,不可 from gimbal_plate import ...)
        from gimbal_plate.dialect import models as _models

        return getattr(_models, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Binding",
    "DeclarationEntry",
    "EndpointSpec",
    "EndpointMetadata",
    "HttpBinding",
    "QueryView",
    "RequestSpec",
    "ResponseSpec",
    "ValueSource",
]
