"""gimbal_plate.dialect —— Markdown 方言内核（批次 A1）。

公开 API：
- :func:`parse_markdown` —— 文本 → ``Deliverable``（frontmatter + 节点序列）
- :func:`render` —— ``Deliverable`` → 规范形 Markdown
- :func:`object_hash` / :func:`shape_hash` —— 内容寻址与适配检测指纹
- :func:`canonical_bytes` / :func:`canonical_payload` —— 规范序列化

设计真源：``claude/plate-design.md``（第 5、6、7.1、7.2 节）。
"""
from .canonical import (
    canonical_bytes,
    canonical_payload,
    object_hash,
    shape_hash,
    shape_projection,
)
from .models import (
    Binding,
    EndpointSpec,
    Frontmatter,
    HttpBinding,
    RequestSpec,
    ResponseSpec,
    Statement,
    Term,
)
from .parser import (
    BLOCK_TYPES,
    Block,
    Deliverable,
    DialectError,
    Prose,
    parse_markdown,
)
from .renderer import render, render_block, render_frontmatter

__all__ = [
    "BLOCK_TYPES",
    "Binding",
    "Block",
    "Deliverable",
    "DialectError",
    "EndpointSpec",
    "Frontmatter",
    "HttpBinding",
    "Prose",
    "RequestSpec",
    "ResponseSpec",
    "Statement",
    "Term",
    "canonical_bytes",
    "canonical_payload",
    "object_hash",
    "parse_markdown",
    "render",
    "render_block",
    "render_frontmatter",
    "shape_hash",
    "shape_projection",
]
