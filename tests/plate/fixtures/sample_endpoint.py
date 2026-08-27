"""共享的示例 EndpointSpec,供端到端测试引用。"""
from __future__ import annotations

from pydantic import BaseModel

from gimbal_plate import (
    ApiSpec,
    EndpointMetadata,
    EndpointSpec,
    IOFieldBinding,
    RequestSpec,
    ResponseSpec,
)


class OrderIn(BaseModel):
    order_no: str
    amount: float


class OrderOut(BaseModel):
    order_id: str
    order_no: str


def make_sample_endpoint() -> EndpointSpec:
    """构造一个用于端到端测试的 EndpointSpec。"""
    return EndpointSpec(
        id="sample.order.add",
        system="sample",
        service="order",
        name="样例下单",
        description="端到端测试用样例",
        api=ApiSpec(
            service="order",
            method="POST",
            path="/api/v1/sample/orders",
            timeout_seconds=10,
        ),
        request=RequestSpec(
            body_type="json",
            model=OrderIn,
            fields=[
                IOFieldBinding(name="order_no", path="order_no", required=True,
                               example="SAMPLE-001", ui_kind="text"),
                IOFieldBinding(name="amount", path="amount", required=True,
                               example=10.0, ui_kind="number"),
            ],
        ),
        responses={
            200: ResponseSpec(
                status=200,
                description="成功",
                model=OrderOut,
                fields=[
                    IOFieldBinding(name="order_id", path="order_id",
                                   required=True, ui_kind="text"),
                ],
                assertable_fields=["order_id"],
            ),
        },
        metadata=EndpointMetadata(
            module="样例",
            tags=["冒烟"],
            priority=1,
        ),
    )
