"""REST 契约快照(审计批次⑤轻量切片,登记册 B5;2026-11-20)。

后端 REST 契约两份快照入库,漂移即红:

* ``contract/openapi.json`` —— ``create_app().openapi()`` 原样落盘
  (199 路径 / 211 schema 量级):请求/响应形状的漂移守卫。FastAPI 版本
  钉在 requirements.lock,生成确定(sort_keys 钉死键序)。
* ``contract/error-codes.json`` —— AST 静态提取的错误码清单。openapi
  不含错误负载形状(错误响应无 response_model),错误码单独建面,覆盖
  四类间接形态:

  1. ``detail={"code": "<字面量>"}`` 直写(主体);
  2. ``_codes.py`` 整型码(auth/users 契约):``code_detail(NAME)`` 与
     ``{"code": NAME}`` 名字解析;
  3. 带码业务异常类(``__init__`` 里 ``self.code = code``,12 个)的
     raise 位点 —— code 参数按各类签名定位(``PromotionError(status,
     code, ...)`` 的 code 在第二位);
  4. 透传 helper(``_bad`` 型:函数体 raise/return HTTPException 且
     detail.code 取自参数)的调用位点 —— 含 ``await assert_name_available
     (code=NAME_TAKEN)`` 这类非 raise 位调用;``at.ERR_*`` 模块常量同解析。

子命令(仿 ``gen_m2.py``)::

    gen    重生两份快照入库(契约变更须随提交重生)
    check  在内存重生,与入库快照逐字节比对 —— 漂移即非零退出
           (CI 显式步骤 + backend pytest test_api_contract 双守卫)

非字面量 code 位点(``e.code`` 透传 / f-string 插值 / 运行时取值)逐处
登记进 ``dynamic`` 面:其取值由对应异常/helper 调用位点枚举,位点增删
本身即契约变化。无码的纯 message detail 不入面;消息模板、动态拼码的
展开值不在快照面(由测试钉)。

治本全量(前端类型 codegen 单源化、错误码表前端接入)另见登记册 B5。
"""
from __future__ import annotations

import argparse
import ast
import difflib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "src" / "gimbal-platform" / "backend"
CONTRACT = BACKEND / "contract"
OPENAPI_JSON = CONTRACT / "openapi.json"
ERROR_CODES_JSON = CONTRACT / "error-codes.json"
SCAN_ROOT = BACKEND / "app"
CODES_MODULE_STEM = "_codes"          # app/routers/_codes.py:整型码单源


# ── openapi 面 ────────────────────────────────────────────────
def build_openapi_text() -> str:
    """``create_app().openapi()`` 归一化落盘文本(sort_keys 钉死键序)。"""
    sys.path.insert(0, str(BACKEND))
    # 契约面只读路由/模型,不连库;但 app.core.db 导入期即校验 DATABASE_URL
    # 形状(SQLite 退役 fail-fast)—— 干净检出无 backend/.env(CI)时给占位
    # PG 形态,调用方环境已有的值不覆盖。
    os.environ.setdefault(
        "DATABASE_URL", "postgresql+asyncpg://contract:snapshot@localhost/contract")
    from app.main import create_app          # noqa: PLC0415(脚本形态)
    spec = create_app().openapi()
    return json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


# ── 错误码面(AST 静态提取) ────────────────────────────────────
@dataclass
class CodeSite:
    code: str
    file: str
    line: int
    status: int | None = None
    name: str | None = None                 # _codes 常量名(整型码)
    shape: tuple[str, ...] | None = None    # detail 兄弟键(形状契约)


@dataclass
class _CodedExc:
    """带 ``self.code = code`` 的业务异常类(code 参数按签名定位)。"""
    home: str
    line: int
    params: list[str]                      # __init__ 参数名序(不含 self)

    def arg(self, call: ast.Call, param: str) -> ast.expr | None:
        v = _kwarg(call, param)
        if v is None and param in self.params:
            i = self.params.index(param)
            if i < len(call.args):
                v = call.args[i]
        return v


@dataclass
class _Helper:
    """raise/return HTTPException 且 detail.code 取自参数的透传函数。"""
    module: str
    func: str
    code_param: str
    params: list[str]                      # 位置参数名序
    status_param: str | None = None
    status_default: int | None = None

    def arg(self, call: ast.Call, param: str) -> ast.expr | None:
        v = _kwarg(call, param)
        if v is None and param in self.params:
            i = self.params.index(param)
            if i < len(call.args):
                v = call.args[i]
        return v


