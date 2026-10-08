"""schema.teardown —— 用例后置动作。"""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel


class Teardown(BaseModel):
    kind: Literal["teardown"] = "teardown"


TeardownUnion = Teardown