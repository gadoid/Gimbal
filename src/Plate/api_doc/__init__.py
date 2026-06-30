"""Plate API doc 子包(Phase 3 §4.1)。

设计动机(对应 ``design/phase3/PR-3.1.md``):
  - 渲染 ``EndpointSpec`` (L1) + ``EndpointDoc`` (L2) 为人类可读的 Markdown
  - 库形态优先,CLI 是薄包装(对齐 PLATE_EVOLUTION §4.3 论证的 B1 原则)
  - **不** import 任何 service 子包(不变量 #1 零侵入)

模块导出:
  - ``render_endpoint(spec, doc=None) -> str``:渲染单个 endpoint 的 Markdown
  - ``render_service(service, specs, doc_lookup=None) -> str``:渲染整个 service
"""
from __future__ import annotations

from .render import render_endpoint, render_service

__all__ = ["render_endpoint", "render_service"]