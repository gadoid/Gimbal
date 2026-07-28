"""gimbal_plate.schema.base —— 非 Step 的基础公共类型。

包含状态枚举、引用基类、认证会话、时间策略、重试策略等。
与 ``gimbal_plate.schema.interface`` 互不依赖,可独立使用。
"""
from gimbal_plate.schema.base.states import StepState
from gimbal_plate.schema.base.ref import RefBase, Ref
from gimbal_plate.schema.base.timepolicy import (
    TimePolicy,
    TimeoutPolicy,
    RecordPolicy,
    TimePolicyUnion,
)
from gimbal_plate.schema.base.retrypolicy import RetryPolicy
from gimbal_plate.schema.base.auth import AuthSession

__all__ = [
    "StepState",
    "RefBase",
    "Ref",
    "TimePolicy",
    "TimeoutPolicy",
    "RecordPolicy",
    "TimePolicyUnion",
    "RetryPolicy",
    "AuthSession",
]
