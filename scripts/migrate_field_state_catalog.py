"""P8 迁移脚本:端点文件 channel→state 目录化(2026-09-05 spec §6 M1-3)。

机械变换(AST 定位 + 位置锚定文本手术,保留注释与排版):
- DeclarationEntry:channel='carry' → state='carry';channel='binding'/
  'view_only' → 删除 kwarg(form 是默认值;响应面无视 state);
- 缺失 type 回填:enclosing spec 的 schema_ 节点吸收 → example/default
  字面量推断 → ui_kind 映射 → 'string' 兜底(兜底命中逐一报告,须复核);
- RequestSpec/ResponseSpec:schema_={} 删除;schema_=Model.model_json_schema()
  且无 declarations → 整体改写为 declare(Model, status, description);
  schema_=字面量 dict(Type C 差集字段)→ 合成 form 条目追加进 declarations;
- 请求侧深实例条目(path 带 [0] 的 binding)与 declare(bindings/carry)
  不做机械变换 —— 报告人工处理(9 条 / 1 文件)。

变换后逐文件 import 验证(构造校验全量跑),报告前后条目计数。
用法(仓库根 Gimbal/ 下):
    PYTHONPATH=src/gimbal-plate python ../scripts/migrate_field_state_catalog.py [--check]
"""
from __future__ import annotations

import ast
import importlib
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
ENDPOINT_DIR = REPO / "src" / "gimbal-plate" / "gimbal_plate" / "systems" / "fin" / "endpoint"

# ── 位置工具 ─────────────────────────────────────────────

class Src:
    """源文本 + (lineno, col) → 绝对偏移换算。

    ast 的 col_offset 是 **UTF-8 字节列**,str 索引是码点列 —— 行内
    含 CJK(如 '疑似 int(字符串形态)')时字节列 > 字符列,直接相加会
    越过真实终点落进后续内容。此处逐行做字节列 → 字符列换算;
    ASCII 行走快速路径。
    """

    def __init__(self, text: str) -> None:
        self.text = text
        self.line_starts = [0]
        for i, ch in enumerate(text):
            if ch == "\n":
                self.line_starts.append(i + 1)

    def _pos(self, lineno: int, col: int) -> int:
        ls = self.line_starts[lineno - 1]
        le = (self.line_starts[lineno] - 1
              if lineno < len(self.line_starts) else len(self.text))
        line = self.text[ls:le]
        if col == 0 or line.isascii():
            return ls + col
        return ls + len(line.encode("utf-8")[:col].decode("utf-8"))

    def off(self, node: ast.AST) -> int:
        return self._pos(node.lineno, node.col_offset)  # type: ignore[attr-defined]

    def end(self, node: ast.AST) -> int:
        return self._pos(node.end_lineno, node.end_col_offset)  # type: ignore[attr-defined]

    def span(self, node: ast.AST) -> tuple[int, int]:
        return self.off(node), self.end(node)


def _swallow_comma(src: Src, start: int, end: int) -> tuple[int, int]:
    """扩展 kwarg 跨度吞掉相邻的一个逗号(+空格)。"""
    t = src.text
    if t[end:end + 2] == ", ":
        return start, end + 2
    if end < len(t) and t[end] == ",":
        return start, end + 1
    if t[start - 2:start] == ", ":
        return start - 2, end
    if start > 0 and t[start - 1] == ",":
        return start - 1, end
    return start, end


# ── type 推断 ────────────────────────────────────────────

def _schema_type(schema: dict[str, Any], path: str) -> str | None:
    """按 JSON path 在 schema 里找节点 type(INDEX→items / FIELD→properties)。"""
    segs: list[Any] = []
    for m in re.finditer(r"([^[\].]+)|\[(\d+)\]", path.lstrip("$.")):
        segs.append(m.group(1) if m.group(1) is not None else int(m.group(2)))
    node: Any = schema
    for seg in segs:
        if not isinstance(node, dict):
            return None
        node = node.get("items") if isinstance(seg, int) else (node.get("properties") or {}).get(seg)
    if not isinstance(node, dict):
        return None
    t = node.get("type")
    if t is not None:
        return t
    for comb in ("anyOf", "oneOf"):  # Optional 剥 null
        members = node.get(comb)
        if isinstance(members, list):
            types = {m.get("type") for m in members
                     if isinstance(m, dict) and m.get("type") != "null"}
            if len(types) == 1:
                return types.pop()
    return None


def _literal_type(node: ast.expr) -> str | None:
    """example/default 字面量 → 原语 type(bool 先于 int!)。"""
    try:
        v = ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return None
    return {str: "string", bool: "boolean", int: "integer", float: "number",
            dict: "object", list: "array"}.get(type(v))


_UI_KIND_MAP = {"number": "number", "boolean": "boolean"}


