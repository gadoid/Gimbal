"""schema.setup —— 用例前置动作。"""
from __future__ import annotations

from typing import Literal, Annotated, Union
from pydantic import BaseModel, Field

from gimbal_plate.schema.ref import RefBase


class Setup(BaseModel):
    kind: Literal["setup"] = "setup"


class SetupRef(RefBase):
    kind: Literal["setup_ref"] = "setup_ref"


SetupUnion = Annotated[
    Union[Setup, SetupRef],
    Field(discriminator="kind"),
]