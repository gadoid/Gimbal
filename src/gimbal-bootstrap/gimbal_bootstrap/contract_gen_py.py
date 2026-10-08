"""契约的终态形态：plate 侧的结构化 py 定义（fin 形制）。

`contract_gen` 产出的是**中间形态** —— 一份 358KB 的 endpoints.json。它有结构，
但对人是不可用的：改一个字段要 diff 几万行，123 个端点挤在一个文件里没法
导航，也没法像 fin 那样在单个端点文件里写实测核订的说明。

本模块把中间形态翻成**终态**：每端点一个 .py，直接构造 EndpointSpec 实例
常量，聚合层汇总，与 fin/endpoint/ 同构。生成逻辑留在 gimbal-bootstrap ——
plate 不认识生成器，只看得到一堆正常的 py 定义文件。

三段的分工：
- `contract_gen`                    OpenAPI → 中间形态（不关心产物长什么样）
- `contract_gen_py`（本模块）        中间形态 → py 定义
- `plate/systems/platform/endpoint/` 人读得改的定义；plate 只管导入

**一处对 plate `_ui_kind_of` 的有意偏离**：容器（object/array）的 ui_kind
取 `json`，不是 plate 那份的 `text`。plate 那是 `declare()` 的**基线**推断，
它看不到节点有没有 children —— 把一棵子树标成 text 显然不对，fin 手写定义
也是标 json。
"""

from __future__ import annotations

import json
import keyword
import re
from pathlib import Path
from typing import Any

from gimbal_bootstrap.contract_gen import (
    CONTRACT_VERSION,
    OWNER,
    SERVICE,
    SYSTEM,
    build_specs,
)

# id 的分节（platform.<domain>.<action>）必须各自像个 Python 标识符，且**不能
# 是关键字** —— 分节直接进 dotted import 路径，`import` / `class` / `lambda` 这
# 类域名会让聚合层写出的 `from ...endpoint.import.x import ...` 编译不过。
_SEGMENT_RE = re.compile(r"^[a-z][a-z0-9_]*$")

# 六原语 → 表单控件。容器走 json（见模块 docstring 里的偏离说明）。
_UI_KINDS: dict[str, str] = {
    "string": "text",
    "integer": "number",
    "number": "number",
    "boolean": "boolean",
    "object": "json",
    "array": "json",
}

_IMPORT_BLOCK = '''\
from typing import Final

from gimbal_plate.schema.endpoint import (
    ApiSpec,
    DeclarationEntry,
    EndpointMetadata,
    EndpointSpec,
    RequestSpec,
    ResponseSpec,
)
from gimbal_plate.systems.platform.system_info import (
    PLATFORM_DEFAULT_OWNER,
    PLATFORM_DEFAULT_TAGS,
    PLATFORM_DEFAULT_VERSION,
    PLATFORM_SERVICE,
    PLATFORM_SYSTEM,
)
'''

# 端点文件里恒用到的常量导入（PLATFORM_DEFAULT_MODULE 不在其中：metadata.module
# 是路由域（auth/executions/...），逐端点不同，用字面量而不是共用常量）。


def constant_name(endpoint_id: str) -> str:
    """id → 常量名。`platform.auth.post_register` → `AUTH_POST_REGISTER`。

    去掉 system 前缀：端点文件里 system 已经由 `PLATFORM_SYSTEM` 表达了，
    常量名里再带一遍是噪音。fin 同样如此（`fin.order.order_page` →
    `ORDER_ORDER_PAGE`）。
    """
    parts = endpoint_id.split(".")
    if len(parts) < 3:
        raise ValueError(
            f"id={endpoint_id!r} 至少要三节 <system>.<domain>.<action>，"
            f"否则定不出常量名与模块路径"
        )
    rest = parts[1:]
    for seg in rest:
        if not _SEGMENT_RE.match(seg) or keyword.iskeyword(seg):
            raise ValueError(
                f"id={endpoint_id!r} 的分节 {seg!r} 不能变成 Python 标识符"
                f"（需匹配 {_SEGMENT_RE.pattern} 且不是关键字）"
            )
    return "_".join(rest).upper()