def _infer_type(
    entry_kw: dict[str, ast.expr], schema: dict[str, Any] | None,
) -> tuple[str | None, str]:
    """返回 (type, 来源)。来源 ∈ schema/literal/ui_kind/None。"""
    path_node = entry_kw.get("path")
    if schema and isinstance(path_node, ast.Constant) and isinstance(path_node.value, str):
        t = _schema_type(schema, path_node.value)
        if t:
            return t, "schema"
    for key in ("example", "default"):
        node = entry_kw.get(key)
        if node is not None:
            t = _literal_type(node)
            if t:
                return t, f"literal({key})"
    ui_node = entry_kw.get("ui_kind")
    if isinstance(ui_node, ast.Constant) and ui_node.value in _UI_KIND_MAP:
        return _UI_KIND_MAP[ui_node.value], "ui_kind"
    return None, ""


# ── schema_ 求值 ─────────────────────────────────────────

def _eval_schema(
    node: ast.expr, imports: dict[str, tuple[str, str]],
) -> dict[str, Any] | None:
    """schema_ 值求值:{} / 字面量 dict / <Model>.model_json_schema()。"""
    if isinstance(node, ast.Dict):
        try:
            return ast.literal_eval(node)
        except (ValueError, SyntaxError):
            return None
    if (isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "model_json_schema"
            and isinstance(node.func.value, ast.Name)):
        model_name = node.func.value.id
        hit = imports.get(model_name)
        if hit is None:
            return None
        module = importlib.import_module(hit[0])
        return getattr(module, model_name).model_json_schema()
    return None


def _collect_imports(tree: ast.Module) -> dict[str, tuple[str, str]]:
    """模块级 import 映射:name → (module, asname)。"""
    out: dict[str, tuple[str, str]] = {}
    for n in tree.body:
        if isinstance(n, ast.ImportFrom) and n.module:
            for a in n.names:
                out[a.asname or a.name] = (n.module, a.asname or a.name)
        elif isinstance(n, ast.Import):
            for a in n.names:
                out[(a.asname or a.name).split(".")[0]] = (a.asname or a.name, a.asname or a.name)
    return out


# ── 主变换 ───────────────────────────────────────────────

class Ctx:
    """遍历上下文:当前 enclosing spec 的 schema 求值结果与种类。"""

    def __init__(self) -> None:
        self.schema: dict[str, Any] | None = None
        self.spec_kind: str = ""


def migrate_file(path: Path, check_only: bool) -> dict[str, Any]:
    report: dict[str, Any] = {"file": path.name, "manual": [], "fallback": [],
                              "before": 0, "after": 0, "carry": 0}
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    src = Src(text)
    imports = _collect_imports(tree)
    edits: list[tuple[int, int, str]] = []

    def visit(node: ast.AST, ctx: Ctx) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Call):
                func = child.func
                fname = func.id if isinstance(func, ast.Name) else ""
                if fname in ("RequestSpec", "ResponseSpec"):
                    sub = Ctx()
                    sub.spec_kind = fname
                    kw = {k.arg: k.value for k in child.keywords}
                    schema_key = "schema_" if "schema_" in kw else (
                        "schema" if "schema" in kw else None)
                    if schema_key:
                        sub.schema = _eval_schema(kw[schema_key], imports)
                        _transform_spec(child, kw, sub, report, edits, src,
                                        schema_key)
                    visit(child, sub)
                    continue
                if fname == "DeclarationEntry":
                    report["before"] += 1
                    _transform_entry(child, ctx, report, edits, src)
                    continue
            visit(child, ctx)

    # declare( 旧签名(bindings/carry)→ 报告人工(settlement 唯一)
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "declare"):
            kws = {k.arg for k in n.keywords}
            if kws & {"bindings", "carry", "view_only"}:
                report["manual"].append(
                    f"{path.name}:{n.lineno}: declare({sorted(kws & {'bindings', 'carry', 'view_only'})}) 旧签名 → 人工改写为 states")

    visit(tree, Ctx())

    if check_only:
        return report

    # 底向上应用编辑;写回前语法校验(失败即拒绝落盘,防半损文件)
    for start, end, repl in sorted(edits, key=lambda e: -e[0]):
        text = text[:start] + repl + text[end:]
    try:
        ast.parse(text)
    except SyntaxError as exc:
        report["manual"].append(
            f"编辑后语法校验失败(line {exc.lineno}: {exc.msg})— 拒绝落盘,需人工")
        return report

    path.write_text(text, encoding="utf-8")
    return report


def _transform_entry(
    call: ast.Call, ctx: Ctx, report: dict, edits: list, src: Src,
) -> None:
    kw = {k.arg: (k, k.value) for k in call.keywords}
    chan = kw.get("channel")
    if chan is not None:
        k_node, v_node = chan
        if isinstance(v_node, ast.Constant) and v_node.value in ("binding", "carry", "view_only"):
            s, e = src.span(k_node)
            if v_node.value == "carry":
                report["carry"] += 1
                edits.append((s, e, "state='carry'"))
            else:
                if (v_node.value == "binding" and ctx.spec_kind == "RequestSpec"
                        and isinstance(kw.get("path", (None, None))[1], ast.Constant)
                        and "[0]" in kw["path"][1].value):
                    report["manual"].append(
                        f"深实例 binding 条目(path={kw['path'][1].value!r})→ 人工缩并为容器模板 + children")
                s, e = _swallow_comma(src, s, e)
                edits.append((s, e, ""))
        else:
            report["manual"].append(f"channel 非字面量(line {k_node.lineno})→ 人工")
    # type 回填
    if "type" not in kw:
        plain = {k: v for k, (_, v) in kw.items()}
        t, _origin = _infer_type(plain, ctx.schema)  # type: ignore[arg-type]
        if t is None:
            t = "string"
            name = kw.get("name", (None, ast.Constant(value="?")))[1]
            report["fallback"].append(
                f"line {call.lineno} {getattr(name, 'value', '?')}: type 兜底 'string'(schema/字面量/ui_kind 均无)")
        anchor = kw.get("path") or kw.get("name")
        if anchor is not None:
            insert_at = src.end(anchor[0])
            edits.append((insert_at, insert_at, f", type='{t}'"))


