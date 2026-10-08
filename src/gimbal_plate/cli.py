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
    root = _REPO / "systems" / system
    if not root.is_dir():
        print(f"error: 未知系统 {system!r}(目录不存在: {root})", file=sys.stderr)
        raise SystemExit(2)
    return root


def _load_tree(system: str):
    from gimbal_plate.dialect import EndpointSpec, Statement, Term, parse_markdown

    root = _repo_system(system)
    deliverables, endpoints, statements, terms = [], [], [], {}
    for md in sorted(root.rglob("*.md")):
        d = parse_markdown(md.read_text(encoding="utf-8"), source=str(md))
        deliverables.append(d)
        for b in d.blocks():
            for m in b.models():
                if isinstance(m, EndpointSpec):
                    endpoints.append(m)
                elif isinstance(m, Statement):
                    statements.append(m)
                elif isinstance(m, Term):
                    terms[m.id] = m
    return root, deliverables, endpoints, statements, terms


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
    _, _, _, _, terms = _load_tree(args.system)
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
        # 方言错误不裸抛 traceback(评审 P1):转 finding,退出码 1
        from gimbal_plate.dialect.validation import Finding
        report.add(Finding("F0", "blocking", str(e),
                           source=str(e).split(":", 1)[0],
                           line=int(str(e).split(":", 2)[1])
                           if str(e).count(":") >= 2 else 0))
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
    """结构化差异:两 release manifest 比 hash(对象级);--base working 时
    与当前树比 shape_hash(G7 简版;字段级 diff 属 B 后续)。"""
    arts = _REPO / "plate_artifacts"
    rel_dir = arts / args.system / "releases"
    releases = sorted(
        (d.name for d in rel_dir.iterdir() if d.is_dir())) if rel_dir.exists() else []
    if len(releases) < 2:
        print(f"不足两个 release(现有 {releases});diff 需要 ≥2 个 manifest")
        return 1
    a_name = args.base if args.base else releases[-2]
    b_name = releases[-1]
    m_a = json.loads((rel_dir / a_name / "manifest.json").read_text(encoding="utf-8"))
    m_b = json.loads((rel_dir / b_name / "manifest.json").read_text(encoding="utf-8"))
    ha = {o["id"]: o["hash"] for o in m_a["objects"]}
    hb = {o["id"]: o["hash"] for o in m_b["objects"]}
    changed = sorted(k for k in ha.keys() & hb.keys() if ha[k] != hb[k])
    added = sorted(hb.keys() - ha.keys())
    removed = sorted(ha.keys() - hb.keys())
    out = {"from": a_name, "to": b_name, "changed": changed,
           "added": added, "removed": removed}
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print(f"{a_name} → {b_name}: {len(changed)} 变更 / "
              f"{len(added)} 新增 / {len(removed)} 移除")
        for k in changed:
            print(f"  ~ {k}")
        for k in added:
            print(f"  + {k}")
        for k in removed:
            print(f"  - {k}")
    return 0


def cmd_gaps(args: argparse.Namespace) -> int:
    from gimbal_plate.dialect.gaps import gaps_report
    *_, endpoints, statements, terms = [
        *_load_tree(args.system)[2:],
    ]
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
    from gimbal_plate.release import release_system

    r = release_system(
        _repo_system(args.system), artifacts_root=_REPO / "plate_artifacts",
        signed_by=args.signed_by or "",
    )
    if args.json:
        print(json.dumps({
            "success": r.success, "release_id": r.release_id,
            "message": r.message,
            "report": r.report.to_dict() if r.report else None,
            "summary": r.manifest["summary"] if r.manifest else None,
        }, ensure_ascii=False, indent=1))
    else:
        print(f"{'OK' if r.success else 'BLOCKED'}: {r.message}")
    return 0 if r.success else 1


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
    sp.set_defaults(fn=cmd_check)

    sp = sub.add_parser("diff", help="结构化差异(两 manifest 比 hash)")
    sp.add_argument("system", nargs="?", default="fin")
    sp.add_argument("--base")
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

    sp = sub.add_parser("release", help="冻结(发布闸门)")
    sp.add_argument("system", nargs="?", default="fin")
    sp.add_argument("--signed-by", default="")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(fn=cmd_release)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.fn(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
