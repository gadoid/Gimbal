"""孪生生成器 CLI:S1→S5 串联。

真实源默认值指向 D:\fin-test;产物默认落 gimbal-tmp/twin_gen(永不提交)。
--install-dir 才写 gimbal_plate 包内(人工 gate 后)。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .s1_routes import scan_actions
from .s2_validator import attach_rules
from .s2_reads import collect_reads
from .s3_semantics import enrich
from .s4_state import assign
from .s5_emit import emit_all, compare_faces

# cli.py → twin_generator → tools → gimbal-plate → src → repo 根
REPO = Path(__file__).resolve().parents[4]


def _plate_registry():
    """(existing_ids, view_rows, handbuilt_faces);plate 不可 import → 全空降级。"""
    sys.path.insert(0, str(REPO / "src" / "gimbal-plate"))
    try:
        from gimbal_plate.systems.fin.endpoint import ALL_ENDPOINTS
        from gimbal_plate.service.query_views import build_query_view_index
    except Exception:
        return set(), [], {}
    ids = {ep.id for ep in ALL_ENDPOINTS}
    views = build_query_view_index(ALL_ENDPOINTS)
    faces = {}
    for ep in ALL_ENDPOINTS:
        if ep.request is None:
            continue
        # vs 存完整 (view, column) 元组:s5_emit.compare_faces 对 vs 做
        # tuple(vs) 后与生成侧 FieldIR.value_source(元组)比对,传裸字符串
        # 会被逐字符拆元组 → 恒判 diff。
        faces[ep.id] = {
            d.name: (d.state, d.description, d.enum, d.required,
                     (d.value_source.view, d.value_source.column)
                     if d.value_source else None)
            for d in ep.request.declarations
        }
    return ids, views, faces


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="fin SUT 请求面孪生生成器")
    ap.add_argument("--app-root", default=r"D:\fin-test\api\Application")
    ap.add_argument("--schema-csv", default=r"D:\fin-test\fin_test_search.csv")
    ap.add_argument("--out", default=str(REPO / "gimbal-tmp" / "twin_gen"))
    ap.add_argument("--baseline", default="fin-test@2026-09-15")
    ap.add_argument("--only", default="", help="逗号分隔 action 过滤(orderAdd,...)")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--install-dir", default="", help="人工 gate 后的正式落盘目录")
    args = ap.parse_args(argv)

    from .schema_source import load_columns
    app_root = Path(args.app_root)
    actions = scan_actions(app_root)
    if args.only:
        keep = {s.strip() for s in args.only.split(",") if s.strip()}
        actions = [a for a in actions if a.action in keep]
    attach_rules(actions, app_root)
    collect_reads(actions, app_root)
    catalog = load_columns(args.schema_csv)
    all_fields = enrich(actions, catalog)
    existing_ids, view_rows, faces = _plate_registry()
    report = assign(all_fields, actions, catalog, view_rows)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "routes.json").write_text(json.dumps(
        [{"id": a.id, "path": a.path, "rules": len(a.rules),
          "reads": len(a.reads)} for a in actions],
        ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "fields.json").write_text(json.dumps(
        {k: [f.__dict__ for f in v] for k, v in all_fields.items()},
        ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    lines = ["# value_source 消歧队列", ""]
    for act_id, key, views_ in report.ambiguous:
        lines.append(f"- `{act_id}` :: `{key}` → {sorted(views_)}")
    (out / "disambiguation.md").write_text("\n".join(lines), encoding="utf-8")

    target = Path(args.install_dir) if args.install_dir else out / "endpoints"
    summary = emit_all(actions, all_fields, target, existing_ids, args.baseline)
    print(f"emitted={summary['emitted']} skipped={summary['skipped']} "
          f"needs_capture={summary['needs_capture']}")

    if args.compare:
        md = compare_faces(all_fields, faces)
        (out / "compare_report.md").write_text(md, encoding="utf-8")
        print(f"compare_report → {out / 'compare_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
