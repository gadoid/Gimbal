"""gimbal_plate.interface.teardown —— 用例后置动作。"""
from __future__ import annotations

from typing import Literal, Annotated, Union
from pydantic import BaseModel, Field

from gimbal_plate.schema.base.ref import RefBase


class Teardown(BaseModel):
    kind: Literal["teardown"] = "teardown"


class TeardownRef(RefBase):
    kind: Literal["teardown_ref"] = "teardown_ref"


TeardownUnion = Annotated[
    Union[Teardown, TeardownRef],
    Field(discriminator="kind"),
]
