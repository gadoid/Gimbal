"""fin 服务:31 个 EndpointSpec 实例(单轨化,PR-C)。

本文件将 ``Plate.fin`` 从"``models.py`` + ``PATH_MODELS`` 双轨"
切到"``endpoints.py`` + 31 个 ``EndpointSpec`` 单轨"。

设计要点(PR-C / PLATE_DESIGN §1 + §2.1 + §3.3):
  * 31 个 ``EndpointSpec`` 模块级常量,供 ``registry.collect('fin')`` 拉式收集
  * 每个 spec 带 ``category`` + ``mutates_state`` 业务标注(PR-B 字段)
  * category 分布:BUSINESS = 14 / QUERY = 17 / TOOL = 0(PR-C review 拍板)
  * ``summary`` / ``tags`` 喂 mock / AI skill 上下文查询(本 PR 加最小可用版本)
  * ``response_data_models`` 字段(PR-C 新增)放 8 个精确建模的 data 模型
"""
from __future__ import annotations

from Plate.binding import FieldBinding
from Plate.spec import EndpointCategory, EndpointSpec

from .models import (
    AccountConfirmRequest,
    ApplyDetailRequest,
    ApplyPageData,
    ApplyPageRequest,
    AuditDetailData,
    AuditDetailRequest,
    AuditExecuteRequest,
    AuditPageData,
    AuditPageRequest,
    BatchDetailRequest,
    BatchOrderEditRequest,
    BookRealAmountEditRequest,
    CheckGenerateOrderSubData,
    CheckGenerateOrderSubRequest,
    CheckStep1Request,
    CheckStep2Request,
    ChangeInvoiceApplyRequest,
    CommonResponseEnvelope,
    FinancePutListData,
    FinancePutListRequest,
    GenerateOrderSubRequest,
    InvoiceAddCheckRequest,
    InvoiceAddRequest,
    OrderAddRequest,
    OrderBookRequest,
    OrderConfirmAccountData,
    OrderConfirmAccountRequest,
    OrderDetailData,
    OrderDetailRequest,
    OrderEntrustOrderAddRequest,
    OrderEntrustOrderPageData,
    OrderEntrustOrderPageRequest,
    OrderFeePageRequest,
    OrderReceiveAccountEditData,
    OrderReceiveAccountEditRequest,
    RealAmountLockSubmitRequest,
    ReceiveAccountDetailData,
    ReceiveAccountDetailRequest,
    ReceiveConfirmListRequest,
    ToggleRealAmountData,
    ToggleRealAmountRequest,
    WriteoffBatchRequest,
    WriteoffPageData,
    WriteoffPageRequest,
)


# ════════════════════════════════════════════════════════════════════════════
# 1. orderEntrust — 委托单
# ════════════════════════════════════════════════════════════════════════════

# 1.1 委托单分页查询(QUERY)
orderEntrustOrderPage = EndpointSpec(
    method="POST",
    path="/api/order/orderEntrust/orderPage",
    category=EndpointCategory.QUERY,
    mutates_state=False,
    request=OrderEntrustOrderPageRequest,
    responses={200: CommonResponseEnvelope},
    response_data_models={200: OrderEntrustOrderPageData},
    summary="委托订单分页查询",
    tags=["order", "entrust", "query"],
)

# 1.2 委托单新增(BUSINESS — 创建委托)
orderEntrustOrderAdd = EndpointSpec(
    method="POST",
    path="/api/order/orderEntrust/orderAdd",
    category=EndpointCategory.BUSINESS,
    mutates_state=True,
    request=OrderEntrustOrderAddRequest,
    responses={200: CommonResponseEnvelope},
    summary="委托订单新增",
    tags=["order", "entrust", "write"],
)


# ════════════════════════════════════════════════════════════════════════════
# 2. order — 订单主数据
# ════════════════════════════════════════════════════════════════════════════

# 2.1 订单详情查询(QUERY)
orderDetail = EndpointSpec(
    method="POST",
    path="/api/order/order/orderDetail",
    category=EndpointCategory.QUERY,
    mutates_state=False,
    request=OrderDetailRequest,
    responses={200: CommonResponseEnvelope},
    response_data_models={200: OrderDetailData},
    summary="订单详情查询",
    tags=["order", "detail", "query"],
)