def module_path(endpoint_id: str) -> Path:
    """id → 端点文件相对路径。`platform.auth.post_register` → `auth/post_register.py`。

    按域分目录而不是 fin 的单层平铺：fin 18 个端点，platform 123 个 ——
    单层没法导航。
    """
    constant_name(endpoint_id)  # 顺带做 id 合法性校验
    parts = endpoint_id.split(".")
    return Path(parts[1]) / f"{'_'.join(parts[2:])}.py"


def ui_kind_of(json_type: str) -> str:
    """JSON 原语 → plate 的 ui_kind。认不出的类型落 `unknown`（DeclarationEntry
    的合法值，也是它的默认值）。"""
    return _UI_KINDS.get(json_type, "unknown")


def _q(value: str) -> str:
    """Python 字符串字面量。双引号 + 保留中文（json.dumps 的 ensure_ascii=False）。"""
    return json.dumps(value, ensure_ascii=False)


def _render_decls(decls: list[dict[str, Any]], pad: str) -> list[str]:
    """声明树 → 源码行。pad 是本块起点的缩进。"""
    if not decls:
        return [f"{pad}[]"]
    out = [f"{pad}["]
    for d in decls:
        out += _render_entry(d, pad + "    ")
    out.append(f"{pad}]")
    return out


def _render_entry(d: dict[str, Any], pad: str) -> list[str]:
    """一个 DeclarationEntry → 源码行。args 折行对齐到开括号后，children 自成一块。

    默认值不写（required / assertable / description 只在非默认时出现）——
    356 个字段里真带 description 的不到一半，全量铺开等于噪音。
    """
    args = [
        f"name={_q(d['name'])}",
        f"path={_q(d['path'])}",
        f"type={_q(d['type'])}",
        f"ui_kind={_q(ui_kind_of(d['type']))}",
    ]
    if d.get("required"):
        args.append("required=True")
    if d.get("description"):
        args.append(f"description={_q(d['description'])}")
    if d.get("assertable"):
        args.append("assertable=True")

    cont = pad + " " * len("DeclarationEntry(")
    lines: list[str] = []
    cur = f"{pad}DeclarationEntry("
    for i, arg in enumerate(args):
        tail = "," if i < len(args) - 1 else ""
        sep = "" if cur.endswith("(") else " "
        cand = cur + sep + arg + tail
        if len(cand) > 92 and not cur.endswith("("):
            lines.append(cur)
            cur = cont + sep + arg + tail
        else:
            cur = cand
    kids = d.get("children") or []
    if not kids:
        lines.append(cur + "),")
        return lines
    kid_lines = _render_decls(kids, cont)
    # children 的方括号跟在 `children=` 后面，不单独起一行 —— 单独起行会让
    # 每个容器前面多出一道对齐不齐的缝。
    head = cur + ", children="
    if len(head) > 92:
        lines.append(cur + ",")
        lines.append(cont + "children=" + kid_lines[0][len(cont):])
    else:
        lines.append(head + kid_lines[0][len(cont):])
    lines += kid_lines[1:]
    lines.append(f"{pad}),")
    return lines


def _block(keyword: str, decls: list[dict[str, Any]], pad: str) -> list[str]:
    """`declarations=[...]` —— 整块源码行，首行带关键字名。"""
    lines = _render_decls(decls, pad)
    lines[0] = f"{pad}{keyword}{lines[0][len(pad):]}"
    return lines


