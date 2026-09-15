"""tree-sitter PHP 解析基座:文件→语法树 + 节点文本/遍历/类定位助手。

节点类型事实(probe 实录,见 plan Global Constraints):
class_declaration→declaration_list→method_declaration/property_element/
const_declaration;调用族 function_call_expression/member_call_expression/
scoped_call_expression/subscript_expression。
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import tree_sitter_php
from tree_sitter import Language, Parser, Node


@lru_cache(maxsize=1)
def _parser() -> Parser:
    return Parser(Language(tree_sitter_php.language_php()))


@dataclass
class ParsedFile:
    path: Path
    tree: object
    src: bytes

    def walk(self):
        yield from _walk(self.tree.root_node)


def _walk(node: Node):
    yield node
    for child in node.children:
        yield from _walk(child)


def load(path: str | Path) -> ParsedFile:
    p = Path(path)
    return ParsedFile(path=p, tree=_parser().parse(p.read_bytes()), src=p.read_bytes())


def text_of(pf: ParsedFile, node: Node) -> str:
    """节点原文(带引号/引号符,如 'require|num')。"""
    return pf.src[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def classes(pf: ParsedFile) -> list[tuple[str, Node, Node]]:
    """[(类名, class_declaration, declaration_list)],不含匿名/错误节点。"""
    out = []
    for n in pf.walk():
        if n.type != "class_declaration":
            continue
        name = next((c for c in n.children if c.type == "name"), None)
        decl = next((c for c in n.children if c.type == "declaration_list"), None)
        if name is not None and decl is not None:
            out.append((text_of(pf, name), n, decl))
    return out