# 2.2 订单新增(BUSINESS — 创建订单)
orderAdd = EndpointSpec(
    method="POST",
    path="/api/order/order/orderAdd",
    category=EndpointCategory.BUSINESS,
    mutates_state=True,
    request=OrderAddRequest,
    responses={200: CommonResponseEnvelope},
    summary="订单新增",
    tags=["order", "write"],
)

# 2.3 订单订舱(BUSINESS — 订单订舱)
orderBook = EndpointSpec(
    method="POST",
    path="/api/order/order/orderBook",
    category=EndpointCategory.BUSINESS,
    mutates_state=True,
    request=OrderBookRequest,
    responses={200: CommonResponseEnvelope},
    summary="订单订舱",
    tags=["order", "book", "write"],
)

# 2.4 checkGenerateOrderSub(QUERY — check 不直接改业务)
checkGenerateOrderSub = EndpointSpec(
    method="POST",
    path="/api/order/order/checkGenerateOrderSub",
    category=EndpointCategory.QUERY,
    mutates_state=False,
    request=CheckGenerateOrderSubRequest,
    responses={200: CommonResponseEnvelope},
    response_data_models={200: CheckGenerateOrderSubData},
    summary="生成子单预检",
    tags=["order", "sub-order", "check"],
)

# 2.5 generateOrderSub(BUSINESS — 生成子单)
generateOrderSub = EndpointSpec(
    method="POST",
    path="/api/order/order/generateOrderSub",
    category=EndpointCategory.BUSINESS,
    mutates_state=True,
    request=GenerateOrderSubRequest,
    responses={200: CommonResponseEnvelope},
    summary="生成子单",
    tags=["order", "sub-order", "write"],
)

# 2.6 changeInvoiceApply(BUSINESS — 发起改票审核)
changeInvoiceApply = EndpointSpec(
    method="POST",
    path="/api/order/order/changeInvoiceApply",
    category=EndpointCategory.BUSINESS,
    mutates_state=True,
    request=ChangeInvoiceApplyRequest,
    responses={200: CommonResponseEnvelope},
    summary="发起改票审核申请",
    tags=["order", "invoice", "audit", "write"],
)

# 2.7 orderConfirmAccount(BUSINESS — 确认账户)
orderConfirmAccount = EndpointSpec(
    method="POST",
    path="/api/order/order/orderConfirmAccount",
    category=EndpointCategory.BUSINESS,
    mutates_state=True,
    request=OrderConfirmAccountRequest,
    responses={200: CommonResponseEnvelope},
    response_data_models={200: OrderConfirmAccountData},
    summary="订单确认账户",
    tags=["order", "account", "write"],
)


# ════════════════════════════════════════════════════════════════════════════
# 3. orderFee — 订单费用
# ════════════════════════════════════════════════════════════════════════════

# 3.1 toggleRealAmount(BUSINESS — 金额确认)
toggleRealAmount = EndpointSpec(
    method="POST",
    path="/api/order/orderFee/toggleRealAmount",
    category=EndpointCategory.BUSINESS,
    mutates_state=True,
    request=ToggleRealAmountRequest,
    responses={200: CommonResponseEnvelope},
    response_data_models={200: ToggleRealAmountData},
    summary="确认实际金额",
    tags=["order-fee", "amount", "write"],
)

# 3.2 bookRealAmountEdit(BUSINESS — 订舱金额修改)
bookRealAmountEdit = EndpointSpec(
    method="POST",
    path="/api/order/orderFee/bookRealAmountEdit",
    category=EndpointCategory.BUSINESS,
    mutates_state=True,
    request=BookRealAmountEditRequest,
    responses={200: CommonResponseEnvelope},
    summary="订舱金额修改",
    tags=["order-fee", "book", "write"],
)

