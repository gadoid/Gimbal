"""gimbal_response_body_extract — 自动为每个执行的 step 注入"提取 response_body"的策略。

通过订阅 HTTP_AFTER_RECV 钩子实现，等价于为每个 step 追加：
    Extract(expression="$.response_body", target=<target>, scope=STEP, phase=AFTER_REQUEST)
"""
from __future__ import annotations

from .plugin import ResponseBodyExtractPlugin

__all__ = ["ResponseBodyExtractPlugin"]