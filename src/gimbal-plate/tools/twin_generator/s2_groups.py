"""T5.3 行容器分组检测:foreach + paramVerification(Validator::$prop, $v)。

权威源 CustomerController::checkBase 五组(customer_team/contact/
bill_lading/finance/association):容器键是 $requestData 的下标,
行规则来自 Validator 静态属性,paramVerification 第二实参是行变量。
检测是纯文本的(方法体内正则),规则解析复用 s2_validator。
"""
from __future__ import annotations

import re
from pathlib import Path

from .ir import ActionIR, RuleEntry
from .php_ast import load, text_of, classes
from .s2_reads import _params
from .s2_validator import parse_rules_file

# foreach ($requestData['customer_team'] as $k => $v) / as $v(无键变体)
_RE_FOREACH = re.compile(
    r"foreach\s*\(\s*\$requestData\[['\"](\w+)['\"]\]\s+as\s+"
    r"(?:\$\w+\s*=>\s*)?\$(\w+)\s*\)")
# paramVerification( XxxValidator::$prop , $v , ...) —— 调用风格不限
# (CustomerService::getInstance()->paramVerification / (new BaseService())->…)
_RE_PARAMV = re.compile(r"paramVerification\s*\(\s*(\w+)::\$(\w+)\s*,\s*\$(\w+)")
_WINDOW = 600      # foreach 之后找 paramVerification 的窗口(字节)
# order 族容器信号:Validator check 方法内 getDataArray($requestData, 'key')
# (OrderValidator::checkContainer/checkServiceItem/checkSupplier 实证 ——
# 这些容器不走 foreach+paramVerification,行结构只在 DB 表里)
_RE_GETDATAARR = re.compile(
    r"getDataArray\s*\(\s*\$(\w+)\s*,\s*['\"](\w+)['\"]")


def detect_groups(actions: list[ActionIR],
                  app_root: Path) -> dict[str, list[tuple[str, list[RuleEntry]]]]:
    """act.id → [(容器键, 行规则列表)]。

    扫描控制器方法体文本;Validator 规则经 parse_rules_file 索引解析
    (类名全局唯一,prop 是静态属性名)。
    """
    want: dict[tuple[str, str], list[ActionIR]] = {}   # (controller, action)
    for a in actions:
        want.setdefault((a.controller, a.action), []).append(a)

    # Validator 索引:类名 → prop → entries(attach_rules 同款扫描)
    vindex: dict[str, dict[str, list[RuleEntry]]] = {}
    for f in sorted(app_root.glob("*/Validator/*.class.php")):
        for cname, *_ in classes(load(f)):
            vindex[cname] = parse_rules_file(f)

    out: dict[str, list[tuple[str, list[RuleEntry]]]] = {}
    for f in sorted(app_root.glob("*/Controller/*.class.php")):
        pf = load(f)
        for cname, _c, decl in classes(pf):
            ctrl = cname[:-len("Controller")] if cname.endswith("Controller") else cname
            for m in decl.children:
                if m.type != "method_declaration":
                    continue
                mn = next((c for c in m.children if c.type == "name"), None)
                if mn is None or (ctrl, text_of(pf, mn)) not in want:
                    continue
                body = text_of(pf, m)
                found: list[tuple[str, list[RuleEntry]]] = []
                seen: set[str] = set()
                for fm in _RE_FOREACH.finditer(body):
                    container, val_var = fm.group(1), fm.group(2)
                    if container in seen:
                        continue
                    pm = _RE_PARAMV.search(body, fm.end(), fm.end() + _WINDOW)
                    if not pm or pm.group(3) != val_var:
                        continue
                    entries = vindex.get(pm.group(1), {}).get(pm.group(2))
                    if not entries:
                        continue
                    seen.add(container)
                    found.append((container, entries))
                if found:
                    for a in want[(ctrl, text_of(pf, mn))]:
                        out.setdefault(a.id, []).extend(found)
    return out


def detect_containers(actions: list[ActionIR],
                      app_root: Path) -> dict[str, list[str]]:
    """act.id → [容器键](getDataArray 信号,order 族)。

    扫描动作绑定的 Validator check 方法体内的 getDataArray($param, 'key'),
    要求实参变量是该方法形参(即请求载体)。与 detect_groups 分开返回:
    该信号无行规则,children 由 S3 按容器表(sys_<module>_<key>)解析。
    同名 check 方法跨 Validator 存在时:模块一致 > 类名=控制器+Validator > 首现。
    """
    if not actions:
        return {}
    # Validator 索引:类名 → (模块, pf, {方法名: (node, 形参集)})
    vfiles: dict[str, tuple[str, object, dict[str, tuple]]] = {}
    for f in sorted(app_root.glob("*/Validator/*.class.php")):
        module = f.parent.parent.name
        pf = load(f)
        for cname, _c, decl in classes(pf):
            methods: dict[str, tuple] = {}
            for m in decl.children:
                if m.type != "method_declaration":
                    continue
                n = next((c for c in m.children if c.type == "name"), None)
                if n:
                    methods[text_of(pf, n)] = m
            vfiles[cname] = (module, pf, methods)

    out: dict[str, list[str]] = {}
    for a in actions:
        if not a.validator_checks:
            continue
        stem = a.controller + "Validator"
        mod_l = a.module.lower()
        found: list[str] = []
        seen: set[str] = set()
        for chk in a.validator_checks:
            cands = [(cname, mod, pf, m)
                     for cname, (mod, pf, methods) in vfiles.items()
                     if (m := methods.get(chk)) is not None]
            if not cands:
                continue
            pick = (next((c for c in cands if c[1].lower() == mod_l), None)
                    or next((c for c in cands if c[0] == stem), None)
                    or cands[0])
            _cname, _mod, pf, m = pick
            body = text_of(pf, m)
            params = set(_params(pf, m))
            for gm in _RE_GETDATAARR.finditer(body):
                if gm.group(1) not in params:
                    continue
                key = gm.group(2)
                if key not in seen:
                    seen.add(key)
                    found.append(key)
        if found:
            out[a.id] = found
    return out