# 3.3 realAmountLockSubmit(BUSINESS — 锁定费用)
realAmountLockSubmit = EndpointSpec(
    method="POST",
    path="/api/order/orderFee/realAmountLockSubmit",
    category=EndpointCategory.BUSINESS,
    mutates_state=True,
    request=RealAmountLockSubmitRequest,
    responses={200: CommonResponseEnvelope},
    summary="实际金额锁定提交",
    tags=["order-fee", "lock", "write"],
)


# ════════════════════════════════════════════════════════════════════════════
# 4. home/audit — 审核工作台
# ════════════════════════════════════════════════════════════════════════════

# 4.1 auditPage(QUERY)
auditPage = EndpointSpec(
    method="POST",
    path="/api/home/audit/auditPage",
    category=EndpointCategory.QUERY,
    mutates_state=False,
    request=AuditPageRequest,
    responses={200: CommonResponseEnvelope},
    response_data_models={200: AuditPageData},
    summary="审核分页查询",
    tags=["audit", "query"],
)

# 4.2 auditDetail(QUERY)
#    binding:audit_id 来自 auditPage 分页列表(PR-D4 §2.4 落地 #1)
auditDetail = EndpointSpec(
    method="POST",
    path="/api/home/audit/auditDetail",
    category=EndpointCategory.QUERY,
    mutates_state=False,
    request=AuditDetailRequest,
    responses={200: CommonResponseEnvelope},
    response_data_models={200: AuditDetailData},
    bindings=(
        FieldBinding(
            from_path=("data", "audit_id"),
            to_path=("audit_id",),
            required=True,
        ),
    ),
    summary="审核详情查询",
    tags=["audit", "detail", "query"],
)

# 4.3 auditExecute(BUSINESS — 执行审核)
auditExecute = EndpointSpec(
    method="POST",
    path="/api/home/audit/auditExecute",
    category=EndpointCategory.BUSINESS,
    mutates_state=True,
    request=AuditExecuteRequest,
    responses={200: CommonResponseEnvelope},
    summary="执行审核",
    tags=["audit", "write"],
)


# ════════════════════════════════════════════════════════════════════════════
# 5. finance/accountFee — 财务手续费
# ════════════════════════════════════════════════════════════════════════════

# 5.1 financePutList(QUERY)
financePutList = EndpointSpec(
    method="POST",
    path="/api/finance/accountFee/financePutList",
    category=EndpointCategory.QUERY,
    mutates_state=False,
    request=FinancePutListRequest,
    responses={200: CommonResponseEnvelope},
    response_data_models={200: FinancePutListData},
    summary="财务手续费列表查询",
    tags=["finance", "account-fee", "query"],
)


# ════════════════════════════════════════════════════════════════════════════
# 6. finance/receiveAccount — 收款账户
# ════════════════════════════════════════════════════════════════════════════

# 6.1 orderReceiveAccountEdit(BUSINESS — 编辑收款账户)
orderReceiveAccountEdit = EndpointSpec(
    method="POST",
    path="/api/finance/receiveAccount/orderReceiveAccountEdit",
    category=EndpointCategory.BUSINESS,
    mutates_state=True,
    request=OrderReceiveAccountEditRequest,
    responses={200: CommonResponseEnvelope},
    response_data_models={200: OrderReceiveAccountEditData},
    summary="订单收款账户编辑",
    tags=["finance", "receive-account", "write"],
)

# 6.2 receiveAccountDetail(QUERY)
receiveAccountDetail = EndpointSpec(
    method="POST",
    path="/api/finance/receiveAccount/receiveAccountDetail",
    category=EndpointCategory.QUERY,
    mutates_state=False,
    request=ReceiveAccountDetailRequest,
    responses={200: CommonResponseEnvelope},
    response_data_models={200: ReceiveAccountDetailData},
    summary="收款账户详情查询",
    tags=["finance", "receive-account", "query"],
)

# 6.3 receiveConfirmList(QUERY)
receiveConfirmList = EndpointSpec(
    method="POST",
    path="/api/finance/receiveAccount/receiveConfirmList",
    category=EndpointCategory.QUERY,
    mutates_state=False,
    request=ReceiveConfirmListRequest,
    responses={200: CommonResponseEnvelope},
    summary="收款确认列表查询",
    tags=["finance", "receive-account", "query"],
)