def _field_drift(want: list[dict[str, Any]], got: Any) -> list[str]:
    """中间形态的声明树 vs 已安装的声明条目 → 人类可读的漂移清单。

    **只拦退化，不拦人工增益。** 端点文件是给人改的：把说明写得更清楚、把一个
    可选字段标成必填、给容器另配 ui_kind，都是允许的；反过来，字段消失、类型
    走样、必填标记被抹掉、说明被清空、控件形态退回 unknown，五种都会伤到用例
    作者（详见 tests/test_contract_definitions.py 里的对应用例）。

    只比 path 集合是不够的：上面后四种退化，path 一个都不会少，门全是绿的。
    """
    from gimbal_plate.schema.endpoint.io_spec import (  # noqa: PLC0415
        iter_declarations,
    )

    wanted: dict[str, dict[str, Any]] = {}
    stack = list(want)
    while stack:
        d = stack.pop()
        wanted[d["path"]] = d
        stack.extend(d.get("children") or [])
    installed = {d.path: d for d in iter_declarations(got)}

    out: list[str] = []
    for path, w in sorted(wanted.items()):
        g = installed.get(path)
        if g is None:
            out.append(f"{path} 消失了")
            continue
        if g.type != w["type"]:
            out.append(f"{path} 类型 {w['type']} → {g.type}")
        if w.get("assertable") and not g.assertable:
            out.append(f"{path} 不可断言了")
        if w.get("required") and not g.required:
            out.append(f"{path} 的必填标记没了")
        if (w.get("description") or "").strip() and not (g.description or "").strip():
            out.append(f"{path} 的说明被清空了")
        if ui_kind_of(w["type"]) != "unknown" and g.ui_kind == "unknown":
            out.append(f"{path} 的控件形态退化成 unknown")
    return out


def _docstring(spec: dict[str, Any]) -> str:
    # 文件头：替代「翻源码才知道这个端点是干嘛的」。
    #
    # （用注释而非 docstring：本函数的 docstring 里写不出三引号本身。）
    api = spec["api"]
    paras = [
        f"{spec['id']} —— {spec['name']}",
        f"`{api['method']} {api['path']}`",
    ]
    desc = (spec.get("description") or "").strip()
    if desc and desc != spec["name"]:
        paras.append(desc)
    paras.append(
        "字段面由 gimbal-bootstrap 的 contract_gen 从平台 OpenAPI 生成。这个文件"
        "\n**可以手改** —— 实测核订的语义（description / ui_kind / required）写在"
        "\n这里，重新生成默认不覆盖；要覆盖用 --force。"
    )
    # 两处转义，缺一不可：
    # - `"""` → `'''`：描述里带三引号会把 docstring 提前闭合；
    # - `\` → `\\`：这是**非 raw** 三引号串，后端 docstring 里写正则（`\d+`）
    #   很常见，原样透传会被当成转义序列（3.12+ 发 SyntaxWarning），而结尾
    #   一个 `\` 还会把后面整行续接掉。
    body = "\n\n".join(
        p.replace("\\", "\\\\").replace('"""', "'''") for p in paras
    )
    return f'"""{body}\n"""\n'