@dataclass
class _FileCtx:
    """单文件解析上下文:名字可见性 + 常量解析源。"""
    rel: str
    int_codes: dict[str, tuple[str, int]]
    mod_aliases: dict[str, str] = field(default_factory=dict)   # 模块别名 → 文件
    module_consts: dict[str, dict[str, str]] = field(default_factory=dict)


def _rel(p: Path) -> str:
    return p.relative_to(BACKEND).as_posix()


def _parse_all() -> dict[str, ast.Module]:
    trees: dict[str, ast.Module] = {}
    for p in sorted(SCAN_ROOT.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        trees[_rel(p)] = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
    return trees


def _load_int_codes(trees: dict[str, ast.Module]) -> dict[str, tuple[str, int]]:
    """``_codes.py`` 常量名 → (十进制码串, 值)。"""
    for rel, tree in trees.items():
        if not rel.endswith(f"/{CODES_MODULE_STEM}.py"):
            continue
        out: dict[str, tuple[str, int]] = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name) \
                    and isinstance(node.value, ast.Constant) and isinstance(node.value.value, int):
                out[node.targets[0].id] = (str(node.value.value), node.value.value)
        return out
    raise SystemExit(f"未找到 {CODES_MODULE_STEM}.py(整型码单源)")


def _module_constants(trees: dict[str, ast.Module]) -> dict[str, dict[str, str]]:
    """模块级字符串常量(``ERR_*`` 型)——跨文件码值单源。"""
    out: dict[str, dict[str, str]] = {}
    for rel, tree in trees.items():
        consts: dict[str, str] = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name) \
                    and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                consts[node.targets[0].id] = node.value.value
        if consts:
            out[rel] = consts
    return out


def _discover_coded_exceptions(trees: dict[str, ast.Module]) -> dict[str, _CodedExc]:
    """``self.code = code`` 的异常类:名字独特的类按裸名/属名匹配 raise。"""
    found: dict[str, _CodedExc] = {}
    for rel, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for item in ast.walk(node):
                if (isinstance(item, ast.Assign) and len(item.targets) == 1
                        and isinstance(item.targets[0], ast.Attribute)
                        and item.targets[0].attr == "code"
                        and isinstance(item.targets[0].value, ast.Name)
                        and item.targets[0].value.id == "self"
                        and isinstance(item.value, ast.Name) and item.value.id == "code"):
                    for fn in ast.walk(node):
                        if isinstance(fn, ast.FunctionDef) and fn.name == "__init__":
                            params = [a.arg for a in
                                      [*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs]]
                            found[node.name] = _CodedExc(
                                rel, node.lineno, params[1:])  # 去 self
                            break
                    break
    return found


def _func_params(fn: ast.FunctionDef | ast.AsyncFunctionDef
                 ) -> tuple[list[str], dict[str, int | None]]:
    names: list[str] = []
    defaults: dict[str, int | None] = {}
    a = fn.args
    pos = [*a.posonlyargs, *a.args]
    d = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)
    for arg, default in zip(pos, d):
        names.append(arg.arg)
        defaults[arg.arg] = default.value if isinstance(default, ast.Constant) \
            and isinstance(default.value, int) else None
    for arg, default in zip(a.kwonlyargs, a.kw_defaults):
        names.append(arg.arg)
        defaults[arg.arg] = default.value if isinstance(default, ast.Constant) \
            and isinstance(default.value, int) else None
    return names, defaults


def _discover_helpers(trees: dict[str, ast.Module]) -> dict[tuple[str, str], _Helper]:
    """函数体 raise/return ``HTTPException(detail={"code": <本函数参数>})``
    → helper;其调用位点的字面量/常量参数即真实错误码(``_bad`` 型、
    ``assert_name_available`` 型)。"""
    helpers: dict[tuple[str, str], _Helper] = {}
    for rel, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            params, defaults = _func_params(node)
            hit: tuple[str, int | None] | None = None
            for call in _walk_scope(node):
                if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                        and call.func.id == "HTTPException"):
                    continue
                detail = _kwarg(call, "detail") or (call.args[1] if len(call.args) >= 2 else None)
                if not (isinstance(detail, ast.Dict) and _dict_get(detail, "code") is not None):
                    continue
                cv = _dict_get(detail, "code")
                if isinstance(cv, ast.Name) and cv.id in params:
                    status = _kwarg(call, "status_code") \
                        or (call.args[0] if call.args else None)
                    status_lit = None
                    if isinstance(status, ast.Name):
                        status_lit = defaults.get(status.id)
                    status_lit = _status_literal(status) if status_lit is None else status_lit
                    hit = (cv.id, status_lit)
                    break
            if hit:
                sp = next((p for p in params if "status" in p and p != hit[0]), None)
                helpers[(rel, node.name)] = _Helper(
                    module=rel, func=node.name, code_param=hit[0],
                    params=params, status_param=sp, status_default=hit[1])
    return helpers


