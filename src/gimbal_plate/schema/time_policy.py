"""M2 TimePolicy（M2 方案 v2.4 §3 M9；步骤 1 定义形态）。

以执行器为准（M9）：``None = 不限时``（plate 副本缺省值与此不一致，
已漂移）。
"""
from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class TimePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TimeoutPolicy(TimePolicy):
    """超时模式：执行器检查每一步是否超时，超时抛异常。"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["timeout"] = "timeout"
    seconds: int = Field(description="超时阈值（秒）")


class RecordPolicy(TimePolicy):
    """记录模式：不检查超时，但记录实际耗时到运行结果。"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["record"] = "record"


TimePolicyUnion = Annotated[
    Union[TimeoutPolicy, RecordPolicy],
    Field(discriminator="kind"),
]
