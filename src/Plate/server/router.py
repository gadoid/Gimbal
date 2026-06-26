"""Plate 服务端 URL 路由分发表(Phase 2 / PR-2.3)。

严格对应 [PR-2.1 §2.1](../../design/phase2/PR-2.1.md) 协议路由表。

业务约束:
  - 每条路由 = (path_pattern, method, handler, requires_version)
  - 路由匹配按注册顺序(精确匹配优先于泛匹配)
  - path 中支持 ``{param}`` 占位符,最后一个占位符支持 ``:path``(透传 '/')
  - 路由匹配与 handler 解耦 —— handler 由 ``server.__init__`` 模块提供

对应设计:PR-2.1 §2.1 路由表 + PR-2.3 §2.2。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from Plate.version import PlateVersion


@dataclass(frozen=True)
class Route:
    """单条路由声明。"""

    pattern: str  # 路径模式,带 {param} 占位
    method: str  # HTTP 方法(本 PR 仅 GET)
    handler: Callable[..., tuple[bytes, int, dict[str, str]]]
    requires_version: bool  # 是否需要 ?version= query param


# ── Handler 类型别名(避免循环导入 — handler 由 server.__init__ 注册) ──
HandlerType = Callable[..., tuple[bytes, int, dict[str, str]]]


def _placeholder_to_regex(pattern: str) -> re.Pattern[str]:
    """将 ``/v1/spec/{service}/{method}/{path:path}`` → 编译后的 regex。

    占位符规则:
      - ``{name}`` → 匹配非 '/' 字符: ``(?P<name>[^/]+)``
      - ``{name:path}`` → 匹配任意字符(含 '/'): ``(?P<name>.+)``
      - 字面字符需 regex-escape
    """
    parts = re.split(r"(\{[^}]+\})", pattern)
    regex_parts: list[str] = []
    for part in parts:
        if not part:
            continue
        m = re.match(r"^\{([^}:]+)(?::path)?\}$", part)
        if m is not None:
            name = m.group(1)
            if part.endswith(":path}"):
                regex_parts.append(f"(?P<{name}>.+)")
            else:
                regex_parts.append(f"(?P<{name}>[^/]+)")
        else:
            regex_parts.append(re.escape(part))
    return re.compile("^" + "".join(regex_parts) + "$")


# ── 路由表(顺序敏感 — 精确匹配优先于泛匹配)──


def _make_routes(handlers: dict[str, HandlerType]) -> tuple[Route, ...]:
    """从 handler 字典构造路由表。延迟绑定 handler 以避免循环导入。"""
    return (
        Route("/healthz", "GET", handlers["healthz"], requires_version=False),
        Route("/v1/version", "GET", handlers["version_list"], requires_version=False),
        Route("/v1/manifest", "GET", handlers["manifest_default"], requires_version=False),
        Route(
            "/v1/manifest/{version}",
            "GET",
            handlers["manifest_pinned"],
            requires_version=False,
        ),
        Route("/v1/spec/{service}", "GET", handlers["spec_service"], requires_version=True),
        Route(
            "/v1/spec/{service}/{method}/{path:path}",
            "GET",
            handlers["spec_endpoint"],
            requires_version=True,
        ),
        Route("/v1/doc/{service}", "GET", handlers["doc_service"], requires_version=True),
        Route(
            "/v1/doc/{service}/{method}/{path:path}",
            "GET",
            handlers["doc_endpoint"],
            requires_version=True,
        ),
    )


# 默认路由表(handler 在首次 match_route 调用时由 caller 注入)
_ROUTES: tuple[Route, ...] | None = None
_ROUTES_BY_HANDLER: dict[str, HandlerType] = {}


def register_handlers(handlers: dict[str, HandlerType]) -> None:
    """注入 handler 字典并构建路由表。``PlateRequestHandler`` 启动前调用一次。"""
    global _ROUTES, _ROUTES_BY_HANDLER
    _ROUTES_BY_HANDLER = handlers
    _ROUTES = _make_routes(handlers)


def match_route(
    path: str,
    method: str,
) -> tuple[Route | None, dict[str, Any]]:
    """匹配 path + method,返回 ``(route, params)``。

    无匹配 → ``(None, {})``。
    """
    if _ROUTES is None:
        # 首次调用未注入 handler:返回 NOT_FOUND
        return None, {}
    for route in _ROUTES:
        if route.method != method:
            continue
        m = _placeholder_to_regex(route.pattern).match(path)
        if m is not None:
            return route, m.groupdict()
    return None, {}


__all__ = ["Route", "register_handlers", "match_route"]
