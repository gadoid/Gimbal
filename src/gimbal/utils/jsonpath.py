"""gimbal/utils/jsonpath.py

轻量级 JSON 路径解析器，零外部依赖。

支持能力
--------
读 (get / get_all):
  $.field                  —— 对象字段
  $.a.b.c                  —— 嵌套字段
  $.items[0]               —— 正向下标
  $.items[-1]              —— 倒序下标
  $.items[*]               —— 通配，返回所有元素
  $.items[*].name          —— 通配后继续导航
  $['key with space']      —— 带空格/特殊字符的 key
  $.items[?(@.status==200)]       —— 过滤（==, !=, >, >=, <, <=, in, contains）
  $..field                 —— 递归搜索（深度优先）

写 (set):
  同上路径格式；路径不存在时自动创建中间节点（dict / list）

删 (delete):
  同上路径格式

模板变量解析:
  resolve_template("Bearer ${token}", ctx_vars) → "Bearer abc123"

设计原则
--------
- 纯 Python，零依赖
- 所有公开函数不抛 JsonPathError 以外的异常
- get() 找不到时返回 default（默认 None），不抛异常
- set() / delete() 直接修改传入的 dict/list（in-place），同时返回修改后的对象
- 线程安全（无模块级可变状态）
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Iterator


# ── 公开异常 ──────────────────────────────────────────────────────────────────

class JsonPathError(Exception):
    """路径语法或运行时错误。"""


# ── Token 定义 ────────────────────────────────────────────────────────────────

class TK(Enum):
    ROOT        = auto()   # $
    DOT         = auto()   # .
    DOT_DOT     = auto()   # ..
    LBRACKET    = auto()   # [
    RBRACKET    = auto()   # ]
    WILDCARD    = auto()   # *
    INDEX       = auto()   # 整数
    KEY         = auto()   # 字符串 key
    FILTER      = auto()   # ?(@...)
    EOF         = auto()


@dataclass
class Token:
    kind: TK
    value: Any = None


# ── 词法分析 ──────────────────────────────────────────────────────────────────

_KEY_RE = re.compile(r"[A-Za-z_\u4e00-\u9fff][A-Za-z0-9_\u4e00-\u9fff]*")
_INT_RE = re.compile(r"-?\d+")


def _tokenize(path: str) -> list[Token]:
    """将路径字符串转换为 Token 列表。"""
    tokens: list[Token] = []
    i = 0
    n = len(path)

    while i < n:
        ch = path[i]

        # $ 根节点
        if ch == "$":
            tokens.append(Token(TK.ROOT))
            i += 1

        # .. 递归下降
        elif path[i:i+2] == "..":
            tokens.append(Token(TK.DOT_DOT))
            i += 2

        # . 普通点号
        elif ch == ".":
            tokens.append(Token(TK.DOT))
            i += 1

        # [
        elif ch == "[":
            i += 1
            # 提前检查是否有配对的 ]
            if "]" not in path[i:]:
                raise JsonPathError(f"Unclosed '[' at position {i - 1} in path {path!r}")
            # 跳过空白
            while i < n and path[i] == " ":
                i += 1

            # 通配 [*]
            if i < n and path[i] == "*":
                tokens.append(Token(TK.WILDCARD))
                i += 1
                while i < n and path[i] == " ":
                    i += 1
                if i < n and path[i] == "]":
                    i += 1
                continue

            # 过滤 [?(@...)]
            if path[i:i+2] == "?(":
                end = path.find(")", i)
                if end == -1:
                    raise JsonPathError(f"Unclosed filter expression at position {i}")
                # 取括号内的内容，即 @...
                inner = path[i+2:end].strip()
                i = end + 1
                while i < n and path[i] == " ":
                    i += 1
                if i < n and path[i] == "]":
                    i += 1
                tokens.append(Token(TK.FILTER, inner))
                continue

            # 带引号的 key ['foo bar']
            if i < n and path[i] in ("'", '"'):
                quote = path[i]
                i += 1
                start = i
                while i < n and path[i] != quote:
                    i += 1
                key = path[start:i]
                i += 1  # 跳过结束引号
                while i < n and path[i] == " ":
                    i += 1
                if i < n and path[i] == "]":
                    i += 1
                tokens.append(Token(TK.KEY, key))
                continue

            # 整数下标 [0] [-1]
            m = _INT_RE.match(path, i)
            if m:
                tokens.append(Token(TK.INDEX, int(m.group())))
                i = m.end()
                while i < n and path[i] == " ":
                    i += 1
                if i < n and path[i] == "]":
                    i += 1
                continue

            raise JsonPathError(f"Unexpected character in bracket at position {i}: {path[i]!r}")

        # ] 单独出现（上面的 [ 处理会消耗配对的 ]，这里是冗余防御）
        elif ch == "]":
            i += 1

        # 通配 .*
        elif ch == "*":
            tokens.append(Token(TK.WILDCARD))
            i += 1

        # 标识符 key
        else:
            m = _KEY_RE.match(path, i)
            if m:
                tokens.append(Token(TK.KEY, m.group()))
                i = m.end()
            else:
                raise JsonPathError(f"Unexpected character at position {i}: {path[i]!r}")

    tokens.append(Token(TK.EOF))
    return tokens


# ── AST 节点 ──────────────────────────────────────────────────────────────────

class NodeKind(Enum):
    ROOT        = auto()
    FIELD       = auto()   # .name
    INDEX       = auto()   # [0]
    WILDCARD    = auto()   # [*] / .*
    FILTER      = auto()   # [?(@...)]
    RECURSIVE   = auto()   # ..name


@dataclass
class PathNode:
    kind: NodeKind
    value: Any = None       # field 名 / 整数下标 / 过滤表达式字符串


# ── 语法分析 ──────────────────────────────────────────────────────────────────

def _parse(path: str) -> list[PathNode]:
    """将 Token 列表解析为 PathNode 列表（去掉 ROOT）。"""
    tokens = _tokenize(path)
    nodes: list[PathNode] = []
    i = 0

    def peek() -> Token:
        return tokens[i] if i < len(tokens) else Token(TK.EOF)

    def consume() -> Token:
        nonlocal i
        t = tokens[i]
        i += 1
        return t

    # 必须以 $ 开头
    if peek().kind != TK.ROOT:
        raise JsonPathError(f"JSONPath must start with '$', got: {path!r}")
    consume()  # 消耗 ROOT

    recursive = False

    while peek().kind != TK.EOF:
        t = consume()

        if t.kind == TK.DOT_DOT:
            recursive = True
            continue

        if t.kind == TK.DOT:
            # . 后面跟 key 或 *
            nxt = consume()
            if nxt.kind == TK.KEY:
                kind = NodeKind.RECURSIVE if recursive else NodeKind.FIELD
                nodes.append(PathNode(kind, nxt.value))
            elif nxt.kind == TK.WILDCARD:
                nodes.append(PathNode(NodeKind.WILDCARD))
            else:
                raise JsonPathError(f"Expected field name after '.', got {nxt}")
            recursive = False

        elif t.kind == TK.KEY:
            kind = NodeKind.RECURSIVE if recursive else NodeKind.FIELD
            nodes.append(PathNode(kind, t.value))
            recursive = False

        elif t.kind == TK.INDEX:
            nodes.append(PathNode(NodeKind.INDEX, t.value))
            recursive = False

        elif t.kind == TK.WILDCARD:
            nodes.append(PathNode(NodeKind.WILDCARD))
            recursive = False

        elif t.kind == TK.FILTER:
            nodes.append(PathNode(NodeKind.FILTER, t.value))
            recursive = False

        elif t.kind == TK.LBRACKET:
            # 不应出现，tokenizer 里已消耗
            pass

    return nodes


# ── 过滤表达式求值 ────────────────────────────────────────────────────────────

_FILTER_RE = re.compile(
    r"@\.(?P<field>[A-Za-z_\u4e00-\u9fff][A-Za-z0-9_.\u4e00-\u9fff]*)"
    r"\s*(?P<op>==|!=|>=|<=|>|<|in|contains)\s*"
    r"(?P<val>.+)"
)


def _parse_filter_value(raw: str) -> Any:
    """解析过滤表达式右侧的值。"""
    raw = raw.strip()
    if (raw.startswith("'") and raw.endswith("'")) or \
       (raw.startswith('"') and raw.endswith('"')):
        return raw[1:-1]
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    if raw.lower() == "null":
        return None
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _eval_filter(expr: str, item: Any) -> bool:
    """对单个元素求值过滤表达式（@.field op value）。"""
    m = _FILTER_RE.match(expr.strip())
    if not m:
        raise JsonPathError(f"Unsupported filter expression: {expr!r}")

    field_path = m.group("field")
    op = m.group("op").strip()
    expected = _parse_filter_value(m.group("val"))

    # 支持嵌套字段 @.a.b
    actual = item
    for part in field_path.split("."):
        if isinstance(actual, dict):
            actual = actual.get(part)
        else:
            actual = None
            break

    try:
        if op == "==":
            return actual == expected
        if op == "!=":
            return actual != expected
        if op == ">":
            return actual > expected   # type: ignore[operator]
        if op == ">=":
            return actual >= expected  # type: ignore[operator]
        if op == "<":
            return actual < expected   # type: ignore[operator]
        if op == "<=":
            return actual <= expected  # type: ignore[operator]
        if op == "in":
            return actual in expected
        if op == "contains":
            return expected in actual  # type: ignore[operator]
    except Exception:
        return False
    return False


# ── 递归搜索辅助 ──────────────────────────────────────────────────────────────

def _recursive_collect(data: Any, field: str) -> list[Any]:
    """深度优先收集所有层级中名为 field 的值。"""
    results: list[Any] = []
    if isinstance(data, dict):
        if field in data:
            results.append(data[field])
        for v in data.values():
            results.extend(_recursive_collect(v, field))
    elif isinstance(data, list):
        for item in data:
            results.extend(_recursive_collect(item, field))
    return results


# ── 核心求值引擎 ──────────────────────────────────────────────────────────────

def _eval_nodes(data: Any, nodes: list[PathNode]) -> list[Any]:
    """
    递归求值节点列表，始终返回匹配值的列表（支持通配/过滤的多结果）。
    """
    if not nodes:
        return [data]

    node = nodes[0]
    rest = nodes[1:]

    # ── FIELD ──────────────────────────────
    if node.kind == NodeKind.FIELD:
        if not isinstance(data, dict):
            return []
        val = data.get(node.value)
        if val is None and node.value not in data:
            return []
        return _eval_nodes(val, rest)

    # ── INDEX ──────────────────────────────
    if node.kind == NodeKind.INDEX:
        if not isinstance(data, list):
            return []
        try:
            val = data[node.value]
        except IndexError:
            return []
        return _eval_nodes(val, rest)

    # ── WILDCARD ───────────────────────────
    if node.kind == NodeKind.WILDCARD:
        if isinstance(data, dict):
            items = list(data.values())
        elif isinstance(data, list):
            items = data
        else:
            return []
        results: list[Any] = []
        for item in items:
            results.extend(_eval_nodes(item, rest))
        return results

    # ── FILTER ─────────────────────────────
    if node.kind == NodeKind.FILTER:
        if not isinstance(data, list):
            return []
        results = []
        for item in data:
            try:
                if _eval_filter(node.value, item):
                    results.extend(_eval_nodes(item, rest))
            except JsonPathError:
                pass
        return results

    # ── RECURSIVE ──────────────────────────
    if node.kind == NodeKind.RECURSIVE:
        all_vals = _recursive_collect(data, node.value)
        results = []
        for v in all_vals:
            results.extend(_eval_nodes(v, rest))
        return results

    return []


# ── 路径 set 辅助 ─────────────────────────────────────────────────────────────

def _set_at(data: Any, nodes: list[PathNode], value: Any) -> Any:
    """
    在 data 上按 nodes 路径写入 value（in-place），返回根对象。

    - 中间节点不存在时按类型自动创建（FIELD → dict，INDEX → list）
    - 不支持通配符 / 过滤写入（语义不明确）
    """
    if not nodes:
        return value

    node = nodes[0]
    rest = nodes[1:]

    if node.kind == NodeKind.FIELD:
        if not isinstance(data, dict):
            data = {}
        next_val = data.get(node.value)
        data[node.value] = _set_at(next_val, rest, value)
        return data

    if node.kind == NodeKind.INDEX:
        idx = node.value
        if not isinstance(data, list):
            data = []
        # 自动扩展列表
        if idx >= 0:
            while len(data) <= idx:
                data.append(None)
        data[idx] = _set_at(data[idx], rest, value)
        return data

    raise JsonPathError(f"Cannot set through node kind: {node.kind}")


def _delete_at(data: Any, nodes: list[PathNode]) -> bool:
    """
    在 data 上按 nodes 路径删除节点，返回是否成功删除。
    """
    if len(nodes) == 1:
        node = nodes[0]
        if node.kind == NodeKind.FIELD and isinstance(data, dict):
            if node.value in data:
                del data[node.value]
                return True
            return False
        if node.kind == NodeKind.INDEX and isinstance(data, list):
            try:
                del data[node.value]
                return True
            except IndexError:
                return False
        return False

    node = nodes[0]
    rest = nodes[1:]

    if node.kind == NodeKind.FIELD:
        if not isinstance(data, dict):
            return False
        child = data.get(node.value)
        if child is None:
            return False
        return _delete_at(child, rest)

    if node.kind == NodeKind.INDEX:
        if not isinstance(data, list):
            return False
        try:
            child = data[node.value]
        except IndexError:
            return False
        return _delete_at(child, rest)

    return False


# ── 公开 API ──────────────────────────────────────────────────────────────────

def get(data: Any, path: str, default: Any = None) -> Any:
    """读取第一个匹配值。找不到返回 default。

    Examples::

        get({"a": {"b": 1}}, "$.a.b")        # → 1
        get({"items": [1, 2]}, "$.items[0]")  # → 1
        get({}, "$.missing", "N/A")           # → "N/A"
    """
    try:
        nodes = _parse(path)
        results = _eval_nodes(data, nodes)
        return results[0] if results else default
    except JsonPathError:
        raise
    except Exception as exc:
        raise JsonPathError(f"Error evaluating path {path!r}: {exc}") from exc


def get_all(data: Any, path: str) -> list[Any]:
    """读取所有匹配值，返回列表（通配/过滤场景）。

    Examples::

        get_all({"items": [{"id": 1}, {"id": 2}]}, "$.items[*].id")  # → [1, 2]
    """
    try:
        nodes = _parse(path)
        return _eval_nodes(data, nodes)
    except JsonPathError:
        raise
    except Exception as exc:
        raise JsonPathError(f"Error evaluating path {path!r}: {exc}") from exc


def set_value(data: Any, path: str, value: Any) -> Any:
    """在 data 上按路径写入 value（in-place + 返回根）。

    Examples::

        d = {}
        set_value(d, "$.user.name", "Alice")  # d == {"user": {"name": "Alice"}}
    """
    try:
        nodes = _parse(path)
        if not nodes:
            return value
        return _set_at(data, nodes, value)
    except JsonPathError:
        raise
    except Exception as exc:
        raise JsonPathError(f"Error setting path {path!r}: {exc}") from exc


def delete(data: Any, path: str) -> bool:
    """按路径删除字段，返回是否成功。

    Examples::

        d = {"a": {"b": 1, "c": 2}}
        delete(d, "$.a.b")  # d == {"a": {"c": 2}}, returns True
    """
    try:
        nodes = _parse(path)
        return _delete_at(data, nodes)
    except JsonPathError:
        raise
    except Exception as exc:
        raise JsonPathError(f"Error deleting path {path!r}: {exc}") from exc


def exists(data: Any, path: str) -> bool:
    """检查路径是否存在。

    Examples::

        exists({"a": 1}, "$.a")    # → True
        exists({"a": 1}, "$.b")    # → False
    """
    try:
        nodes = _parse(path)
        results = _eval_nodes(data, nodes)
        return bool(results)
    except JsonPathError:
        return False


# ── 模板变量解析 ──────────────────────────────────────────────────────────────

_TEMPLATE_VAR_RE = re.compile(r"\$\{([^}]+)\}")


def resolve_template(template: str, variables: dict[str, Any]) -> Any:
    """将 '${varname}' 占位符替换为 variables 中的对应值。

    - 若整个 template 就是单个占位符（如 "${token}"），直接返回原始类型值
      （避免把 int/dict 强制转为字符串）。
    - 若包含多个占位符或夹杂普通文本，则做字符串替换。

    Examples::

        resolve_template("Bearer ${token}", {"token": "abc"})  # → "Bearer abc"
        resolve_template("${user_id}", {"user_id": 42})        # → 42  (int 保留)
        resolve_template("${a}+${b}", {"a": 1, "b": 2})       # → "1+2"
    """
    # 整个字符串就是单个变量 → 直接返回原始类型
    m = _TEMPLATE_VAR_RE.fullmatch(template.strip())
    if m:
        var_name = m.group(1).strip()
        return variables.get(var_name)

    def _replacer(match: re.Match) -> str:
        var_name = match.group(1).strip()
        val = variables.get(var_name, match.group(0))  # 找不到保留原样
        return str(val) if val is not None else ""

    return _TEMPLATE_VAR_RE.sub(_replacer, template)


# ── 便捷函数：路径是否是模板变量 ─────────────────────────────────────────────

def is_template(value: Any) -> bool:
    """判断 value 是否是模板变量字符串（含 ${...}）。"""
    return isinstance(value, str) and bool(_TEMPLATE_VAR_RE.search(value))


def is_jsonpath(value: Any) -> bool:
    """判断 value 是否是 JSONPath 表达式（以 $ 开头）。"""
    return isinstance(value, str) and value.startswith("$")