"""fin 服务契约包。

目录结构(PLATE_DESIGN §1):
    Plate/fin/
    ├── __init__.py    # 本文件:re-export endpoints + 通用 envelope
    ├── models.py      # Pydantic 数据类(L1)
    ├── endpoints.py   # 31 个 EndpointSpec 实例(L1)
    └── docs.py        # EndpointDoc 实例(L2)

典型用法(从 registry 单轨查询)::

    from Plate import registry
    spec = registry.resolve("fin", "POST", "/api/order/order/orderDetail")
    req = spec.request.model_validate({...})
"""
from .endpoints import (
    # 1. orderEntrust
    orderEntrustOrderPage,
    orderEntrustOrderAdd,
    # 2. order
    orderDetail,
    orderAdd,
    orderBook,
    checkGenerateOrderSub,
    generateOrderSub,
    changeInvoiceApply,
    orderConfirmAccount,
    # 3. orderFee
    toggleRealAmount,
    bookRealAmountEdit,
    realAmountLockSubmit,
    # 4. home/audit
    auditPage,
    auditDetail,
    auditExecute,
    # 5. finance/accountFee
    financePutList,
    # 6. finance/receiveAccount
    orderReceiveAccountEdit,
    receiveAccountDetail,
    receiveConfirmList,
    accountConfirm,
    # 7. finance/ReceiveInvoiceBatch
    applyPage,
    checkStep1,
    checkStep2,
    batchOrderEdit,
    batchDetail,
    applyDetail,
    # 8. finance/receiveInvoice
    invoiceAddCheck,
    invoiceAdd,
    # 9. finance/receiveWriteoff
    orderFeePage,
    writeoffBatch,
    writeoffPage,
)

# 通用 envelope(几乎所有 spec 引用)
from .models import CommonResponseEnvelope

__all__ = [
    # 31 个 EndpointSpec 实例(按 orderEntrust/order/orderFee/home.audit/...
    # 分组,见 endpoints.py)
    "orderEntrustOrderPage",
    "orderEntrustOrderAdd",
    "orderDetail",
    "orderAdd",
    "orderBook",
    "checkGenerateOrderSub",
    "generateOrderSub",
    "changeInvoiceApply",
    "orderConfirmAccount",
    "toggleRealAmount",
    "bookRealAmountEdit",
    "realAmountLockSubmit",
    "auditPage",
    "auditDetail",
    "auditExecute",
    "financePutList",
    "orderReceiveAccountEdit",
    "receiveAccountDetail",
    "receiveConfirmList",
    "accountConfirm",
    "applyPage",
    "checkStep1",
    "checkStep2",
    "batchOrderEdit",
    "batchDetail",
    "applyDetail",
    "invoiceAddCheck",
    "invoiceAdd",
    "orderFeePage",
    "writeoffBatch",
    "writeoffPage",
    # 通用 envelope(供需要 envelope 类型的消费者按需 import)
    "CommonResponseEnvelope",
]