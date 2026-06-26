"""fin 服务的人工注释(L2 物理层)。

对应设计:PLATE_DESIGN.md §2.3 + §4 + PR-D3 §2.4。

L1(spec,机器可再生,见 ``Plate.fin.endpoints``)与 L2(本文件,人工写)物理分离。
key 是 ``EndpointSpec.path``(全路径,如 ``"/api/order/order/orderDetail"``)。

PR-D3 本文件为空壳 —— 后续 PR 按 endpoint 渐进补注释。
PR-EOP review pipeline 会校验"L1/L2 对称性"(有 spec 无 doc 允许;有 doc 无 spec 报错)。
"""
from __future__ import annotations

from Plate.doc import EndpointDoc

# 结构: path → EndpointDoc
_DOCS: dict[str, EndpointDoc] = {
    # 例(后续 PR 补):
    # "/api/order/order/orderDetail": EndpointDoc(
    #     summary="按订单 ID 查询订单详情,返回订单全字段快照",
    #     notes=("限流:每用户 10 QPS", "时区:所有时间字段为 UTC+8"),
    #     requires=("已登录", "订单属于当前用户"),
    #     see_also=("/api/order/order/addOrder",),
    # ),
}


def get_doc(path: str) -> EndpointDoc | None:
    """按 path 查 L2 doc;不存在返回 None。

    对应设计:§2.4 get_doc 契约 —— 不抛错(KeyError 会强迫消费方 try/except,
    API 难用)。
    """
    return _DOCS.get(path)


__all__ = ["EndpointDoc", "_DOCS", "get_doc"]