def _transform_spec(
    call: ast.Call, kw: dict[str, ast.expr], ctx: Ctx,
    report: dict, edits: list, src: Src, schema_key: str,
) -> None:
    """schema_/schema kwarg 处置:删除 / 整体 declare 改写。

    字面量 dict(Type C 字段)一律直删不合成 —— 2026-09-05 定稿:
    目录即宇宙,schema 残余 body 键归前端「其他字段」区兜底。
    """
    schema_node = kw[schema_key]
    schema = ctx.schema
    decls = kw.get("declarations")
    has_entries = isinstance(decls, ast.List) and bool(decls.elts)
    kw_node = next(k for k in call.keywords if k.arg == schema_key)

    if schema == {}:
        s, e = _swallow_comma(src, *src.span(kw_node))
        edits.append((s, e, ""))
        return

    if (isinstance(schema_node, ast.Call)
            and isinstance(schema_node.func, ast.Attribute)
            and schema_node.func.attr == "model_json_schema"):
        if has_entries:
            report["manual"].append(
                f"line {call.lineno}: {schema_key}=模型 且已带 declarations → 人工核对 type 吸收")
            return
        # 无 declarations → 整体改写为 declare(Model[, status, description])
        # (status/description 仅 ResponseSpec 签名有;RequestSpec 只传模型)
        model_name = schema_node.func.value.id  # type: ignore[attr-defined]
        is_response = ctx.spec_kind == "ResponseSpec"
        status = (ast.literal_eval(kw["status"])
                  if is_response and "status" in kw else 200)
        desc = (ast.literal_eval(kw["description"])
                if is_response and "description" in kw else "")
        repl = f"declare({model_name})"
        if is_response:
            repl = f"declare({model_name}, status={status}"
            if desc:
                repl += f", description={desc!r}"
            repl += ")"
        func_name = "ResponseSpec" if is_response else "RequestSpec"
        repl = f"{func_name}.{repl}"
        s, e = src.span(call)
        edits.append((s, e, repl))
        return

    # 字面量 dict(含 Type C 差集字段):直删 —— 不合成条目(定稿裁决)
    s, e = _swallow_comma(src, *src.span(kw_node))
    edits.append((s, e, ""))


# ── import 验证 ──────────────────────────────────────────

def import_verify(path: Path, report: dict) -> None:
    from gimbal_plate.schema.endpoint.endpoint import EndpointSpec
    mod_name = f"_mig_{path.stem}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    count = 0
    for attr in vars(mod).values():
        if isinstance(attr, EndpointSpec):
            count += 1
            req = attr.request
            if req is not None:
                report["after"] += len(req.declarations)
            for rsp in attr.responses.values():
                report["after"] += len(rsp.declarations)
    if count == 0:
        report["manual"].append("未找到 EndpointSpec 实例(import 验证失败?)")


def main() -> None:
    check_only = "--check" in sys.argv
    # --dir <path>:迁移其他目录(如 tests/plate 的旧 channel 夹具);
    # 非 endpoint 目录跳过 import_verify(测试文件依赖 pytest/conftest,
    # 验证归 pytest 收集/运行)
    target_dir = ENDPOINT_DIR
    if "--dir" in sys.argv:
        target_dir = (REPO / Path(sys.argv[sys.argv.index("--dir") + 1])).resolve()
    files = sorted(p for p in target_dir.glob("*.py") if p.name != "__init__.py")
    print(f"files under {target_dir}: {len(files)}  mode: {'CHECK' if check_only else 'MIGRATE'}\n")
    total_manual = 0
    for p in files:
        report = migrate_file(p, check_only)
        if not check_only and target_dir == ENDPOINT_DIR:
            try:
                import_verify(p, report)
            except Exception as exc:  # noqa: BLE001 — 报告而非中断
                report["manual"].append(f"import 验证失败: {exc!r}")
        flag = " **" if report["manual"] else ""
        print(f"{report['file']}: entries {report['before']}→{report['after']}"
              f"  carry={report['carry']}{flag}")
        for m in report["manual"]:
            print(f"    [人工] {m}")
            total_manual += 1
        for f in report["fallback"]:
            print(f"    [兜底] {f}")
    print(f"\nmanual items: {total_manual}")
    if total_manual:
        print("存在需人工处理项 — 完成后重跑至 0。")


if __name__ == "__main__":
    main()