def _walk_scope(node: ast.AST):
    """作用域内节点迭代:不进嵌套函数/类/λ(各自独立成域)。"""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.Lambda, ast.ClassDef)):
            continue
        yield child
        yield from _walk_scope(child)


def _status_literal(node: ast.expr | None) -> int | None:
    """``409`` / ``status.HTTP_409_CONFLICT`` → 409;其余不可静态判定。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.Attribute):
        m = re.fullmatch(r"HTTP_(\d{3})_[A-Z_]+", node.attr)
        if m:
            return int(m.group(1))
    return None


def _kwarg(call: ast.Call, name: str) -> ast.expr | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _dict_get(d: ast.Dict, key: str) -> ast.expr | None:
    for k, v in zip(d.keys, d.values):
        if isinstance(k, ast.Constant) and k.value == key:
            return v
    return None


def _file_imports(tree: ast.Module, known: dict[str, ast.Module], rel: str
                  ) -> tuple[dict[str, str], dict[str, str]]:
    """名字导入 → 定义文件;模块别名导入(``from ..services import
    access_token as at``)→ 模块文件。含函数内局部 import(依赖名按
    全文件收集)。相对导入按 node.level 自当前文件包上溯精确定位
    (后缀匹配会把 ``..services`` 误吸成 ``routers/services.py``)。"""
    names: dict[str, str] = {}
    mods: dict[str, str] = {}
    pkg_parts = rel.split("/")[:-1]
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level == 0:
            if not node.module:
                continue                # ``from x import`` 不存在的形态
            base = node.module.split(".")
        else:
            keep = len(pkg_parts) - (node.level - 1)
            if keep < 0:
                continue
            # ``from . import x as y``(module=None)→ 当前包
            base = pkg_parts[:keep] + (node.module.split(".") if node.module else [])
        m = "/".join(base)
        target = f"{m}.py" if f"{m}.py" in known else None
        pkg_dir = m if f"{m}/__init__.py" in known else None
        for a in node.names:
            nm = a.asname or a.name
            if target:
                names[nm] = target
            elif pkg_dir and f"{pkg_dir}/{a.name}.py" in known:
                mods[nm] = f"{pkg_dir}/{a.name}.py"
    return names, mods


class _LocalTable:
    """函数域符号表:参数缺省 + 直赋值(字面量/名链 ≤3 跳)。"""

    def __init__(self, int_codes: dict[str, tuple[str, int]]):
        self._vals: dict[str, ast.expr | None] = {}
        self._int_codes = int_codes

    def assign(self, name: str, value: ast.expr) -> None:
        self._vals[name] = value

    def resolve_name(self, name: str, depth: int = 3) -> tuple[str, str | None] | None:
        """→ (码, _codes 常量名或 None);解析不出返回 None。"""
        if name in self._int_codes:
            code, _ = self._int_codes[name]
            return code, name
        if depth <= 0 or name not in self._vals:
            return None
        v = self._vals[name]
        if v is None:
            return None
        if isinstance(v, ast.Constant) and isinstance(v.value, str):
            return v.value, None
        if isinstance(v, ast.Name):
            return self.resolve_name(v.id, depth - 1)
        return None


def _scope_table(fn: ast.FunctionDef | ast.AsyncFunctionDef,
                 int_codes: dict[str, tuple[str, int]]) -> _LocalTable:
    """参数缺省(如 ``not_found_code="generator_kind_not_found"``)+
    函数体直赋值(``code = "plate_rejected"``)收进符号表。"""
    table = _LocalTable(int_codes)
    a = fn.args
    pos = [*a.posonlyargs, *a.args]
    dpos = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)
    for arg, dft in zip(pos, dpos):
        if dft is not None:
            table.assign(arg.arg, dft)
    for arg, dft in zip(a.kwonlyargs, a.kw_defaults):
        if dft is not None:
            table.assign(arg.arg, dft)
    for node in _walk_scope(fn):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, (ast.Constant, ast.Name)):
            table.assign(node.targets[0].id, node.value)
    return table


def _resolve_value(v: ast.expr, table: _LocalTable, ctx: _FileCtx,
                   dyn) -> tuple[str, str | None] | None:
    """code 表达式 → (码, 常量名);不可静态解析则登记 dynamic 返回 None。"""
    if isinstance(v, ast.Constant) and isinstance(v.value, str):
        return v.value, None
    if isinstance(v, ast.Name):
        got = table.resolve_name(v.id)
        if got:
            return got
        # 同文件模块级常量(``raise TokenAuthError(401, ERR_TOKEN_EXPIRED,..)``)
        same = ctx.module_consts.get(ctx.rel, {}).get(v.id)
        if same is not None:
            return same, None
        dyn(v)
        return None
    if isinstance(v, ast.Attribute) and isinstance(v.value, ast.Name):
        m = ctx.mod_aliases.get(v.value.id)
        if m is not None and v.attr in ctx.module_consts.get(m, {}):
            return ctx.module_consts[m][v.attr], None
    dyn(v)
    return None


def build_error_codes() -> dict:
    trees = _parse_all()
    int_codes = _load_int_codes(trees)
    coded_exc = _discover_coded_exceptions(trees)
    helpers = _discover_helpers(trees)
    module_consts = _module_constants(trees)
    exc_names = set(coded_exc)

    all_sites: list[CodeSite] = []
    dynamic: dict[str, str] = {}

    for rel, tree in trees.items():
        imports, mod_aliases = _file_imports(tree, trees, rel)
        ctx = _FileCtx(rel, int_codes, mod_aliases, module_consts)
        local_helpers: dict[str, _Helper] = {
            f: h for (m, f), h in helpers.items() if m == rel}
        for alias, target in imports.items():
            if (target, alias) in helpers:
                local_helpers[alias] = helpers[(target, alias)]

        def dyn(expr: ast.expr, _rel: str = rel) -> None:
            dynamic[f"{_rel}:{expr.lineno}"] = ast.unparse(expr)

        def record(code: str, node: ast.AST, status: int | None,
                   name: str | None = None,
                   shape: tuple[str, ...] | None = None,
                   _rel: str = rel) -> None:
            all_sites.append(CodeSite(code, _rel, getattr(node, "lineno", 0),
                                      status, name, shape))

        # 作用域:模块体 + 各函数域(helper 自身跳过 —— 其码值来自调用位点)
        scopes: list[tuple[ast.AST, _LocalTable]] = [(
            tree, _LocalTable(int_codes))]
        for fn in ast.walk(tree):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and (rel, fn.name) not in helpers:
                scopes.append((fn, _scope_table(fn, int_codes)))

        for scope, table in scopes:
            for node in _walk_scope(scope):
                if not isinstance(node, ast.Call):
                    continue
                fname = node.func.id if isinstance(node.func, ast.Name) else (
                    node.func.attr if isinstance(node.func, ast.Attribute) else None)
                if fname is None:
                    continue
                if fname == "HTTPException":
                    _on_http_exception(node, table, ctx, dyn, record)
                elif fname in exc_names:
                    exc = coded_exc[fname]
                    cv = exc.arg(node, "code")
                    if cv is not None:
                        resolved = _resolve_value(cv, table, ctx, dyn)
                        if resolved:
                            sv = exc.arg(node, "status") or exc.arg(node, "status_code")
                            record(resolved[0], node, _status_literal(sv), resolved[1])
                elif fname in local_helpers:
                    h = local_helpers[fname]
                    cv = h.arg(node, h.code_param)
                    if cv is not None:
                        status = None
                        if h.status_param:
                            status = _status_literal(h.arg(node, h.status_param)) \
                                or h.status_default
                        resolved = _resolve_value(cv, table, ctx, dyn)
                        if resolved:
                            record(resolved[0], node, status, resolved[1])

    # 汇总:码 → statuses / sites / shapes / 常量名
    codes: dict[str, dict] = {}
    for s in sorted(all_sites, key=lambda x: (x.code, x.file, x.line)):
        entry = codes.setdefault(s.code, {
            "statuses": set(), "sites": [], "shapes": set()})
        entry["statuses"].add(s.status)
        entry["sites"].append(f"{s.file}:{s.line}")
        if s.shape:
            entry["shapes"].add(s.shape)
        if s.name:
            entry["name"] = s.name
    out_codes: dict[str, dict] = {}
    for code, e in sorted(codes.items()):
        item: dict = {
            "statuses": sorted(x for x in e["statuses"] if x is not None),
            "sites": e["sites"]}
        if e["shapes"]:
            item["shapes"] = sorted(list(t) for t in e["shapes"])
        if "name" in e:
            item["name"] = e["name"]
        out_codes[code] = item
    return {
        "meta": {
            "scanned_files": len(trees),
            "coded_exception_classes": sorted(
                f"{e.home}:{e.line} {n}" for n, e in coded_exc.items()),
            "helpers": sorted(f"{m}:{fn}" for (m, fn) in helpers),
            "int_codes_module": f"app/routers/{CODES_MODULE_STEM}.py",
            "note": "动态(非字面量)code 位点在 dynamic 面:取值由对应异常"
                    "/helper 调用位点枚举,位点增删即契约变化;无码纯 "
                    "message detail 不入面",
        },
        "codes": out_codes,
        "dynamic": dict(sorted(dynamic.items())),
    }


def _on_http_exception(call: ast.Call, table: _LocalTable, ctx: _FileCtx,
                       dyn, record) -> None:
    """HTTPException 调用:dict detail 取 code 键;code_detail 展开整型码。

    无码(纯 message / dict 无 code 键)不入面;detail 为变量/造 dict 的
    helper 调用时登记 dynamic。
    """
    status = _status_literal(_kwarg(call, "status_code")
                             or (call.args[0] if call.args else None))
    detail = _kwarg(call, "detail") \
        or (call.args[1] if len(call.args) >= 2 else None)
    if isinstance(detail, ast.Dict):
        cv = _dict_get(detail, "code")
        if cv is None:
            return                          # 无码 detail:纯 message 面
        shape = tuple(sorted(k.value for k in detail.keys
                             if isinstance(k, ast.Constant)))
        resolved = _resolve_value(cv, table, ctx, dyn)
        if resolved:
            record(resolved[0], call, status, resolved[1], shape)
    elif isinstance(detail, ast.Call) and isinstance(detail.func, ast.Name) \
            and detail.func.id == "code_detail":
        arg = detail.args[0] if detail.args else _kwarg(detail, "code")
        if arg is not None:
            resolved = _resolve_value(arg, table, ctx, dyn)
            if resolved:
                record(resolved[0], call, status, resolved[1], ("code", "msg"))
    elif isinstance(detail, ast.Call) and isinstance(detail.func, ast.Name) \
            and detail.func.id == "str":
        return                              # 字符串化 message:无码面
    elif detail is not None and not isinstance(detail, (ast.Constant, ast.JoinedStr)):
        dyn(detail)                         # 变量 dict / 造 dict helper:动态


def _dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _drift_summary(committed: str, fresh: str, label: str) -> list[str]:
    diff = list(difflib.unified_diff(
        committed.splitlines(), fresh.splitlines(),
        fromfile=f"入库 {label}", tofile=f"重生 {label}", lineterm="", n=1))
    return diff[:120]


def cmd_gen() -> int:
    CONTRACT.mkdir(exist_ok=True)
    OPENAPI_JSON.write_text(build_openapi_text(), encoding="utf-8")
    ERROR_CODES_JSON.write_text(_dump(build_error_codes()), encoding="utf-8")
    print(f"gen: {OPENAPI_JSON.relative_to(REPO)} / "
          f"{ERROR_CODES_JSON.relative_to(REPO)} 已重生")
    return 0


def cmd_check() -> int:
    drift = False
    for path, fresh in (
        (OPENAPI_JSON, build_openapi_text()),
        (ERROR_CODES_JSON, _dump(build_error_codes())),
    ):
        rel = path.relative_to(REPO)
        if not path.exists():
            print(f"漂移[{rel}]: 快照缺失 — 先 python scripts/gen_api_contract.py gen")
            drift = True
            continue
        committed = path.read_text(encoding="utf-8")
        if committed != fresh:
            drift = True
            print(f"漂移[{rel}] — 契约变更未重生快照:")
            for line in _drift_summary(committed, fresh, path.name):
                print(line)
    if drift:
        print("\n处置:契约改动须随提交重生 — "
              "python scripts/gen_api_contract.py gen(产物入库)")
        return 1
    print("check: 两份契约快照与实现一致")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("gen", help="重生快照入库")
    sub.add_parser("check", help="漂移比对(重生 vs 入库,漂移非零退出)")
    args = ap.parse_args(argv)
    return cmd_gen() if args.cmd == "gen" else cmd_check()


if __name__ == "__main__":
    raise SystemExit(main())
