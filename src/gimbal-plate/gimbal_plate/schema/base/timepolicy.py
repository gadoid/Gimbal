"""gimbal_plate.base.timepolicy —— 用例时间策略(超时/记录)。"""
from __future__ import annotations

from typing import Literal, Annotated, Union
from pydantic import BaseModel, Field


class TimePolicy(BaseModel):
    """时间策略抽象基类。"""

    pass


class TimeoutPolicy(TimePolicy):
    """超时模式:执行器检查每一步是否超时,超时抛异常。"""

    kind: Literal["timeout"] = "timeout"
    seconds: int = Field(description="超时阈值(秒)")


class RecordPolicy(TimePolicy):
    """记录模式:不检查超时,但记录实际耗时到运行结果。"""

    kind: Literal["record"] = "record"


TimePolicyUnion = Annotated[
    Union[TimeoutPolicy, RecordPolicy],
    Field(discriminator="kind"),
]
