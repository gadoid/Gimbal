"""孪生生成器 CLI:S1→S5 串联。

真实源默认值指向 D:\fin-test;产物默认落 src/gimbal-plate/tmp/twin_gen(不入册)。
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
from .s2c_frontend import scan_frontend, fe_to_json
from .s3_semantics import enrich
from .s4_state import assign
from .s5_emit import emit_all, compare_faces

# cli.py → twin_generator → tools → gimbal-plate → src → repo 根
REPO = Path(__file__).resolve().parents[4]

# 产物永不写 gimbal_plate 包内,除非显式 --install-dir(人工 gate)
_PLATE_PKG = (REPO / "src" / "gimbal-plate" / "gimbal_plate").resolve()


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
                     if d.value_source else None, d.ui_kind)
            for d in ep.request.declarations
        }
    return ids, views, faces


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="fin SUT 请求面孪生生成器")
    ap.add_argument("--app-root", default=r"D:\fin-test\api\Application")
    ap.add_argument("--schema-csv", default=r"D:\fin-test\fin_test_search.csv")
    ap.add_argument("--js-dir", default=r"D:\fin-test\static\js",
                    help="前端 webpack chunk 目录(S2c;传空串跳过)")
    ap.add_argument("--out", default=str(REPO / "src/gimbal-plate/tmp/twin_gen"))
    ap.add_argument("--baseline", default="fin-test@2026-09-15")
    ap.add_argument("--only", default="", help="逗号分隔 action 过滤(orderAdd,...)")
    ap.add_argument("--modules", default="",
                    help="逗号分隔模块过滤(Order,Customer,Audit;试点用)")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--verify", action="store_true",
                    help="产物自检:import+唯一性+信封 → verify_report.json")
    ap.add_argument("--install-dir", default="", help="人工 gate 后的正式落盘目录")
    args = ap.parse_args(argv)

    from .schema_source import load_columns
    app_root = Path(args.app_root)
    actions = scan_actions(app_root)
    if args.modules:
        mods = {s.strip() for s in args.modules.split(",") if s.strip()}
        actions = [a for a in actions if a.module in mods]
    if args.only:
        keep = {s.strip() for s in args.only.split(",") if s.strip()}
        actions = [a for a in actions if a.action in keep]
    attach_rules(actions, app_root)
    collect_reads(actions, app_root)
    fe_faces: dict = {}
    if args.js_dir:
        fe_faces = scan_frontend(Path(args.js_dir), actions)
    from .s3_lang import load_langs, lang_zh, load_headers
    common_by_ctrl, module_langs = load_langs(app_root)
    lang_views = {a.id: lang_zh(a.controller, a.module,
                                common_by_ctrl, module_langs)
                  for a in actions}
    header_views = load_headers(app_root)
    from .module_tables import build_index
    mod_tables_views = build_index(app_root, sorted({a.module for a in actions}))
    from .s3_semantics import load_enums
    enums = load_enums(app_root)
    from .s2_groups import detect_groups, detect_containers
    groups = detect_groups(actions, app_root)
    container_sigs = detect_containers(actions, app_root)
    catalog = load_columns(args.schema_csv)
    all_fields = enrich(actions, catalog, fe_faces, lang_views,
                        header_views, mod_tables_views, enums, groups,
                        container_sigs)
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
    if args.js_dir:
        (out / "frontend_faces.json").write_text(json.dumps(
            fe_to_json(fe_faces), ensure_ascii=False, indent=2),
            encoding="utf-8")
    lines = ["# value_source 消歧队列", ""]
    for act_id, key, views_ in report.ambiguous:
        lines.append(f"- `{act_id}` :: `{key}` → {sorted(views_)}")
    (out / "disambiguation.md").write_text("\n".join(lines), encoding="utf-8")

    target = Path(args.install_dir) if args.install_dir else out / "endpoints"
    if not args.install_dir:
        r = target.resolve()
        if r == _PLATE_PKG or _PLATE_PKG in r.parents:
            raise SystemExit(
                f"拒绝写入 {r}(gimbal_plate 包内)。产物不入册 —— 需要人工 gate "
                "请显式传 --install-dir。")
    summary = emit_all(actions, all_fields, target, existing_ids, args.baseline)
    print(f"emitted={summary['emitted']} skipped={summary['skipped']} "
          f"needs_capture={summary['needs_capture']}")

    if args.compare:
        # T6.1 missing 分档证据:FE 面(该端点全部键)vs 次级源键全集
        evidence = {}
        for a in actions:
            fe = fe_faces.get(a.id)
            fe_keys = (set(fe.form_keys) | set(fe.payload_keys)
                       | set(fe.label_keys)) if fe else set()
            be_keys = (set(lang_views.get(a.id, {}))
                       | set(header_views.get(a.controller.lower(), {}))
                       | set(catalog.by_name))
            evidence[a.id] = (fe_keys, be_keys)
        md = compare_faces(all_fields, faces, evidence)
        (out / "compare_report.md").write_text(md, encoding="utf-8")
        print(f"compare_report → {out / 'compare_report.md'}")
    if args.verify:
        from .verify_emit import verify_dir
        vr = verify_dir(target)
        (out / "verify_report.json").write_text(json.dumps(
            vr, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"verify: {vr['ok']}/{vr['files']} ok"
              f"({len(vr['errors'])} 文件有错)→ {out / 'verify_report.json'}")
        if vr["errors"]:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