# 6.4 accountConfirm(BUSINESS — 确认收款)
accountConfirm = EndpointSpec(
    method="POST",
    path="/api/finance/receiveAccount/accountConfirm",
    category=EndpointCategory.BUSINESS,
    mutates_state=True,
    request=AccountConfirmRequest,
    responses={200: CommonResponseEnvelope},
    summary="确认收款",
    tags=["finance", "receive-account", "write"],
)


# ════════════════════════════════════════════════════════════════════════════
# 7. finance/ReceiveInvoiceBatch — 收票批量(路径大小写不规则,保留)
# ════════════════════════════════════════════════════════════════════════════

# 7.1 applyPage(QUERY)
applyPage = EndpointSpec(
    method="POST",
    path="/api/Finance/ReceiveInvoiceBatch/applyPage",
    category=EndpointCategory.QUERY,
    mutates_state=False,
    request=ApplyPageRequest,
    responses={200: CommonResponseEnvelope},
    response_data_models={200: ApplyPageData},
    summary="批量收票申请分页查询",
    tags=["finance", "invoice-batch", "query"],
)

# 7.2 checkStep1(QUERY — check 不改业务)
#    binding:receive_invoice_batch_id 来自 applyPage 分页列表(PR-D4 §2.4 落地 #3)
checkStep1 = EndpointSpec(
    method="POST",
    path="/api/Finance/ReceiveInvoiceBatch/checkStep1",
    category=EndpointCategory.QUERY,
    mutates_state=False,
    request=CheckStep1Request,
    responses={200: CommonResponseEnvelope},
    bindings=(
        FieldBinding(
            from_path=("data", "receive_invoice_batch_id"),
            to_path=("receive_invoice_batch_id",),
            required=True,
        ),
    ),
    summary="批量收票校验 Step1",
    tags=["finance", "invoice-batch", "check"],
)

# 7.3 checkStep2(QUERY)
#    binding:receive_invoice_batch_id 来自 applyPage 分页列表(PR-D4 §2.4 落地 #4)
checkStep2 = EndpointSpec(
    method="POST",
    path="/api/Finance/ReceiveInvoiceBatch/checkStep2",
    category=EndpointCategory.QUERY,
    mutates_state=False,
    request=CheckStep2Request,
    responses={200: CommonResponseEnvelope},
    bindings=(
        FieldBinding(
            from_path=("data", "receive_invoice_batch_id"),
            to_path=("receive_invoice_batch_id",),
            required=True,
        ),
    ),
    summary="批量收票校验 Step2",
    tags=["finance", "invoice-batch", "check"],
)

# 7.4 batchOrderEdit(BUSINESS — 批量编辑)
batchOrderEdit = EndpointSpec(
    method="POST",
    path="/api/Finance/ReceiveInvoiceBatch/batchOrderEdit",
    category=EndpointCategory.BUSINESS,
    mutates_state=True,
    request=BatchOrderEditRequest,
    responses={200: CommonResponseEnvelope},
    summary="批量订单编辑",
    tags=["finance", "invoice-batch", "write"],
)

# 7.5 batchDetail(QUERY)
#    binding:receive_invoice_batch_id 来自 applyPage 分页列表(PR-D4 §2.4 落地 #5)
batchDetail = EndpointSpec(
    method="POST",
    path="/api/Finance/ReceiveInvoiceBatch/batchDetail",
    category=EndpointCategory.QUERY,
    mutates_state=False,
    request=BatchDetailRequest,
    responses={200: CommonResponseEnvelope},
    bindings=(
        FieldBinding(
            from_path=("data", "receive_invoice_batch_id"),
            to_path=("receive_invoice_batch_id",),
            required=True,
        ),
    ),
    summary="批量详情查询",
    tags=["finance", "invoice-batch", "query"],
)

