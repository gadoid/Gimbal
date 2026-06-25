"""fin 服务契约模型包。

提供 :mod:`Plate.fin.models` 中定义的全部 pydantic v2 数据类,以及
``(method, path)`` → 模型的查询函数。

典型用法::

    from Plate.fin import get_request_model, get_response_data_model

    Req = get_request_model("POST", "/api/order/order/orderDetail")
    req = Req.model_validate({"order_id": "327661182355767296"})

    Resp = get_response_data_model("POST", "/api/order/order/orderDetail")
    data = Resp.model_validate(...)
"""
from .models import (
    PATH_MODELS,
    CommonResponseEnvelope,
    EndpointBinding,
    get_binding,
    get_request_model,
    get_response_data_model,
    list_paths,
)

__all__ = [
    "PATH_MODELS",
    "CommonResponseEnvelope",
    "EndpointBinding",
    "get_binding",
    "get_request_model",
    "get_response_data_model",
    "list_paths",
]
