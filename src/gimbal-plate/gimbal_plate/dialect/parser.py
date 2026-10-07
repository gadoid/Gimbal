"""dialect.parser —— Markdown 方言解析（批次 A1，第 5 节）。

语法：frontmatter（``---`` YAML 头）+ 围栏块（info string =
``gimbal:<type>``，块体 YAML）+ 块外散文。行内 ``[[term-id]]`` 为纯书写
约定（已定）：**不解析、不校验、不进规范形**——它就是普通散文。

块信封（8s）：块体 YAML 中的 ``review: draft | reviewed`` 由方言层处理
（缺省 draft），strip 后才进 M2 模型（模型均 extra="forbid"）。

报错定位到文件与行（G2/R3 的基础）：所有错误携带 1-based 行号。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Union

import yaml

from .models import EndpointSpec, Frontmatter, Statement, Term


class _StrictLoader(yaml.SafeLoader):
    """重复键即报错（评审 P0-10：N5 合并冲突残留不再静默取后值）。"""


def _no_dup_keys(loader, node, deep=False):
    seen = set()
    for k_node, _ in node.value:
        key = loader.construct_object(k_node, deep=True)
        if key in seen:
            raise DialectError(
                f"YAML 重复键 {key!r}（合并冲突残留?）",
                source=getattr(loader, "_dialect_source", "<yaml>"),
                line=getattr(loader, "_dialect_line", node.start_mark.line + 1),
            )
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


_StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_dup_keys)


def strict_yaml_load(text: str, *, source: str, line: int):
    """统一 YAML 入口：重复键检测 + 环境信息注入。"""
    loader = _StrictLoader(text)
    loader._dialect_source = source  # noqa: SLF001
    loader._dialect_line = line  # noqa: SLF001
    try:
        return loader.get_single_data()
    finally:
        loader.dispose()

BLOCK_TYPES = ("endpoint", "system", "defaults", "statement", "term")
REVIEW_VALUES = ("draft", "reviewed")

# 声明块类型 → M2 模型（system/defaults 复用存量模型，payload 保持
# dict 由加载器消费——A1 不强校验，S/F 类全量规则在批次 B）
_MODEL_FOR: dict[str, type | None] = {
    "endpoint": EndpointSpec,
    "statement": Statement,
    "term": Term,
    "system": None,
    "defaults": None,
}

_FENCE_RE = re.compile(r"^(`{3,}|~{3,})\s*gimbal:(\w+)\s*$")
_HEADING_RE = re.compile(r"^#{1,6}\s")


class DialectError(ValueError):
    """方言解析错误：携带文件名与 1-based 行号。"""

    def __init__(self, message: str, *, source: str, line: int) -> None:
        super().__init__(f"{source}:{line}: {message}")
        self.source = source
        self.line = line


@dataclass
class Block:
    """一个 gimbal 块：类型 + 信封 + 载荷（M2 模型或模型列表）。"""

    type: str
    review: str = "draft"
    payload: Any = None  # 单对象 | list[对象] | dict(system/defaults)
    line: int = 0

    def models(self) -> list[Any]:
        """载荷展平为模型列表（多对象块与单对象块统一）。"""
        if isinstance(self.payload, list):
            return list(self.payload)
        return [self.payload]


@dataclass
class Prose:
    """块外散文（含标题行、空行结构原样保留；statement 原文从中派生）。"""

    text: str


Node = Union[Prose, Block]


@dataclass
class Deliverable:
    """一个交付物文件的解析结果：frontmatter + 有序节点序列。"""

    frontmatter: Frontmatter | None = None
    nodes: list[Node] = field(default_factory=list)
    source: str = "<memory>"

    def blocks(self, block_type: str | None = None) -> list[Block]:
        return [
            n for n in self.nodes
            if isinstance(n, Block) and (block_type is None or n.type == block_type)
        ]

    def statements(self) -> list[Statement]:
        """全部片段模型（text 已由块后散文派生）。"""
        out: list[Statement] = []
        for b in self.blocks("statement"):
            out.extend(m for m in b.models() if isinstance(m, Statement))
        return out


def _extract_envelope(
    data: dict[str, Any], *, source: str, line: int
) -> tuple[str, dict[str, Any]]:
    """剥离块信封 ``review``（缺省 draft）；其余键留给 M2 模型。"""
    review = data.pop("review", "draft")
    if review not in REVIEW_VALUES:
        raise DialectError(
            f"块信封 review={review!r} 非法（须为 {'/'.join(REVIEW_VALUES)}）",
            source=source, line=line,
        )
    return review, data


def _coerce_payload(
    block_type: str, data: Any, *, source: str, line: int
) -> Any:
    """YAML 载荷 → M2 模型（单对象或对象列表；system/defaults 保 dict）。"""
    model_cls = _MODEL_FOR.get(block_type)
    if model_cls is None:
        return data  # system / defaults：加载器消费，A1 不强校验
    items = data if isinstance(data, list) else [data]
    out = []
    for i, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise DialectError(
                f"gimbal:{block_type} 载荷第 {i} 项不是映射", source=source, line=line
            )
        try:
            out.append(model_cls.model_validate(item))
        except Exception as e:  # noqa: BLE001 — 统一翻译为带定位的方言错误
            raise DialectError(
                f"gimbal:{block_type} 载荷第 {i} 项校验失败: {e}",
                source=source, line=line,
            ) from e
    return out if isinstance(data, list) else out[0]


def _derive_statement_text(
    nodes: list[Node], index: int, *, source: str
) -> None:
    """片段原文 = 块后紧跟的段落，直到下一个块或标题（6.3 / 第 5 节）。"""
    block = nodes[index]
    assert isinstance(block, Block)
    parts: list[str] = []
    j = index + 1
    while j < len(nodes):
        nxt = nodes[j]
        if isinstance(nxt, Block):
            break
        # 标题行终止片段原文
        if _HEADING_RE.match(nxt.text.split("\n", 1)[0]):
            break
        parts.append(nxt.text.strip("\n"))
        j += 1
    text = "\n\n".join(p for p in (q.strip() for q in parts) if p)
    for m in block.models():
        if isinstance(m, Statement):
            m.text = text
    _ = source


def parse_markdown(text: str, *, source: str = "<memory>") -> Deliverable:
    """解析一个交付物文件。frontmatter 可缺省（无块文件 = 纯散文）。"""
    lines = text.split("\n")
    # 末尾单个换行是文件终止符而非内容行:剥掉,由 render 恒补一个,
    # 保证 render→parse→render 字节幂等(尾换行不逐轮累积)。
    if lines and lines[-1] == "":
        lines.pop()
    deliverable = Deliverable(source=source)
    i = 0

    # ── frontmatter ──
    if lines and lines[0].strip() == "---":
        end = next(
            (k for k in range(1, len(lines)) if lines[k].strip() == "---"), None
        )
        if end is None:
            raise DialectError("frontmatter 未闭合（缺少结尾 '---'）",
                               source=source, line=1)
        try:
            data = strict_yaml_load("\n".join(lines[1:end]),
                                    source=source, line=1) or {}
        except yaml.YAMLError as e:
            raise DialectError(f"frontmatter YAML 解析失败: {e}",
                               source=source, line=1) from e
        if not isinstance(data, dict):
            raise DialectError("frontmatter 须为映射", source=source, line=1)
        try:
            deliverable.frontmatter = Frontmatter.model_validate(data)
        except Exception as e:  # noqa: BLE001
            raise DialectError(f"frontmatter 校验失败: {e}",
                               source=source, line=1) from e
        i = end + 1

    # ── 正文：围栏块与散文 ──
    prose_buf: list[str] = []

    def flush_prose() -> None:
        if prose_buf:
            # 规范形纪律:Prose 节点不携带首尾空行——节点间空行由 render 的
            # "\n\n" join 统一提供,否则逐轮往返空白累积(幂等被破坏)。
            text = "\n".join(prose_buf).strip("\n")
            if text:
                deliverable.nodes.append(Prose(text=text))
            prose_buf.clear()

    while i < len(lines):
        m = _FENCE_RE.match(lines[i].rstrip())
        if m:
            fence, block_type = m.group(1), m.group(2)
            if block_type not in BLOCK_TYPES:
                raise DialectError(
                    f"未知块类型 gimbal:{block_type}（合法: "
                    f"{'/'.join('gimbal:' + t for t in BLOCK_TYPES)}）",
                    source=source, line=i + 1,
                )
            flush_prose()
            body_start = i + 1
            close = next(
                (
                    k for k in range(body_start, len(lines))
                    if lines[k].rstrip() == fence
                ),
                None,
            )
            if close is None:
                raise DialectError(f"gimbal:{block_type} 围栏未闭合",
                                   source=source, line=i + 1)
            try:
                data = strict_yaml_load("\n".join(lines[body_start:close]),
                                        source=source, line=i + 1)
            except yaml.YAMLError as e:
                raise DialectError(
                    f"gimbal:{block_type} 块体 YAML 解析失败: {e}",
                    source=source, line=i + 1,
                ) from e
            if data is None:
                data = {}
            top_is_list = isinstance(data, list)
            if not top_is_list and not isinstance(data, dict):
                raise DialectError(
                    f"gimbal:{block_type} 块体须为映射或映射列表",
                    source=source, line=i + 1,
                )
            items = data if top_is_list else [data]
            envelopes = []
            for item in items:
                if not isinstance(item, dict):
                    raise DialectError(
                        f"gimbal:{block_type} 块体列表元素须为映射",
                        source=source, line=i + 1,
                    )
                envelopes.append(_extract_envelope(item, source=source, line=i + 1))
            reviews = {r for r, _ in envelopes}
            if len(reviews) > 1:
                raise DialectError(
                    f"gimbal:{block_type} 列表块内信封不一致: {sorted(reviews)}",
                    source=source, line=i + 1,
                )
            review = reviews.pop() if reviews else "draft"
            payload_data = data if top_is_list else envelopes[0][1]
            payload = _coerce_payload(
                block_type, payload_data, source=source, line=i + 1
            )
            deliverable.nodes.append(
                Block(type=block_type, review=review, payload=payload, line=i + 1)
            )
            i = close + 1
        else:
            prose_buf.append(lines[i])
            i += 1
    flush_prose()

    # ── 片段原文派生 ──
    for idx, node in enumerate(deliverable.nodes):
        if isinstance(node, Block) and node.type == "statement":
            _derive_statement_text(deliverable.nodes, idx, source=source)

    return deliverable
