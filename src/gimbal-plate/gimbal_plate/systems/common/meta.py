"""systems.common.meta —— 系统无关的 Meta 默认模板工厂。

提供 ``common_meta_template(**overrides) -> Meta``:
- 返回 schema.Meta 的实例(不是子类 — V3 §1 schema 封闭)
- 填好所有系统都共享的最低公共默认
- 调用方用 kwargs 覆盖系统专属字段(system / module / author / owner 等)

调用方传入的覆盖项必须能通过 Meta 字段验证。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from gimbal_plate.schema import Meta


def common_meta_template(**overrides: Any) -> Meta:
    """构造系统无关的 Meta 默认模板。

    最低公共默认:
        - version="1.0.0"
        - createTime=固定锚点(2026-01-01 UTC),保证跨调用 round-trip 一致
        - expire=False
        - requirementRef=[]
        - system=[]  (V3.2:list[str],空 list 表示未指定系统)

    调用方负责传入 system / module / author / owner / tags 等系统专属字段。
    """
    defaults: dict[str, Any] = {
        "version": "1.0.0",
        "createTime": datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        "expire": False,
        "requirementRef": [],
        "system": [],
    }
    defaults.update(overrides)
    return Meta(**defaults)


__all__ = ["common_meta_template"]