def emit_module(spec: dict[str, Any]) -> str:
    """中间形态的一条端点 → 一个 fin 形制的端点文件源码。"""
    # 端点文件里的身份字段是**写死的 plate 常量名**（`system=PLATFORM_SYSTEM`、
    # `version=PLATFORM_DEFAULT_VERSION`）。中间形态一旦跟这些常量对不上，
    # 生成器就是在照着常量说谎 —— 而结构对账只比 path，不会发现。所以在这里
    # 挡：说谎要在生成期暴露，不是等到 plate 加载后无从追查。
    meta = spec.get("metadata") or {}
    for key, got, want in (
        ("system", spec["system"], SYSTEM),
        ("service", spec["service"], SERVICE),
        ("version", spec.get("version"), CONTRACT_VERSION),
        ("owner", meta.get("owner"), OWNER),
        ("tags", meta.get("tags"), [SYSTEM]),
    ):
        if got != want:
            raise ValueError(
                f"{spec['id']}: 中间形态的 {key}={got!r} 与端点文件写死的常量 "
                f"{want!r} 不一致 —— 要么改生成器常量，要么改 plate 的 system_info"
            )
    api = spec["api"]
    req = spec["request"]
    responses = spec["responses"]
    out: list[str] = [_docstring(spec), "\n", _IMPORT_BLOCK, "\n"]

    # 合成 200 与真实状态码共用同一份声明（build_specs 的占位约定）—— 提成一个
    # 模块级常量，两处引用，跟 fin 的 _RESPONSE_DECLS 一样。
    # 中间形态的 responses 键是字符串（JSON 对象），排序时按 int 排。
    first = responses[min(responses, key=int)]
    shared = len(responses) > 1 and all(
        r["declarations"] == first["declarations"] for r in responses.values()
    )
    if shared:
        block = _render_decls(first["declarations"], "")
        out.append(
            "_RESPONSE_DECLS: Final[list[DeclarationEntry]] = " + block[0] + "\n"
        )
        out += [ln + "\n" for ln in block[1:]]
        out.append("\n")

    out.append(f"{constant_name(spec['id'])}: Final[EndpointSpec] = EndpointSpec(\n")
    out.append(f"    id={_q(spec['id'])},\n")
    out.append("    system=PLATFORM_SYSTEM,\n")
    out.append("    service=PLATFORM_SERVICE,\n")
    out.append(f"    name={_q(spec['name'])},\n")
    if spec.get("description"):
        out.append(f"    description={_q(spec['description'])},\n")
    out.append("    api=ApiSpec(\n")
    out.append("        service=PLATFORM_SERVICE,\n")
    out.append(f"        method={_q(api['method'])},\n")
    out.append(f"        path={_q(api['path'])},\n")
    if api.get("auth", "none") != "none":
        out.append(f"        auth={_q(api['auth'])},\n")
    out.append(f"        timeout_seconds={api.get('timeout_seconds', 30.0)!r},\n")
    out.append("    ),\n")

    out.append("    request=RequestSpec(\n")
    out.append(f"        body_type={_q(req.get('body_type', 'none'))},\n")
    out += [ln + "\n" for ln in _block("declarations=", req.get("declarations") or [], " " * 8)]
    out.append("    ),\n")

    out.append("    responses={\n")
    for status in sorted(responses, key=int):
        r = responses[status]
        out.append(f"        {int(status)}: ResponseSpec(\n")
        out.append(f"            status={int(status)},\n")
        if r.get("description"):
            out.append(f"            description={_q(r['description'])},\n")
        if shared:
            out.append("            declarations=_RESPONSE_DECLS,\n")
        else:
            out += [ln + "\n" for ln in _block("declarations=", r["declarations"], " " * 12)]
        out.append("        ),\n")
    out.append("    },\n")

    out.append("    version=PLATFORM_DEFAULT_VERSION,\n")
    out.append("    metadata=EndpointMetadata(\n")
    out.append(f"        module={_q(meta.get('module', ''))},\n")
    out.append("        owner=PLATFORM_DEFAULT_OWNER,\n")
    out.append("        tags=list(PLATFORM_DEFAULT_TAGS),\n")
    if meta.get("business_notes"):
        out.append(f"        business_notes={_q(meta['business_notes'])},\n")
    out.append("    ),\n")
    out.append(")\n")
    return "".join(out)


def _emit_domain_init(domain: str) -> str:
    return (
        f'"""platform 契约的 {domain} 域。\n'
        "\n"
        "按域分目录是 platform 对 fin 形制的偏离:fin 18 个端点单层平铺,platform\n"
        "123 个 —— 单层没法导航。代价是这个 __init__.py 不能少,少了装包后\n"
        "`...platform.endpoint.<域>.<动作>` 这个 import path 就断了(开发时 namespace\n"
        'package 还能凑合)。"""\n'
    )


