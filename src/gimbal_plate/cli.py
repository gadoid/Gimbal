"""plate CLI（批次 D，独立 console script——附录 D 入口已定）。

命令（附录 D；``--json`` 输出与 G2/G7 对齐）：

    plate new <type>                        按类型模板生成骨架
    plate term search <词> [--json]         词条候选检索(G3:label/alias/相似度)
    plate check [系统] [--json] [--stdin]   校验(规则编号即错误码,带文件:行号)
    plate diff [系统] [--base <ref>] [--json]  结构化差异(两 manifest 比 hash)
    plate gaps [系统] [--json]              定义完整性缺口(G6)
    plate review <交付物id|块id> [--set reviewed|draft]  评审置位(N4)
    plate reload [系统]                     重载 working 快照(S1 显式触发)
    plate release [系统] [--signed-by <人>] [--json]     冻结
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
from pathlib import Path
from typing import Any

# 仓库根:包位置回溯;wheel(非 editable)安装后回溯到 venv,数据目录
# (systems/、types/)不在那里——PLATE_REPO_ROOT 显式覆盖(评审 M2:
# 让非 editable 安装的 check/gaps/release 在指定 checkout 上可用,
# CI 的 wheel 冒烟即走此入口)。
_REPO = (Path(os.environ["PLATE_REPO_ROOT"])
         if os.environ.get("PLATE_REPO_ROOT")
         else Path(__file__).resolve().parents[2])
_TYPES = _REPO / "types" / "types.yaml"


def _repo_system(system: str) -> Path:
    # O4(第七轮):不合规名字独立拦截——目录存在也不让过 CI 的 check
    # (loader 会静默跳过它,服务里不出现;check 必须替它报出来)
    from gimbal_plate.loader import SYSTEM_NAME_RE
    if not SYSTEM_NAME_RE.match(system):
        print(f"error: 系统名 {system!r} 不合规({SYSTEM_NAME_RE.pattern}),"
              f"服务不会加载该目录", file=sys.stderr)
        raise SystemExit(2)
    root = _REPO / "systems" / system
    if not root.is_dir():
        hint = ""
        if not os.environ.get("PLATE_REPO_ROOT") and "site-packages" in str(_REPO):
            hint = ("\n(wheel 安装的包位置回溯不到数据目录——"
                    "设 PLATE_REPO_ROOT 指向仓库 checkout)")
        print(f"error: 未知系统 {system!r}(目录不存在: {root}){hint}",
              file=sys.stderr)
        raise SystemExit(2)
    return root


def _load_tree(system: str):
    """装配系统树(评审 J1:与 check/release/gaps 同一 collect_system_tree,
    不再各写一份遍历)。"""
    from gimbal_plate.dialect.validation import collect_system_tree

    root = _repo_system(system)
    tree = collect_system_tree(root)
    return (root, tree.deliverables, tree.endpoints, tree.statements, tree.terms)


# ── 命令 ──────────────────────────────────────────────────────────

def cmd_new(args: argparse.Namespace) -> int:
    from gimbal_plate.dialect.validation import load_types

    types = load_types(_TYPES)
    template = types.get(args.type)
    if template is None:
        print(f"error: 未知类型 {args.type!r}(合法: {sorted(types)})",
              file=sys.stderr)
        return 2
    system = args.system
    target = _REPO / "systems" / system
    slug = args.id or f"new-{args.type}"
    default_dir = {
        "endpoints": "endpoints", "dictionary": "dictionary",
    }.get(args.type, "deliverables")
    base = target / (args.path or (default_dir + "/" + slug))
    path = base if base.suffix == ".md" else base.with_name(base.name + ".md")
    if path.suffix != ".md":
        path = path.with_name(path.name + ".md")
    if path.exists():
        print(f"error: 文件已存在 {path}", file=sys.stderr)
        return 2
    blocks: list[str] = []
    for block_type in template.get("blocks", []):
        if block_type == "endpoint":
            blocks.append(
                "```gimbal:endpoint\nid: <系统>.<服务>.<名>\nsystem: "
                f"{system}\nservice: <服务>\nname: <名>\nbinding:\n  "
                "protocol: http\n  method: GET\n  path: /<路径>\n"
                "responses:\n  '200': {}\n```"
            )
        elif block_type == "term":
            blocks.append(
                "```gimbal:term\n- id: entity:<实体>\n  label: <业务名>\n"
                "- id: cap:<实体>.<动作>\n  label: <业务名>\n```"
            )
        elif block_type == "statement":
            kinds = template.get("statement_kinds", ["note"])
            blocks.append(
                f"```gimbal:statement\nid: st.<域>.<名>\nkind: {kinds[0]}\n"
                "# 按 kind 填槽位(plate check 校验;slots 省略 = 空)\n"
                "```\n\n<片段原文>"
            )
        else:  # system / defaults
            blocks.append(f"```gimbal:{block_type}\n# 按 6.2/8e 填写\n```")
    fm = f"---\nid: {system}.{args.type}.{slug}\ntype: {args.type}\n" \
         f"system: {system}\n---\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(fm + "\n# " + (template.get("label") or args.type) + "\n\n"
                    + "\n\n".join(blocks) + "\n", encoding="utf-8", newline="\n")
    print(f"created: {path}")
    return 0


def cmd_term_search(args: argparse.Namespace) -> int:
    from gimbal_plate.dialect.parser import DialectError
    try:
        _, _, _, _, terms = _load_tree(args.system)
    except DialectError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    # common 一并检索(解析顺序:本系统 → common)
    for m in sorted((_REPO / "systems" / "common").rglob("*.md")):
        from gimbal_plate.dialect import parse_markdown, Term
        for b in parse_markdown(m.read_text(encoding="utf-8"),
                                source=str(m)).blocks("term"):
            for t in b.models():
                if isinstance(t, Term):
                    terms.setdefault(t.id, t)

    needle = args.query.lower()
    hits: list[dict[str, Any]] = []
    for t in terms.values():
        reasons: list[str] = []
        if needle in t.label.lower():
            reasons.append("label")
        if any(needle in a.lower() for a in t.aliases):
            reasons.append("alias")
        ratio = difflib.SequenceMatcher(
            None, needle, t.label.lower()).ratio()
        if ratio >= 0.6:
            reasons.append(f"similarity:{ratio:.2f}")
        if reasons:
            hits.append({
                "id": t.id, "label": t.label, "gloss": t.gloss,
                "status": t.status, "matched_by": reasons,
            })
    hits.sort(key=lambda h: -max(
        (float(r.split(":")[1]) if r.startswith("similarity") else 1.0)
        for r in h["matched_by"]))
    if args.json:
        print(json.dumps({"query": args.query, "hits": hits},
                         ensure_ascii=False, indent=1))
    else:
        for h in hits[:20]:
            print(f"{h['id']:<36} {h['label']}"
                  f"  [{'/'.join(h['matched_by'])}]")
        if not hits:
            print("(无候选——可新建词条,先查再建已尽)")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    from gimbal_plate.dialect.validation import ValidationReport, load_types
    from gimbal_plate.dialect.parser import DialectError
    text = sys.stdin.read() if args.stdin else None
    types = load_types(_TYPES)
    report = ValidationReport()
    try:
        _check_body(args, text, types, report)
    except DialectError as e:
        # 方言错误不裸抛 traceback(评审 P1):转 finding,退出码 1。
        # J5:直接用异常自带的 source/line——此前拆报错字符串,Windows
        # 盘符路径(C:\...)会把列拆错;系统级 check 的 F0 已由
        # validate_system_tree 内部生成,这里兜 --stdin 单文件路径。
        from gimbal_plate.dialect.validation import Finding
        report.add(Finding("F0", "blocking", str(e),
                           source=e.source, line=e.line))
    _emit_check(args, report)
    return 0 if report.ok else 1


def _check_body(args, text, types, report) -> None:
    from gimbal_plate.dialect.validation import validate_system_tree
    if text is not None:
        from gimbal_plate.dialect import parse_markdown
        from gimbal_plate.dialect.validation import validate_deliverable
        d = parse_markdown(text, source="<stdin>")
        validate_deliverable(d, types=types, report=report)
        return
    # S1.5a(评审质量尾项):--all 遍历 systems 根下全部系统目录——CI
    # 此前写死系统名清单,多出来的目录(如 fin.v2)能通过 CI 却在服务里
    # 被 loader 静默跳过;--all 让每个真实存在的目录都过一遍闸门。
    if getattr(args, "all", False):
        from gimbal_plate.loader import SYSTEM_NAME_RE
        systems_root = _REPO / "systems"
        names = sorted(
            d.name for d in systems_root.iterdir()
            if d.is_dir() and SYSTEM_NAME_RE.match(d.name)
        )
        illegal = sorted(
            d.name for d in systems_root.iterdir()
            if d.is_dir() and not SYSTEM_NAME_RE.match(d.name)
        )
        for name in illegal:
            print(f"error: 系统目录 {name!r} 名字不合规,"
                  f"服务不会加载该目录", file=sys.stderr)
        for name in names:
            validate_system_tree(
                systems_root / name, types=types, report=report)
        return
    # 统一 check 引擎(评审 R10):CLI 与 HTTP system/action/check 调同一
    # validate_system_tree(common 参照 + 树级 F3 + C 类,与 release 机械检查同口径)。
    validate_system_tree(_repo_system(args.system), types=types, report=report)


def _emit_check(args, report) -> None:
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=1))
    else:
        for f in report.findings:
            loc = f"{f.source}:{f.line}" if f.source else "-"
            print(f"[{f.severity:<9}] {f.rule:<3} {loc:<40} {f.message}")
        print(f"{'OK' if report.ok else 'BLOCKED'}: "
              f"{len(report.blocking)} blocking / {len(report.warnings)} warnings"
              f" / {len(report.corrections)} corrections")


def cmd_diff(args: argparse.Namespace) -> int:
    """结构化差异(版本模型 §7 / Release 4.3):对象级 + 变化接口的部位。

    ``plate diff <系统> <a> <b>``——a/b 为 ``<line>#<n>`` / ``<line>``(最新)
    / ``working``(当前源树);可跨版本线。
    """
    from gimbal_plate.release import read as release_read
    from gimbal_plate.release.release import resolve_artifacts_root

    try:
        root = resolve_artifacts_root()
    except RuntimeError as e:
        print(f"BLOCKED: {e}")
        return 2
    a = args.a or args.base
    if not a:
        print("用法: plate diff <系统> <a> <b>  (a/b: <line>#<n> | <line> | working)")
        return 1

    def _snap(ref: str):
        if ref == "working":
            from gimbal_plate.dialect.validation import collect_system_tree

            fin = _repo_system(args.system)
            tree = collect_system_tree(fin)
            snap = release_read.RevisionSnapshot(
                system=args.system, line="working", n=0, manifest={})
            for ep in tree.endpoints:
                snap.endpoints[ep.id] = ep
            return snap
        line, n, _m = release_read.resolve_revision(root, args.system, ref)
        return release_read.load_snapshot(root, args.system, line, n)

    try:
        out = release_read.diff_snapshots(_snap(a), _snap(args.b))
    except release_read.ReleaseReadError as e:
        print(f"BLOCKED: {e.message}")
        return 1
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print(f"{out['from']} → {out['to']}: {len(out['changed'])} 变更 / "
              f"{len(out['added'])} 新增 / {len(out['removed'])} 移除")
        for k, v in out["changed"].items():
            parts = v.get("parts") or {}
            tags = ",".join(parts.keys()) or "-"
            print(f"  ~ {k}  [{tags}]")
        for k in out["added"]:
            print(f"  + {k}")
        for k in out["removed"]:
            print(f"  - {k}")
    return 0


def cmd_gaps(args: argparse.Namespace) -> int:
    from gimbal_plate.dialect.gaps import gaps_report
    from gimbal_plate.dialect.parser import DialectError
    try:
        *_, endpoints, statements, terms = [
            *_load_tree(args.system)[2:],
        ]
    except DialectError as e:
        # J5 残留(第六轮):内容错误不裸 traceback(与 check 的 F0 同源)
        print(f"error: {e}", file=sys.stderr)
        return 2
    out = gaps_report(endpoints, statements, terms)
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        for k, v in out["items"].items():
            print(f"{k:<36} {v}")
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    """评审置位(N4):块信封 review 字段改写,规范形回写只动该块。"""
    from gimbal_plate.dialect import parse_markdown, render
    from gimbal_plate.dialect.parser import Block

    target_id = args.target
    value = args.set or "reviewed"
    hits = 0
    for system_dir in sorted((_REPO / "systems").iterdir()):
        if not system_dir.is_dir():
            continue
        for md in sorted(system_dir.rglob("*.md")):
            d = parse_markdown(md.read_text(encoding="utf-8"), source=str(md))
            dirty = False
            for n in d.nodes:
                if not isinstance(n, Block):
                    continue
                ids = [getattr(m, "id", "") for m in n.models()]
                fm_id = (d.frontmatter.id or "") if d.frontmatter else ""
                if target_id in ids or target_id == fm_id:
                    if n.review != value:
                        n.review = value
                        dirty = True
                    hits += 1
            if dirty:
                md.write_text(render(d), encoding="utf-8", newline="\n")
                print(f"reviewed -> {value}: {md}")
    if not hits:
        print(f"error: 未找到 {target_id!r}", file=sys.stderr)
        return 2
    return 0


def cmd_reload(args: argparse.Namespace) -> int:
    """重载 working 快照(生产由 CI 触发;本地显式)。"""
    from gimbal_plate.loader import load_registry

    reg = load_registry([_REPO / "systems"])
    n = len(list(reg.list_endpoints()))
    print(f"reloaded working snapshot: {n} endpoints, "
          f"systems={reg.list_systems()}")
    return 0


def cmd_release(args: argparse.Namespace) -> int:
    from gimbal_plate.release import release_system, resolve_artifacts_root

    try:
        resolve_artifacts_root()
    except RuntimeError as e:
        print(f"BLOCKED: {e}")
        return 2
    r = release_system(_repo_system(args.system),
                       signed_by=args.signed_by or "")
    if args.json:
        print(json.dumps({
            "success": r.success, "line": r.line, "revision": r.revision,
            "message": r.message,
            "report": r.report.to_dict() if r.report else None,
            "summary": r.manifest["summary"] if r.manifest else None,
        }, ensure_ascii=False, indent=1))
    else:
        print(f"{'OK' if r.success else 'BLOCKED'}: {r.message}")
    return 0 if r.success else 1


def cmd_lines(args: argparse.Namespace) -> int:
    """列出版本线与修订(版本模型 2.4;构件根只读)。"""
    from gimbal_plate.release import (
        latest_revision_manifest,
        resolve_artifacts_root,
    )

    try:
        root = resolve_artifacts_root()
    except RuntimeError as e:
        print(f"BLOCKED: {e}")
        return 2
    system_dir = root / args.system / "lines"
    lines: list[dict] = []
    if system_dir.is_dir():
        for line_dir in sorted(system_dir.iterdir()):
            if not line_dir.is_dir():
                continue
            nums = sorted(int(p.name) for p in line_dir.iterdir()
                          if p.is_dir() and p.name.isdigit())
            if not nums:
                continue
            latest = latest_revision_manifest(root, args.system, line_dir.name)
            latest_manifest = latest[1] if latest else {}
            lines.append({
                "line": line_dir.name,
                "revisions": len(nums),
                "latest": f"{line_dir.name}#{nums[-1]}",
                "line_scheme": latest_manifest.get("line_scheme"),
                "latest_signed_by": latest_manifest.get("signed_by"),
            })
    if args.json:
        print(json.dumps({"system": args.system, "lines": lines},
                         ensure_ascii=False, indent=1))
    elif lines:
        for l in lines:
            print(f"{l['line']}\t{l['revisions']} 个修订\t最新 {l['latest']}"
                  f"\tscheme={l['line_scheme']}")
    else:
        print(f"{args.system}: 尚无版本线(构件根 {root})")
    return 0


def cmd_cold_archive(args: argparse.Namespace) -> int:
    """冷化判定查询（Release v4.4 §9 / RS5）：列出可冷化的修订。"""
    from gimbal_plate.release.cold_archive import list_cold_archivable
    from gimbal_plate.release.release import resolve_artifacts_root

    try:
        root = resolve_artifacts_root()
    except RuntimeError as e:
        print(f"BLOCKED: {e}")
        return 2

    referenced: dict = {}
    pinned: dict = {}
    if args.referenced:
        referenced = json.loads(
            Path(args.referenced).read_text(encoding="utf-8"))
    if args.pinned:
        pinned = json.loads(
            Path(args.pinned).read_text(encoding="utf-8"))

    items = list_cold_archivable(root, referenced_revisions=referenced,
                                 pinned_revisions=pinned)
    if args.json:
        print(json.dumps({"items": items, "total": len(items)},
                         ensure_ascii=False, indent=1))
    elif items:
        for item in items:
            print(f"{item['system']}@{item['revision']}  "
                  f"signed={item['signed_by']}  "
                  f"at={item['released_at'][:10]}")
    else:
        print("无可冷化修订（全部被引用或可能成为生效修订）")
    return 0


def cmd_migrate_m2(args):
    import json as _json
    from gimbal_plate.schema import M2_GENERATION
    from gimbal_plate.schema.migrate import migrate_definition
    value = _json.loads(Path(args.file).read_text(encoding="utf-8"))
    migrated = migrate_definition(value, args.from_gen)
    text = _json.dumps(migrated, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8", newline=chr(10))
        print(f"migrated {args.file} gen {args.from_gen} to {M2_GENERATION}")
    else:
        print(text)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="plate", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("new", help="按类型模板生成骨架")
    sp.add_argument("type")
    sp.add_argument("--system", required=True)
    sp.add_argument("--id")
    sp.add_argument("--path")
    sp.set_defaults(fn=cmd_new)

    sp = sub.add_parser("term", help="词条候选检索(G3)")
    sp.add_argument("search")
    sp.add_argument("query")
    sp.add_argument("--system", default="fin")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(fn=cmd_term_search)

    sp = sub.add_parser("check", help="校验(--json 规则编号即错误码)")
    sp.add_argument("system", nargs="?", default="fin")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--stdin", action="store_true")
    sp.add_argument("--all", action="store_true",
                    help="检查 systems 根下全部系统目录(CI 口径)")
    sp.set_defaults(fn=cmd_check)

    sp = sub.add_parser(
        "diff", help="结构化差异(对象级+变化部位;a/b 为 <line>#<n>/<line>/working)")
    sp.add_argument("system", nargs="?", default="fin")
    sp.add_argument("a", nargs="?", default=None)
    sp.add_argument("b", nargs="?", default="working")
    sp.add_argument("--base", default=None,
                    help="(兼容旧写法)等价于位置参数 a")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(fn=cmd_diff)

    sp = sub.add_parser("gaps", help="定义完整性缺口(G6)")
    sp.add_argument("system", nargs="?", default="fin")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(fn=cmd_gaps)

    sp = sub.add_parser("review", help="评审置位(N4)")
    sp.add_argument("target")
    sp.add_argument("--set", choices=["draft", "reviewed"], default="reviewed")
    sp.set_defaults(fn=cmd_review)

    sp = sub.add_parser("reload", help="重载 working 快照")
    sp.add_argument("system", nargs="?", default=None)
    sp.set_defaults(fn=cmd_reload)

    sp = sub.add_parser("release", help="签发修订(版本模型;构件提交到构件分支)")
    sp.add_argument("system", nargs="?", default="fin")
    sp.add_argument("--signed-by", default="")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(fn=cmd_release)

    sp = sub.add_parser(
        "cold-archive", help="冷化判定：列出可冷化的修订(RS5)")
    sp.add_argument("--referenced",
                    help="被引用修订 JSON 文件 {系统: [line#n, ...]}")
    sp.add_argument("--pinned",
                    help="执行记录钉住修订 JSON 文件")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(fn=cmd_cold_archive)
    sp = sub.add_parser("migrate-m2", help="M2 generation migration")
    sp.add_argument("file")
    sp.add_argument("--from-gen", type=int, default=1)
    sp.add_argument("--output", default="")
    sp.set_defaults(fn=cmd_migrate_m2)

    sp = sub.add_parser("lines", help="列出版本线与修订(版本模型 2.4)")
    sp.add_argument("system", nargs="?", default="fin")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(fn=cmd_lines)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.fn(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
