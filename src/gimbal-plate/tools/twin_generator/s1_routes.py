"""S1 路由发现:Application/*/Controller/*.class.php → ActionIR 清单。

约定(plan Global Constraints,26 个手建 endpoint 实证):
path = /api/<module小写>/<controller去Controller首字母小写>/<action>;
排除模块 Script/Template/Event/Corn/Common;排除 Base* 类、_ 前缀/魔术方法、
非 public 方法。控制器体内解析:paramVerification(Xxx::$prop) 绑定、
XxxValidator::checkYyy() 静态校验、Xxx::getInstance()->yyy()/new Xxx() 服务边。
"""
from __future__ import annotations

import re
from pathlib import Path

from .php_ast import ParsedFile, load, text_of, classes
from .ir import ActionIR

EXCLUDED_MODULES = {"Script", "Template", "Event", "Corn", "Common"}
_MAGIC = {"__construct", "__destruct", "__get", "__set", "__call", "__clone"}

_RE_RULESET = re.compile(r"^(\w+)::\$(\w+)$")           # 节点级文本,安全


def _is_public(method_node, pf: ParsedFile) -> bool:
    texts = [text_of(pf, c) for c in method_node.children
             if c.type in ("visibility_modifier", "static_modifier")]
    return any(t == "public" for t in texts) and not any(
        "static" in t for t in texts)


def _method_name(method_node, pf: ParsedFile) -> str | None:
    n = next((c for c in method_node.children if c.type == "name"), None)
    return text_of(pf, n) if n else None


def scan_actions(app_root: Path) -> list[ActionIR]:
    out: list[ActionIR] = []
    for ctl_file in sorted(app_root.glob("*/Controller/*.class.php")):
        module = ctl_file.parent.parent.name
        if module in EXCLUDED_MODULES:
            continue
        pf = load(ctl_file)
        for cname, _cnode, decl in classes(pf):
            if cname.startswith("Base"):
                continue
            controller = cname[:-10] if cname.endswith("Controller") else cname
            for child in decl.children:
                if child.type != "method_declaration":
                    continue
                mname = _method_name(child, pf)
                if (not mname or mname.startswith("_") or mname in _MAGIC
                        or not _is_public(child, pf)):
                    continue
                act = _bind(load(ctl_file), child, module, controller, mname)
                out.append(act)
    return out


def _bind(pf: ParsedFile, method_node, module: str, controller: str, action: str) -> ActionIR:
    act = ActionIR(module=module, controller=controller, action=action)
    # 真源实测(task-10 OrderController::orderAdd):规则可经局部变量间接绑定
    # ($rule = OrderValidator::$orderAddRules; ... paramVerification($rule))。
    # 先整树扫一遍建 变量名 → (Validator 类, 属性) 映射,再解析调用。
    var_rules: dict[str, tuple[str, str]] = {}
    scan = [method_node]
    while scan:
        n = scan.pop()
        scan.extend(n.children)
        if n.type != "assignment_expression":
            continue
        kids = n.children
        if len(kids) == 3 and kids[0].type == "variable_name":
            m = _RE_RULESET.match(text_of(pf, kids[2]).strip())
            if m:
                # variable_name 文本带 $;键存裸名与 paramVerification($var) 对齐
                var_rules[text_of(pf, kids[0]).lstrip("$")] = (
                    m.group(1), m.group(2))
    stack = [method_node]
    while stack:
        n = stack.pop()
        stack.extend(n.children)
        t = n.type
        # probe 实录:$this->paramVerification(...) 是 member_call_expression
        # (方法名 name 为直接子节点,`this` 嵌在 variable_name 里,_callee 两者通吃)
        if (t in ("function_call_expression", "member_call_expression")
                and _callee(pf, n) == "paramVerification"):
            args = [c for c in n.children if c.type == "arguments"]
            for arg in _arg_nodes(args[0]) if args else []:
                txt = text_of(pf, arg).strip()
                m = _RE_RULESET.match(txt)
                if m:
                    act.ruleset = (m.group(1), m.group(2))
                elif txt.startswith("$") and txt[1:] in var_rules:
                    act.ruleset = var_rules[txt[1:]]
        elif t == "scoped_call_expression":
            names = [c for c in n.children if c.type == "name"]
            if len(names) == 2:
                cls, meth = text_of(pf, names[0]), text_of(pf, names[1])
                if cls.endswith("Validator") and meth.startswith("check"):
                    act.validator_checks.append(meth)
        elif t == "member_call_expression":
            base = n.children[0] if n.children else None
            if base is not None and base.type == "scoped_call_expression":
                inner = [c for c in base.children if c.type == "name"]
                meth = next((c for c in n.children if c.type == "name"), None)
                if len(inner) >= 1 and meth is not None:
                    act.callees.append((text_of(pf, inner[0]), text_of(pf, meth)))
    return act


def _callee(pf: ParsedFile, call_node) -> str:
    n = next((c for c in call_node.children if c.type == "name"), None)
    return text_of(pf, n) if n else ""


def _arg_nodes(args_node) -> list:
    return [c for c in args_node.children if c.type == "argument"]
