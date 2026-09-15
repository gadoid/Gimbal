"""S2a:Validator $xxxRules 数组抽取 —— 活跃行 + 被注释行(中文注释都在)。

行结构(tree-sitter 实测,见 task-4 报告):
declaration_list → property_declaration → property_element
  → variable_name → name(属性名)
  → array_creation_expression → [array_element_initializer, ',', comment(同行行尾), ...]
被注释规则行是 array_creation_expression 下的独立 comment 节点,文本形如
  // 'carrier'                => 'present', //船公司/承运人
comment 节点内部用正则解析(节点级文本,安全)。
"""
from __future__ import annotations

import re
from pathlib import Path

from .php_ast import ParsedFile, load, text_of, classes, is_string_literal
from .ir import RuleEntry, ActionIR

# 被注释规则行:行尾 // 中文注可有可无(真源 orderAddRules 实测有 11 行无尾注,
# 如 `//        'settle_type' => 'present|num|in:1,2',` —— 只认尾注会整行丢)
_RE_COMMENTED_RULE = re.compile(
    r"//\s*'([A-Za-z0-9_]+)'\s*=>\s*'([^']*)'\s*,?(?:\s*//\s*(.+))?$"
)


def parse_rules_file(path: Path) -> dict[str, list[RuleEntry]]:
    pf = load(path)
    out: dict[str, list[RuleEntry]] = {}
    for _name, _cnode, decl in classes(pf):
        _parse_decl(pf, decl, out)
    return out


def _parse_decl(pf: ParsedFile, decl, out: dict) -> None:
    for prop_decl in decl.children:
        if prop_decl.type != "property_declaration":
            continue
        prop = next((c for c in prop_decl.children
                     if c.type == "property_element"), None)
        if prop is None:
            continue
        name_n = _prop_name(pf, prop)
        if name_n is None:
            continue
        entries: list[RuleEntry] = []
        arr = next((c for c in prop.children
                    if c.type == "array_creation_expression"), None)
        # named_children:滤掉匿名分隔符 ',' —— 否则 elements[i+1] 是逗号
        # 而非同行行尾 comment(comment 是命名节点)
        children = list(arr.named_children) if arr is not None else []
        for i, node in enumerate(children):
            if node.type == "array_element_initializer":
                # 双引号值是 encapsed_string(task-10 真源实测),不只 string
                strs = [c for c in node.children if is_string_literal(c)]
                if len(strs) != 2:
                    continue
                zh = ""
                nxt = children[i + 1] if i + 1 < len(children) else None
                if nxt is not None and nxt.type == "comment" \
                        and nxt.start_point[0] == node.start_point[0]:
                    zh = _strip_comment(text_of(pf, nxt))
                entries.append(RuleEntry(
                    key=_unquote(text_of(pf, strs[0])),
                    rules=_unquote(text_of(pf, strs[1])),
                    zh=zh, active=True,
                ))
            elif node.type == "comment":
                m = _RE_COMMENTED_RULE.search(text_of(pf, node))
                if m:
                    entries.append(RuleEntry(
                        key=m.group(1), rules=m.group(2),
                        zh=(m.group(3) or "").strip(), active=False,
                    ))
        out[text_of(pf, name_n)] = entries


def _prop_name(pf: ParsedFile, prop):
    """property_element → variable_name → name(实测无直接 name 子节点)。"""
    vn = next((c for c in prop.children if c.type == "variable_name"), None)
    if vn is None:
        return None
    n = next((c for c in vn.children if c.type == "name"), None)
    return n


def _strip_comment(t: str) -> str:
    return t.lstrip("/ ").strip()


def _unquote(t: str) -> str:
    inner = t[1:-1] if len(t) >= 2 and t[0] in "'\"" else t
    return inner


def attach_rules(actions: list[ActionIR], app_root: Path) -> None:
    """显式 ruleset 绑定优先;无绑定时按 $<action>Rules / $<action>Rule 兜底。
    Validator 文件按 Application/*/Validator/*.class.php 扫描一次建索引。
    兜底重名撞车时优先同模块类(task-10:changeSettlementDateRuleS 在
    Customer 模块 Customer/Supplier 两 Validator 重名,Order 模块亦多处)。"""
    index: dict[str, dict[str, list[RuleEntry]]] = {}   # 类名 → prop → entries
    mod_of: dict[str, str] = {}                          # 类名 → 模块
    for f in sorted(app_root.glob("*/Validator/*.class.php")):
        module = f.parent.parent.name
        for cname, *_ in classes(load(f)):
            index[cname] = parse_rules_file(f)
            mod_of[cname] = module
    for act in actions:
        if act.ruleset:
            cls, prop = act.ruleset
            act.rules = list(index.get(cls, {}).get(prop, []))
            continue
        for suffix in ("Rules", "Rule"):
            name = act.action + suffix
            hits = [(cls, props[name]) for cls, props in index.items()
                    if props.get(name)]
            if hits:
                same = [h for h in hits if mod_of[h[0]] == act.module]
                cls, entries = (same or hits)[0]
                act.rules = list(entries)
                break