# 7.6 applyDetail(QUERY)
#    binding:receive_invoice_apply_id 来自 applyPage 分页列表(PR-D4 §2.4 落地 #2)
applyDetail = EndpointSpec(
    method="POST",
    path="/api/Finance/ReceiveInvoiceBatch/applyDetail",
    category=EndpointCategory.QUERY,
    mutates_state=False,
    request=ApplyDetailRequest,
    responses={200: CommonResponseEnvelope},
    bindings=(
        FieldBinding(
            from_path=("data", "receive_invoice_apply_id"),
            to_path=("receive_invoice_apply_id",),
            required=True,
        ),
    ),
    summary="批量申请详情查询",
    tags=["finance", "invoice-batch", "query"],
)


# ════════════════════════════════════════════════════════════════════════════
# 8. finance/receiveInvoice — 收票
# ════════════════════════════════════════════════════════════════════════════

# 8.1 invoiceAddCheck(QUERY — check 不改业务)
invoiceAddCheck = EndpointSpec(
    method="POST",
    path="/api/finance/receiveInvoice/invoiceAddCheck",
    category=EndpointCategory.QUERY,
    mutates_state=False,
    request=InvoiceAddCheckRequest,
    responses={200: CommonResponseEnvelope},
    summary="添加发票预检",
    tags=["finance", "invoice", "check"],
)

# 8.2 invoiceAdd(BUSINESS — 添加发票)
invoiceAdd = EndpointSpec(
    method="POST",
    path="/api/finance/receiveInvoice/invoiceAdd",
    category=EndpointCategory.BUSINESS,
    mutates_state=True,
    request=InvoiceAddRequest,
    responses={200: CommonResponseEnvelope},
    summary="添加发票",
    tags=["finance", "invoice", "write"],
)


# ════════════════════════════════════════════════════════════════════════════
# 9. finance/receiveWriteoff — 收款核销
# ════════════════════════════════════════════════════════════════════════════

# 9.1 orderFeePage(QUERY)
orderFeePage = EndpointSpec(
    method="POST",
    path="/api/finance/receiveWriteoff/orderFeePage",
    category=EndpointCategory.QUERY,
    mutates_state=False,
    request=OrderFeePageRequest,
    responses={200: CommonResponseEnvelope},
    summary="订单费用分页查询",
    tags=["finance", "writeoff", "query"],
)

# 9.2 writeoffBatch(BUSINESS — 批量核销)
writeoffBatch = EndpointSpec(
    method="POST",
    path="/api/finance/receiveWriteoff/writeoffBatch",
    category=EndpointCategory.BUSINESS,
    mutates_state=True,
    request=WriteoffBatchRequest,
    responses={200: CommonResponseEnvelope},
    summary="批量核销",
    tags=["finance", "writeoff", "write"],
)

# 9.3 writeoffPage(QUERY)
writeoffPage = EndpointSpec(
    method="POST",
    path="/api/finance/receiveWriteoff/writeoffPage",
    category=EndpointCategory.QUERY,
    mutates_state=False,
    request=WriteoffPageRequest,
    responses={200: CommonResponseEnvelope},
    response_data_models={200: WriteoffPageData},
    summary="核销分页查询",
    tags=["finance", "writeoff", "query"],
)


__all__ = [
    # 1. orderEntrust
    "orderEntrustOrderPage",
    "orderEntrustOrderAdd",
    # 2. order
    "orderDetail",
    "orderAdd",
    "orderBook",
    "checkGenerateOrderSub",
    "generateOrderSub",
    "changeInvoiceApply",
    "orderConfirmAccount",
    # 3. orderFee
    "toggleRealAmount",
    "bookRealAmountEdit",
    "realAmountLockSubmit",
    # 4. home/audit
    "auditPage",
    "auditDetail",
    "auditExecute",
    # 5. finance/accountFee
    "financePutList",
    # 6. finance/receiveAccount
    "orderReceiveAccountEdit",
    "receiveAccountDetail",
    "receiveConfirmList",
    "accountConfirm",
    # 7. finance/ReceiveInvoiceBatch
    "applyPage",
    "checkStep1",
    "checkStep2",
    "batchOrderEdit",
    "batchDetail",
    "applyDetail",
    # 8. finance/receiveInvoice
    "invoiceAddCheck",
    "invoiceAdd",
    # 9. finance/receiveWriteoff
    "orderFeePage",
    "writeoffBatch",
    "writeoffPage",
]