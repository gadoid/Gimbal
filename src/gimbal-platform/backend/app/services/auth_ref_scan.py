"""平台侧 ${auth.<alias>.*} 模板引用扫描器。

语义对齐前端 tpl-refs(frontend/src/utils/tpl-refs.ts):递归扫 steps
的字符串值(headers/path/body/strategy 一网打尽),收集被引用的 auth
alias。注入清单的自动部分以此为准 — 场景内容是单一事实源(spec §5)。
"""
from __future__ import annotations

import re

# ${auth.<alias>} 或 ${auth.<alias>.<field>};alias 字符集与前端
# tpl-refs 一致:字母数字下划线连字符。
_AUTH_RE = re.compile(r"\$\{\s*auth\.([A-Za-z0-9_-]+)(?:\.[A-Za-z0-9_.-]+)?\s*\}")


def scan_auth_aliases(steps: list) -> list[str]:
    """收集 steps 里 ${auth.<alias>.*} 引用的去重 alias(保持出现序)。"""
    seen: dict[str, None] = {}  # dict 保序去重
    for found in _scan_value(steps):
        seen.setdefault(found, None)
    return list(seen)


def _scan_value(node: object) -> list[str]:
    if isinstance(node, str):
        return _AUTH_RE.findall(node)
    if isinstance(node, dict):
        out: list[str] = []
        for v in node.values():
            out.extend(_scan_value(v))
        return out
    if isinstance(node, list):
        out = []
        for v in node:
            out.extend(_scan_value(v))
        return out
    return []
