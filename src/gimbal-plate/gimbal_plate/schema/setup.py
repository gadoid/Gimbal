"""schema.setup —— 用例前置动作。"""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel


class Setup(BaseModel):
    kind: Literal["setup"] = "setup"


SetupUnion = Setup