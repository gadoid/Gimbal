"""S2b:Service/Validator 读取树 —— 控制器动作为根的调用图 BFS + 键读收集。

精确度取舍(写入文档而非隐瞒):known-var 单级别名($x = $requestData);
数组解包/foreach/extract 不追(残差由 S5 对照报告兜底)。

节点形状实测修正(相对 brief 草案,probe 见 task-5 报告):
- assignment_expression 子节点 = [variable_name, '='(匿名), variable_name]:
  赋值源是 kids[2] 而非 kids[1](brief 原判永远指到 `=` 操作符);
- isset/empty($var['k']) 里 args[0] 是 argument 包裹节点(剥壳后才是
  subscript_expression),brief 原判 a0.type == "subscript_expression" 永不成立;
- isset/empty 确为 function_call_expression(无专用节点),brief 假设成立。
"""
from __future__ import annotations

from pathlib import Path

from .php_ast import ParsedFile, load, text_of, classes, is_string_literal
from .ir import ActionIR, Read

_GET_DATA = {"getDataString", "getDataInt", "getDataFloat",
             "getDataArray", "getDataBool"}
_ISSET = {"isset", "empty"}


class _ClassIndex:
    """类名 → 方法名 → (method_node, ParsedFile);全 Application 扫描。"""

    def __init__(self, app_root: Path):
        self.methods: dict[str, dict[str, tuple]] = {}
        for f in sorted(app_root.rglob("*.class.php")):
            pf = load(f)
            for cname, _c, decl in classes(pf):
                bucket = self.methods.setdefault(cname, {})
                for m in decl.children:
                    if m.type != "method_declaration":
                        continue
                    n = next((c for c in m.children if c.type == "name"), None)
                    if n:
                        bucket[text_of(pf, n)] = (m, pf)


def _var_name(pf: ParsedFile, node) -> str:
    """variable_name 节点的裸名(去 $)。"""
    for c in node.children:
        if c.type == "name":
            return text_of(pf, c)
    return text_of(pf, node).lstrip("$")


def _params(pf: ParsedFile, method_node) -> list[str]:
    out = []
    fp = next((c for c in method_node.children if c.type == "formal_parameters"), None)
    if fp:
        for p in fp.children:
            if p.type == "simple_parameter":
                vn = next((c for c in p.children if c.type == "variable_name"), None)
                if vn:
                    out.append(_var_name(pf, vn))
    return out


def _string_content(pf: ParsedFile, str_node) -> str:
    sc = next((c for c in str_node.children if c.type == "string_content"), None)
    if sc is not None:
        return text_of(pf, sc)
    t = text_of(pf, str_node)
    return t[1:-1] if len(t) >= 2 and t[0] in "'\"" else t


def _collect(pf: ParsedFile, method_node, known: set[str], edges: list,
             reads: dict[str, Read]) -> None:
    """单方法体一次遍历:读三类 + 调用边(带实参位置) + 单级别名。"""
    skip: set[int] = set()          # isset/empty 已消费的 subscript 节点
    # children 逆序入栈 → pop 出来是源码顺序:别名($data = $requestData)先于
    # 后续消费($data 走 getData)被记入 known;父调用先于其内层 subscript。
    stack = list(reversed(method_node.children))
    while stack:
        n = stack.pop()
        stack.extend(reversed(n.children))
        t = n.type
        if t == "function_call_expression":
            name = ""
            for c in n.children:
                if c.type == "name":
                    name = text_of(pf, c)
            args_node = next((c for c in n.children if c.type == "arguments"), None)
            args = [c for c in args_node.children if c.type == "argument"] if args_node else []
            if name in _GET_DATA and len(args) >= 2:
                key_n = _first_string(args[1])
                if key_n is not None and _arg_var(pf, args[0]) in known:
                    default = None
                    if len(args) >= 3:
                        dn = _first_string(args[2])
                        default = _string_content(pf, dn) if dn else None
                    key = _string_content(pf, key_n)
                    reads.setdefault(key, Read(key=key, default=default, via="getData"))
            elif name in _ISSET and args:
                # 实测:args[0] 是 argument 包裹节点,subscript 是其子
                a0 = args[0].children[0] if args[0].children else args[0]
                if a0.type == "subscript_expression":
                    sub = _subscript_parts(pf, a0)
                    if sub and sub[0] in known:
                        reads.setdefault(sub[1], Read(key=sub[1], via="isset"))
                        skip.add(a0.id)
        elif t == "subscript_expression":
            if n.id not in skip:
                sub = _subscript_parts(pf, n)
                if sub and sub[0] in known:
                    reads.setdefault(sub[1], Read(key=sub[1], via="subscript"))
        elif t == "assignment_expression":
            # 实测:$x = $y → [variable_name, '='(匿名), variable_name],源在 kids[2]
            kids = n.children
            if len(kids) == 3 and kids[0].type == "variable_name" \
                    and kids[1].type == "=":
                if kids[2].type == "variable_name":
                    src = _var_name(pf, kids[2])
                    if src in known:
                        known.add(_var_name(pf, kids[0]))
                elif kids[2].type == "function_call_expression" \
                        and _call_name(pf, kids[2]) == "getRequestParam":
                    # Service 自取请求(getRequestParam() 是全局函数,返回即请求体)
                    known.add(_var_name(pf, kids[0]))
        elif t == "member_call_expression":
            base = n.children[0] if n.children else None
            meth = next((c for c in n.children if c.type == "name"), None)
            args_node = next((c for c in n.children if c.type == "arguments"), None)
            if base is not None and base.type == "scoped_call_expression" and meth:
                cls = next((c for c in base.children if c.type == "name"), None)
                if cls:
                    _edge(edges, text_of(pf, cls), text_of(pf, meth),
                          _arg_positions(pf, args_node, known))
        elif t == "scoped_call_expression":
            # 直接静态调用(如 Validator::checkXxx($requestData));
            # 跳过getInstance(它是 member_call 基座,边由上一分支记)
            names = [c for c in n.children if c.type == "name"]
            args_node = next((c for c in n.children if c.type == "arguments"), None)
            if len(names) == 2 and text_of(pf, names[1]) != "getInstance":
                _edge(edges, text_of(pf, names[0]), text_of(pf, names[1]),
                      _arg_positions(pf, args_node, known))
        elif t == "object_creation_expression":
            name = next((c for c in n.children if c.type == "name"), None)
            if name:
                _edge(edges, text_of(pf, name), "__construct", [])