def _emit_aggregator(specs: list[dict[str, Any]]) -> str:
    """聚合层：导入全部端点常量，汇总成 ALL_ENDPOINTS。

    **这个文件每次生成都重写**，端点文件不重写 —— 它必须跟磁盘上的端点文件
    对得上，人删了端点文件就 ImportError（显式、响亮），优于静默少注册。
    """
    out = [
        '"""platform 全部 endpoint 契约的聚合入口。\n'
        "\n"
        "每端点一个文件 <域>/<动作>.py,只导出一个 EndpointSpec 实例常量。\n"
        "本模块聚合所有实例供 PlateRegistry 一键注册。\n"
        "\n"
        "**本文件由 contract_gen_py 生成,重新生成即覆盖** —— 端点文件可以手改,\n"
        "这个不行。\n"
        '"""\n'
        "from typing import Final\n"
        "\n"
        "from gimbal_plate.schema.endpoint import EndpointSpec\n",
    ]
    for spec in specs:
        mod = ".".join(
            ["gimbal_plate", "systems", SYSTEM, "endpoint", *module_path(spec["id"]).with_suffix("").parts]
        )
        out.append(f"from {mod} import (\n    {constant_name(spec['id'])},\n)\n")
    out.append("\nALL_ENDPOINTS: Final[list[EndpointSpec]] = [\n")
    out += [f"    {constant_name(spec['id'])},\n" for spec in specs]
    out.append("]\n\n__all__ = [\n")
    out += [f'    "{constant_name(spec["id"])}",\n' for spec in specs]
    out.append('    "ALL_ENDPOINTS",\n]\n')
    return "".join(out)


def emit_package(
    specs: list[dict[str, Any]], root: Path, *, force: bool = False
) -> list[Path]:
    """把一组中间形态端点落成一套 py 定义包，返回写盘的文件清单。

    端点文件默认**不覆盖已存在的**（`force=False`）：这些文件是给人改的，
    实测核订的语义注释没有一份在 OpenAPI 里，重新生成抹掉就没了。聚合层
    与各域的 `__init__.py` 例外 —— 纯机械，无人工内容，每次都重写。
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    ordered = sorted(specs, key=lambda s: s["id"])
    written: list[Path] = []

    # 全部生成 + 编译通过，才开始落盘。生成中途失败就抛在写之前，上一份能用的
    # 聚合层原封不动 —— 半新半旧的聚合层比这一轮什么都不生效更糟（新增端点成了
    # 没人注册的孤儿，已删端点则 ImportError）。
    sources = [(spec, emit_module(spec)) for spec in ordered]
    agg_src = _emit_aggregator(ordered)
    for spec, src in sources:
        compile(src, f"<{spec['id']}>", "exec")
    compile(agg_src, "<aggregator>", "exec")

    # 域名的收集**不能**放在「文件已存在就跳过」之后：正常重跑时每个端点文件
    # 都已存在，那样一个域都收集不到，域目录的 __init__.py 永远补不回来 ——
    # 而「删掉一个 __init__.py 再跑一次生成器」正是最需要它自愈的场景。
    domains = {module_path(spec["id"]).parts[0] for spec in ordered}

    for spec, src in sources:
        rel = module_path(spec["id"])
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and not force:
            continue
        target.write_text(src, encoding="utf-8")
        written.append(target)

    for domain in sorted(domains):
        init = root / domain / "__init__.py"
        init.write_text(_emit_domain_init(domain), encoding="utf-8")
        written.append(init)

    agg = root / "__init__.py"
    agg.write_text(agg_src, encoding="utf-8")
    written.append(agg)
    return written


def main() -> int:
    import argparse

    from gimbal_bootstrap.contract_gen import PLATFORM_BASE_URL, fetch_openapi

    default_root = (
        Path(__file__).resolve().parents[2]
        / f"gimbal_plate/systems/{SYSTEM}/endpoint"
    )
    parser = argparse.ArgumentParser(
        description="从平台 OpenAPI 生成 plate 的结构化 py 契约定义"
    )
    parser.add_argument("--base-url", default=PLATFORM_BASE_URL)
    parser.add_argument("--out-root", default=str(default_root))
    parser.add_argument(
        "--force",
        action="store_true",
        help="覆盖已存在的端点文件（默认跳过，保住人工核订的注释）",
    )
    args = parser.parse_args()

    specs, warnings = build_specs(fetch_openapi(args.base_url, allow_inprocess_fallback=True))
    written = emit_package(specs, Path(args.out_root), force=args.force)
    print(f"generated {len(specs)} endpoints -> {len(written)} files under {args.out_root}")
    for w in warnings:
        print("WARN:", w)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
