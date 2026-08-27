"""Pydantic schemas for the constants-pool API(常量池条目)。"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

NAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{1,64}$")


def is_literal_primitive(v: Any) -> bool:
    """literal 条目 value 仅接受 str/int/float/bool(bool 是 int 子类,先排除)。"""
    if isinstance(v, bool):
        return True
    return isinstance(v, (str, int, float))


class ConstantEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    entry_kind: Literal["literal", "generator"]
    value: Any = None
    spec: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class ConstantEntryCreateIn(BaseModel):
    name: str
    description: str = Field(default="", max_length=256)
    entry_kind: Literal["literal", "generator"]
    value: Any = None
    spec: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _check_payload(self) -> "ConstantEntryCreateIn":
        if not NAME_PATTERN.fullmatch(self.name):
            raise ValueError("name 须匹配 ^[A-Za-z0-9_]{1,64}$")
        if self.entry_kind == "literal":
            if not is_literal_primitive(self.value):
                raise ValueError("literal 条目的 value 必须是 str/int/float/bool")
            if self.spec is not None:
                raise ValueError("literal 条目不能携带 spec(value/spec 互斥)")
        else:
            if self.value is not None:
                raise ValueError("generator 条目不能携带 value(value/spec 互斥)")
            if not (
                isinstance(self.spec, dict)
                and isinstance(self.spec.get("kind"), str)
                and self.spec["kind"]
            ):
                raise ValueError("generator 条目的 spec 必须含非空字符串 kind")
        return self


class ConstantEntryPatchIn(BaseModel):
    """PATCH 语义: None = 不改(与 auth_sessions 一致);校验依赖行的 entry_kind,在 router 层做。"""

    description: str | None = Field(default=None, max_length=256)
    value: Any = None
    spec: dict[str, Any] | None = None