def _edge(edges, cls: str, meth: str, arg_pos: list[int]) -> None:
    edges.append((cls, meth, arg_pos))


def _arg_positions(pf: ParsedFile, args_node, known: set[str]) -> list[int]:
    """实参里哪些位置传的是 known-var(位置索引从 0 计)。"""
    out = []
    if args_node is None:
        return out
    for i, a in enumerate(c for c in args_node.children if c.type == "argument"):
        if _arg_var(pf, a) in known:
            out.append(i)
    return out


def _arg_var(pf: ParsedFile, arg) -> str:
    """实参(argument 节点包一层表达式)内取 variable_name 裸名;非变量返回 ''。"""
    node = arg
    if arg.type == "argument":
        node = next((c for c in arg.children if c.type == "variable_name"), None)
        if node is None:
            return ""
    return _var_name(pf, node) if node is not None and node.type == "variable_name" else ""


def _call_name(pf: ParsedFile, call_node) -> str:
    """function_call_expression 的函数名直接子节点。"""
    n = next((c for c in call_node.children if c.type == "name"), None)
    return text_of(pf, n) if n else ""


def _first_string(arg):
    """argument 内第一个字符串字面量节点(含双引号 encapsed_string,
    task-10 真源实测);没有(如 [] 默认参)返回 None。"""
    return next((c for c in arg.children if is_string_literal(c)), None)


def _subscript_parts(pf: ParsedFile, node) -> tuple[str, str] | None:
    """subscript_expression → (变量裸名, 字符串键);非字符串键返回 None。"""
    var = key = None
    for c in node.children:
        if c.type == "variable_name":
            var = _var_name(pf, c)
        elif is_string_literal(c):
            key = _string_content(pf, c)
    return (var, key) if var and key else None


def collect_reads(actions: list[ActionIR], app_root: Path) -> None:
    idx = _ClassIndex(app_root)
    for act in actions:
        ctl_class = act.controller + "Controller"
        visited: set[tuple[str, str]] = set()
        reads: dict[str, Read] = {}
        # 队列:(类, 方法, 进入时已知的变量名集)
        # 根动作与 Validator 校验方法确实持有 $requestData;Service 边一律经
        # 实参位置链接传入(task-10 实测:无条件种 requestData + 形参全量入
        # known 会把 OrderService::orderBook 的读取面串给 orderBookUpdate ——
        # 它实际只传 order_id)。
        queue: list[tuple[str, str, frozenset]] = []
        # 根动作与 Validator 校验方法确实持有 $requestData:种 requestData 并
        # 并入各自形参名(校验方法形参即请求体);控制器直调的 Service 以形参名
        # 判定(形参恰名 requestData 视为请求载体);此后 known 只经实参链接
        # 传递,不再把被调方法形参全量当已知 —— task-10 实测:orderBookUpdate
        # 只传 order_id,却因 orderBook 形参恰名 requestData 被串进整张订单读取面。
        plan: list[tuple[str, str, set]] = [
            (ctl_class, act.action, {"requestData"}),
            *((act.controller + "Validator", chk, {"requestData"})
              for chk in act.validator_checks)]
        for e_cls, e_meth in act.callees:
            entry1 = idx.methods.get(e_cls, {}).get(e_meth)
            if entry1 is None:
                continue
            holds_request = "requestData" in set(_params(entry1[1], entry1[0]))
            plan.append((e_cls, e_meth, {"requestData"} if holds_request else set()))
        for cls, meth, extra in plan:
            entry0 = idx.methods.get(cls, {}).get(meth)
            if not entry0:
                continue
            queue.append((cls, meth,
                          frozenset(extra | set(_params(entry0[1], entry0[0])))))
        while queue:
            cls, meth, known = queue.pop(0)
            if (cls, meth) in visited:
                continue
            visited.add((cls, meth))
            entry = idx.methods.get(cls, {}).get(meth)
            if not entry:
                continue
            node, pf = entry
            k = set(known)
            edges: list[tuple[str, str, list[int]]] = []
            _collect(pf, node, k, edges, reads)
            for e_cls, e_meth, positions in edges:
                entry2 = idx.methods.get(e_cls, {}).get(e_meth)
                if not entry2:
                    continue
                callee_params = _params(entry2[1], entry2[0])
                linked = {callee_params[p] for p in positions
                          if p < len(callee_params)}
                queue.append((e_cls, e_meth, frozenset(linked)))
        act.reads = reads
