"""Plate 服务端响应工具(Phase 2 / PR-2.3)。

职责:统一 JSON 响应与错误响应的构造。

对应设计:PR-2.1 §2.4 + PR-2.3 §2.3。
"""
from __future__ import annotations

import json
from typing import Any


def json_response(
    body: Any,
    status: int = 200,
    headers: dict[str, str] | None = None,
) -> tuple[bytes, int, dict[str, str]]:
    """构造 JSON 响应。

    关键约定(对应 PR-2.1 §2.5):
      - Content-Type: application/json; charset=utf-8
      - sort_keys=True + separators=(",", ":"):byte-equal 保证
      - Content-Length 必带(BaseHTTPRequestHandler 需要)

    Args:
        body: 可 JSON 序列化的对象
        status: HTTP 状态码
        headers: 额外的响应头(会被 Content-Type/Content-Length 覆盖)

    Returns:
        (body_bytes, status, headers_dict)
    """
    payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    h: dict[str, str] = {
        "Content-Type": "application/json; charset=utf-8",
        "Content-Length": str(len(payload)),
    }
    if headers:
        h.update(headers)
    return payload, status, h


def error_response(
    code: str,
    message: str,
    status: int,
    extra: dict | None = None,
) -> tuple[bytes, int, dict[str, str]]:
    """构造错误响应(对应 PR-2.1 §2.4)。

    错误响应体形态:
        {"error": "<CODE>", "message": "<human readable>", ...extra}
    """
    body: dict = {"error": code, "message": message}
    if extra:
        body.update(extra)
    return json_response(body, status=status)


__all__ = ["json_response", "error_response"]