"""fin 系统各接口 request/response body 的具体 pydantic 类。

按 V3 PLATE_V3_DESIGN.md §3 第二条:接口的真实请求/响应结构,通过组合
(挂载到 RequestSpec.model / ResponseSpec.model)与 EndpointSpec 拼成该
系统的完整真实数据类。本模块只定义 body 模型,不继承 schema 层任何类。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class CreateOrderRequest(BaseModel):
    """fin.settlement.create_order 的请求 body。"""

    model_config = {"extra": "forbid"}

    order_id: str = Field(..., min_length=1, description="业务订单号")
    amount: int = Field(..., gt=0, description="结算金额,单位分")
    currency: str = Field(default="CNY", description="币种")


class CreateOrderResponse(BaseModel):
    """fin.settlement.create_order 的 200 响应 body。"""

    model_config = {"extra": "forbid"}

    order_id: str
    status: str
    created_at: str


class QueryBalanceResponse(BaseModel):
    """fin.account.query_balance 的 200 响应 body。"""

    model_config = {"extra": "forbid"}

    account_id: str
    balance: int = Field(..., ge=0, description="账户余额,单位分")
    currency: str = "CNY"
    as_of: str


class OrderEntrustOrderAddRequest(BaseModel):
    """fin.order_entrust.order_add 的请求 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    placeholder: str = Field(default="__pending__", description="待从 scenario 同步")


class OrderEntrustOrderAddResponse(BaseModel):
    """fin.order_entrust.order_add 的 200 响应 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    data: dict | None = Field(default=None, description="原始响应数据透传")

class OrderEntrustOrderPageRequest(BaseModel):
    """fin.order_entrust.order_page 的请求 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    placeholder: str = Field(default="__pending__", description="待从 scenario 同步")


class OrderEntrustOrderPageResponse(BaseModel):
    """fin.order_entrust.order_page 的 200 响应 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    data: dict | None = Field(default=None, description="原始响应数据透传")

class OrderOrderAddRequest(BaseModel):
    """fin.order.order_add 的请求 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    placeholder: str = Field(default="__pending__", description="待从 scenario 同步")


class OrderOrderAddResponse(BaseModel):
    """fin.order.order_add 的 200 响应 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    data: dict | None = Field(default=None, description="原始响应数据透传")

class OrderOrderDetailRequest(BaseModel):
    """fin.order.order_detail 的请求 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    placeholder: str = Field(default="__pending__", description="待从 scenario 同步")


class OrderOrderDetailResponse(BaseModel):
    """fin.order.order_detail 的 200 响应 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    data: dict | None = Field(default=None, description="原始响应数据透传")

class OrderOrderPageRequest(BaseModel):
    """fin.order.order_page 的请求 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    placeholder: str = Field(default="__pending__", description="待从 scenario 同步")


class OrderOrderPageResponse(BaseModel):
    """fin.order.order_page 的 200 响应 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    data: dict | None = Field(default=None, description="原始响应数据透传")

class OrderOrderBookRequest(BaseModel):
    """fin.order.order_book 的请求 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    placeholder: str = Field(default="__pending__", description="待从 scenario 同步")


class OrderOrderBookResponse(BaseModel):
    """fin.order.order_book 的 200 响应 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    data: dict | None = Field(default=None, description="原始响应数据透传")

class OrderCheckGenerateOrderSubRequest(BaseModel):
    """fin.order.check_generate_order_sub 的请求 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    placeholder: str = Field(default="__pending__", description="待从 scenario 同步")


class OrderCheckGenerateOrderSubResponse(BaseModel):
    """fin.order.check_generate_order_sub 的 200 响应 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    data: dict | None = Field(default=None, description="原始响应数据透传")

class OrderGenerateOrderSubRequest(BaseModel):
    """fin.order.generate_order_sub 的请求 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    placeholder: str = Field(default="__pending__", description="待从 scenario 同步")


class OrderGenerateOrderSubResponse(BaseModel):
    """fin.order.generate_order_sub 的 200 响应 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    data: dict | None = Field(default=None, description="原始响应数据透传")

class OrderOrderNoticeRequest(BaseModel):
    """fin.order.order_notice 的请求 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    placeholder: str = Field(default="__pending__", description="待从 scenario 同步")


class OrderOrderNoticeResponse(BaseModel):
    """fin.order.order_notice 的 200 响应 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    data: dict | None = Field(default=None, description="原始响应数据透传")

class OrderFeeToggleRealAmountRequest(BaseModel):
    """fin.order_fee.toggle_real_amount 的请求 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    placeholder: str = Field(default="__pending__", description="待从 scenario 同步")


class OrderFeeToggleRealAmountResponse(BaseModel):
    """fin.order_fee.toggle_real_amount 的 200 响应 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    data: dict | None = Field(default=None, description="原始响应数据透传")

class OrderFeeBookRealAmountEditRequest(BaseModel):
    """fin.order_fee.book_real_amount_edit 的请求 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    placeholder: str = Field(default="__pending__", description="待从 scenario 同步")


class OrderFeeBookRealAmountEditResponse(BaseModel):
    """fin.order_fee.book_real_amount_edit 的 200 响应 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    data: dict | None = Field(default=None, description="原始响应数据透传")

class OrderFeeRealAmountLockSubmitRequest(BaseModel):
    """fin.order_fee.real_amount_lock_submit 的请求 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    placeholder: str = Field(default="__pending__", description="待从 scenario 同步")


class OrderFeeRealAmountLockSubmitResponse(BaseModel):
    """fin.order_fee.real_amount_lock_submit 的 200 响应 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    data: dict | None = Field(default=None, description="原始响应数据透传")

class OrderFeeAssetPushRequest(BaseModel):
    """fin.order_fee.asset_push 的请求 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    placeholder: str = Field(default="__pending__", description="待从 scenario 同步")


class OrderFeeAssetPushResponse(BaseModel):
    """fin.order_fee.asset_push 的 200 响应 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    data: dict | None = Field(default=None, description="原始响应数据透传")

class AuditAuditPageRequest(BaseModel):
    """fin.audit.audit_page 的请求 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    placeholder: str = Field(default="__pending__", description="待从 scenario 同步")


class AuditAuditPageResponse(BaseModel):
    """fin.audit.audit_page 的 200 响应 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    data: dict | None = Field(default=None, description="原始响应数据透传")

class AuditAuditExecuteRequest(BaseModel):
    """fin.audit.audit_execute 的请求 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    placeholder: str = Field(default="__pending__", description="待从 scenario 同步")


class AuditAuditExecuteResponse(BaseModel):
    """fin.audit.audit_execute 的 200 响应 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    data: dict | None = Field(default=None, description="原始响应数据透传")

class AuditAuditDetailRequest(BaseModel):
    """fin.audit.audit_detail 的请求 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    placeholder: str = Field(default="__pending__", description="待从 scenario 同步")


class AuditAuditDetailResponse(BaseModel):
    """fin.audit.audit_detail 的 200 响应 body。"""

    model_config = {"extra": "forbid"}

    # TODO 由 Scenario_Test_14 提取的字段清单补充
    data: dict | None = Field(default=None, description="原始响应数据透传")

