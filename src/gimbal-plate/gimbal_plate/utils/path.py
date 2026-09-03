"""plate/utils/path.py

``DeclarationEntry.path`` 的归一化、末段提取与节点序列解析。

path 语法（与 ``plate/utils/jsonpath.py`` 一致）：JSONPath，须以 ``$`` 领头，
支持 ``$.a.b.c`` / ``$.items[0]`` / ``$.items[*].id`` / ``$['key with space']`` /
``$.items[?(@.status==200)]`` / ``$..field`` 等形态。

归一规则：
  - 形态统一为带 ``$.`` 前缀的字符串。``"order_no"`` → ``"$.order_no"``。
  - 非字符串、空字符串、非法 JSONPath 视为非法 path。

末段提取（``last_segment``，独立工具函数）：
  - ``name`` 校验已不再消费末段（name↔path 解绑，2026-09-03 spec D1）；
  - 末段节点是 ``FIELD`` → 用其 ``value``（标识符或带空格/中文的 key）。
  - 末段节点是 ``INDEX`` / ``WILDCARD`` / ``FILTER`` / ``RECURSIVE`` →
    ``last_segment`` 返回 ``None``（``DeclarationEntry`` 允许这种 path）。
"""
from __future__ import annotations

import re
from typing import Any

from . import jsonpath as _jp


_PREFIX = "$."

_SHORT_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*$")


def is_valid_path(value: Any) -> bool:
    """判断 value 是否是合法 path 字符串。

    双形态并存：接受非空字符串，且要么
      - 是合法 JSONPath（能通过 ``plate/utils/jsonpath.py`` 的解析），要么
      - 是合法短名（不以 ``$`` 领头的标识符，符合 ``[A-Za-z_][A-Za-z0-9_]*``）。
    """
    if not isinstance(value, str) or not value:
        return False
    if value.startswith("$"):
        try:
            _jp._parse(value)
        except _jp.JsonPathError:
            return False
        return True
    # 短名：标识符形态
    return bool(_SHORT_NAME_RE.match(value))


def normalize(value: str) -> str:
    """将 path 归一为带 ``$.`` 前缀的形态。

    - ``"order_no"`` → ``"$.order_no"``。
    - ``"$.order_no"`` → ``"$.order_no"``（原样）。
    - 空字符串、非法 JSONPath 直接抛 ``ValueError``，由调用方在 ``model_validator``
      中捕获并转成 ``ValueError`` 形式的 pydantic 错误。
    """
    if not isinstance(value, str) or not value:
        raise ValueError(f"path 必须是非空字符串，实际为 {value!r}")
    if not value.startswith("$"):
        # 双形态并存：短名自动补前缀
        return _PREFIX + value
    try:
        _jp._parse(value)
    except _jp.JsonPathError as exc:
        raise ValueError(f"非法 path {value!r}: {exc}") from exc
    return value


def last_segment(value: str) -> str | None:
    """提取 path 末段。返回末段 ``FIELD`` 的标识符，否则 ``None``。

    - ``"$.a.b.c"`` → ``"c"``
    - ``"$.items[0].sku"`` → ``"sku"``
    - ``"$.items[0]"`` → ``None``（末段是数组下标）
    - ``"$.items[*]"`` → ``None``（末段是通配）
    - ``"$..field"`` → ``None``（整段是递归下降）
    - ``"order_id"``（短名） → ``"order_id"``（整段即末段）
    - ``""`` / 非法 path → ``None``
    """
    if not isinstance(value, str) or not value:
        return None
    # 短名形态：双形态并存下,非 ``$`` 领头的合法标识符整段即末段
    if not value.startswith("$"):
        return value if _SHORT_NAME_RE.match(value) else None
    try:
        nodes = _jp._parse(value)
    except _jp.JsonPathError:
        return None
    if not nodes:
        return None
    last = nodes[-1]
    if last.kind.name == "FIELD":
        # 内部 enum 名见 plate/utils/jsonpath.py：FIELD / INDEX / WILDCARD / FILTER / RECURSIVE
        return last.value
    return None


def parse_nodes(value: str) -> "list[_jp.PathNode] | None":
    """合法 path → 节点序列(非法/空/非字符串 → None)。

    包含判定(io_spec D3)与通道形态判定(D2)的公共入口。
    """
    if not isinstance(value, str) or not value:
        return None
    try:
        return _jp._parse(value)
    except _jp.JsonPathError:
        return None