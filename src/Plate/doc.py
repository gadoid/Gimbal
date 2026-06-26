"""Plate 端点的人类注释(L2 字段,文档元数据)。

对应设计:PLATE_DESIGN.md §2.3 + PR-D3 §2.2。

关键约束(对应设计 §4 "L1/L2 物理解耦"):
- L1 = ``Plate.spec.EndpointSpec``(机器可再生,本文件**不**依赖 spec 即可 import)
- L2 = ``Plate.doc.EndpointDoc``(人工写,独立 review)
- 物理上与 spec 分离:``Plate.spec`` 不 import ``Plate.doc``;反之亦然
- summary ≤ 120 字符(强制,超长 AI 截断失真)
- 所有 list-like 字段用 tuple(满足 frozen 不可变,见 §2.2)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import final

_SUMMARY_MAX_LEN: int = 120


@final
@dataclass(frozen=True)
class EndpointDoc:
    """端点的人类注释(L2 字段)。

    字段语义(对应设计 §2.3):
      - summary:一句话用途(必填,≤120 字符,AI 总结时不被截断)
      - notes:注意事项(限流 / 时序 / 单位 / 时区等)
      - requires:前置条件(调此端点前必须满足的状态,字符串描述)
      - see_also:相关端点 path 列表(供 AI 导航 / 知识图谱构建)

    物理位置:由 ``Plate.fin.dannotations`` 等子模块按 endpoint path 索引,
    本文件**不**关心"哪个 endpoint 对应哪个 doc"——那是上层模块的事。
    """

    summary: str
    notes: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()
    see_also: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # 1. summary 强校
        if not self.summary or not self.summary.strip():
            raise ValueError("EndpointDoc: summary 不能为空或全空白")
        if len(self.summary) > _SUMMARY_MAX_LEN:
            raise ValueError(
                f"EndpointDoc: summary 长度 {len(self.summary)} 超过上限 "
                f"{_SUMMARY_MAX_LEN}(防止 AI 总结时被截断失真)。"
                f"实际内容: {self.summary!r}"
            )
        # 2. list-like 字段必须是 tuple(对应设计 §2.2 frozen 不变式)
        for fname in ("notes", "requires", "see_also"):
            v = getattr(self, fname)
            if not isinstance(v, tuple):
                raise TypeError(
                    f"EndpointDoc.{fname} 必须是 tuple,实际 {type(v).__name__}"
                )


__all__ = ["EndpointDoc", "_SUMMARY_MAX_LEN"]
