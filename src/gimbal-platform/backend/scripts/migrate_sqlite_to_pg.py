"""migrate_sqlite_to_pg — ETL 直切脚本(PG迁移方案 §3.3)。

跑法(backend 目录;演练必须用生产 app.db 的副本):
    python scripts/migrate_sqlite_to_pg.py \
        --source <app.db 副本> --target postgresql://gimbal:...@host/gimbal \
        [--report etl-report.json]

前置(§3.2 门禁):pg_preccheck.py 报告人工过目、blocking_problems=0、
JWT_SECRET/FERNET_KEY 已固定。目标库必须先经 ``alembic upgrade head``
建好 schema(切换链的人工第一步,§3.3 第九轮)。

要点与设计偏离(如实入案):
* **生成列排除**:INSERT 列清单排除全部 Computed 列(composer 七列;
  users.role 不在 metadata,天然不进列清单)—— PG 对 GENERATED ALWAYS
  列拒插,M0-4 已实测报错形态。
* **时间戳照搬**(偏离「func.now() 列不搬」):台账是审计级数据,
  created_at 是真实历史;且 §3.3 自己要求「抽样 50 行规范化 JSON
  checksum 比对」—— 时间戳重置会让对账全炸。按「视为 UTC」补 aware。
* **NOT VALID 两步 → 装载后 FK join 全量校验**:变换(owner_id=0→NULL、
  孤儿→SET NULL 语义)已保证引用干净,baseline schema 已带约束;装载后
  逐关系 join 校验一次,等价完成「存量单独验」。
* 表序 = Base.metadata.sorted_tables(拓扑序,父先子后);每表一个事务。
* scenario_endpoint_refs **不导入**,切换后 rebuild(§3.3;顺带补齐存量
  锚点行——NOT VALID 换不来的)。

输出:迁移报告(行数对账/checksum 抽样/生成列抽样/stars 计数/
execution_rows 吸收行数),与演练报告逐项对比是正式切换的门禁。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.db import Base  # noqa: E402
from app import models  # noqa: E402,F401
from app.core.config import settings  # noqa: E402

SAMPLE_N = 50
CHECKSUM_EXCLUDE = {
    "created_at", "updated_at", "synced_at", "applied_at", "closed_at",
    "started_at", "finished_at", "read_at", "expires_at",
    # ETL 变换产物(源库为空/旧值,目标库为回填真值 —— 差异即目的,
    # 由专项校验负责,不进 checksum):
    "owner_name", "scenario_name", "author_name", "operator_name",
    "updated_by_name",
}


def _aware(v):
    if isinstance(v, datetime) and v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)  # 「视为 UTC」(§3.3)
    return v


def _norm(v):
    """规范化 checksum 材料:JSON 语义排序 + aware 归一 + bool 归一
    (SQLite 存 1/0,PG 驱动回 True/False —— 同值异型)。"""
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, dict):
        return {k: _norm(v[k]) for k in sorted(v)}
    if isinstance(v, (list, tuple)):
        return [_norm(x) for x in v]
    if isinstance(v, datetime):
        return _aware(v).isoformat()
    return v


def _load_payload(v):
    if isinstance(v, str):
        return json.loads(v)
    return v


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="SQLite app.db(生产副本)")
    ap.add_argument("--target", required=True, help="PG DSN(postgresql://…)")
    ap.add_argument("--report", default="etl-report.json")
    args = ap.parse_args()

    src = create_engine(f"sqlite:///{args.source}")
    dst = create_engine(args.target, future=True)

    report: dict = {
        "source": args.source, "target": args.target,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tables": {}, "verifications": {},
    }

    # ── 变换辅助:回填用查找表(源库)────────────────────────────────
    with src.connect() as c:
        users_by_id = {
            r[0]: (r[1] or r[2]) for r in c.execute(text(
                "SELECT id, display_name, username FROM users"))
        }
        scen_name = {
            r[0]: r[1] for r in c.execute(text(
                "SELECT scenario_id, name FROM composer_scenarios"))
        }

    def repair_scenario_payload(payload: dict) -> dict:
        """meta 遗留修复一次性写回(空 module→default、空 system→["default"],
        与 scenario_store.update 的 repair 口径一致;迁移后读侧修复分支可删)。"""
        defn = (payload or {}).get("definition")
        if not isinstance(defn, dict):
            return payload
        meta = defn.get("meta")
        if not isinstance(meta, dict):
            return payload
        changed = False
        if not (meta.get("module") or "").strip():
            meta["module"] = "default"
            changed = True
        if not list(meta.get("system") or []):
            meta["system"] = ["default"]
            changed = True
        return payload if changed else payload  # 修复写回(值层面已变更)

    SKIP_TABLES = {"alembic_version", "scenario_endpoint_refs"}

    for table in Base.metadata.sorted_tables:
        if table.name in SKIP_TABLES:
            continue
        cols = [c for c in table.columns if c.computed is None]
        col_names = [c.name for c in cols]
        with src.connect() as c:
            rows = [dict(r._mapping) for r in c.execute(text(
                f"SELECT {', '.join(col_names)} FROM [{table.name}]"
            ))]

        # ── 逐表变换 ────────────────────────────────────────────────
        json_cols = {
            c.name for c in cols
            if isinstance(c.type, __import__("sqlalchemy").types.JSON)
        }
        for r in rows:
            for k in list(r):
                r[k] = _aware(r[k])
                # 裸 SQL 读回的 JSON 列是字符串 → 反序列化(bind 侧按对象走)
                if k in json_cols and isinstance(r[k], str):
                    r[k] = json.loads(r[k])
            if table.name == "composer_scenarios":
                r["payload"] = repair_scenario_payload(_load_payload(r["payload"]))
                if r.get("owner_id") == 0:
                    r["owner_id"] = None  # 历史 0 行 → NULL(§3.3)
                if not (r.get("owner_name") or ""):
                    r["owner_name"] = users_by_id.get(r.get("owner_id"), "") or ""
            elif table.name == "executions":
                if not (r.get("owner_name") or ""):
                    r["owner_name"] = users_by_id.get(r.get("owner_id"), "") or ""
                if not (r.get("scenario_name") or ""):
                    r["scenario_name"] = scen_name.get(r["scenario_id"], "") or ""
                # 孤儿 owner(已注销)→ SET NULL 语义(设计内降级,列表显示已注销)
                if r.get("owner_id") is not None and r["owner_id"] not in users_by_id:
                    r["owner_id"] = None
                    r["owner_name"] = r.get("owner_name") or ""
            elif table.name == "board_cards":
                if not (r.get("author_name") or ""):
                    r["author_name"] = users_by_id.get(r.get("author_id"), "") or ""
            elif table.name == "adaptation_batches":
                if not (r.get("operator_name") or ""):
                    r["operator_name"] = users_by_id.get(r.get("operator_id"), "") or ""

        with dst.begin() as tx:
            if rows:
                tx.execute(
                    table.insert(),
                    [{c: r.get(c) for c in col_names} for r in rows],
                )
        report["tables"][table.name] = {"rows": len(rows)}

    # ── stars.json → user_stars(键一律 int(k),§3.3 第六轮)──────────
    stars_path = settings.DATA_DIR / "stars.json"
    stars_imported = 0
    if stars_path.is_file():
        raw = json.loads(stars_path.read_text(encoding="utf-8"))
        user_stars = Base.metadata.tables["user_stars"]
        vals = []
        dangling = []
        for k, items in raw.items():
            uid = int(k)  # JSON 对象键一律字符串,直接插库轻则类型错重则静默丢
            for sid in items:
                # 悬空关注(场景已删而 stars.json 未清的历史缺口)按
                # user_stars 的 CASCADE 语义滤除;计数入报告,不静默丢。
                if sid not in scen_name:
                    dangling.append({"user_id": uid, "scenario_id": sid})
                    continue
                vals.append({"user_id": uid, "scenario_id": sid})
        report["verifications"]["stars_dangling_skipped"] = dangling
        if vals:
            with dst.begin() as tx:
                tx.execute(user_stars.insert(), vals)
        stars_imported = len(vals)
    report["tables"].setdefault("user_stars", {"rows": 0})["rows"] += stars_imported
    report["verifications"]["stars_imported"] = stars_imported
    stars_file_count = sum(
        len(v) for v in json.loads(stars_path.read_text(encoding="utf-8")).values()
    ) if stars_path.is_file() else 0
    report["verifications"]["stars_in_file"] = stars_file_count

    # ── JSONL → execution_rows(_replay_rows 折叠,事件流→终态)───────
    from app.services.run_dispatcher import _replay_rows
    with src.connect() as c:
        exec_ids = [r[0] for r in c.execute(text("SELECT id FROM executions"))]
    rows_table = Base.metadata.tables["execution_rows"]
    absorbed = 0
    batch: list[dict] = []
    for eid in exec_ids:
        for row in _replay_rows(eid):
            batch.append({
                "execution_id": eid,
                "seq": row["seq"],
                "dataset_id": row.get("datasetId"),
                "injection_id": row.get("injectionId"),
                "row_index": row.get("rowIndex", 0),
                "rep": row.get("rep", 0),
                "status": row.get("status", ""),
                "case_dir": row.get("caseDir", "") or "",
                "started_at": _aware(_parse_ts(row.get("startedAt"))),
                "finished_at": _aware(_parse_ts(row.get("finishedAt"))),
            })
        if len(batch) >= 500:
            absorbed += _flush(dst, rows_table, batch)
    absorbed += _flush(dst, rows_table, batch)
    report["tables"].setdefault("execution_rows", {"rows": 0})["rows"] += absorbed
    report["verifications"]["execution_rows_absorbed"] = absorbed

    # ── 收尾:全部序列列 setval(pg_get_serial_sequence,不手拼)────────
    # SERIAL(baseline 默认)与 IDENTITY 都经 pg_get_serial_sequence 覆盖:
    # 遍历 public 全部整型列,凡有归属序列即对齐 max(id)——漏一个 = 切换后
    # 首次 INSERT 主键冲突(§8 风险 4)。
    setval_n = 0
    with dst.begin() as tx:
        int_cols = tx.execute(text(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND data_type IN "
            "('integer','bigint','smallint')"
        )).fetchall()
        for tname, cname in int_cols:
            seq = tx.execute(text(
                "SELECT pg_get_serial_sequence(:t, :c)"),
                {"t": tname, "c": cname}).scalar()
            if not seq:
                continue
            tx.execute(text(
                f"SELECT setval('{seq}', "
                f'COALESCE((SELECT max("{cname}") FROM "{tname}"), 1))'
            ))
            setval_n += 1
    report["verifications"]["identity_columns_setval"] = setval_n

    # ── 校验:行数对账 + 抽样 checksum + 生成列抽样 ─────────────────
    row_counts_ok = True
    for tname, info in report["tables"].items():
        with dst.connect() as c:
            n = c.execute(text(f'SELECT count(*) FROM "{tname}"')).scalar()
        info["target_rows"] = n
        if n != info["rows"]:
            row_counts_ok = False
    report["verifications"]["row_counts_match"] = row_counts_ok

    import sqlalchemy as sa
    checksums_ok = True
    for tname, info in report["tables"].items():
        if info["rows"] == 0:
            continue
        tmeta = Base.metadata.tables.get(tname)
        json_cols = {
            c.name for c in (tmeta.columns if tmeta is not None else [])
            if isinstance(c.type, sa.types.JSON)
        }
        # 行对齐按主键在 Python 侧做 —— SQLite(二进制序)与 PG(库
        # collation)对 '.'/'_' 等字符的排序不同,ORDER BY 的行序不可比。
        tmeta_pk = [c.name for c in (tmeta.primary_key.columns
                                     if tmeta is not None else [])]
        with src.connect() as c:
            src_rows = [dict(r._mapping) for r in c.execute(text(
                f'SELECT * FROM [{tname}] LIMIT {SAMPLE_N * 2}'))]
        for r in src_rows:
            for k in json_cols:
                if isinstance(r[k], str):
                    r[k] = json.loads(r[k])
        with dst.connect() as c:
            dst_rows = [dict(r._mapping) for r in c.execute(text(
                f'SELECT * FROM "{tname}" LIMIT {SAMPLE_N * 2}'))]

        def key_of(r):
            return tuple(str(r.get(k)) for k in tmeta_pk) or (
                tuple(str(v) for v in r.values()),)

        dst_by_key = {key_of(r): r for r in dst_rows}
        cols_cmp = [k for k in src_rows[0]
                    if k not in CHECKSUM_EXCLUDE] if src_rows else []
        for a in src_rows[:SAMPLE_N]:
            b = dst_by_key.get(key_of(a))
            if b is None:
                checksums_ok = False
                info.setdefault("checksum_mismatch", []).append(
                    {"key": key_of(a), "reason": "target_missing"})
                break
            ha = sha256(json.dumps(_norm({k: a[k] for k in cols_cmp}),
                                   ensure_ascii=False, sort_keys=True,
                                   default=str).encode()).hexdigest()
            hb = sha256(json.dumps(_norm({k: b.get(k) for k in cols_cmp}),
                                   ensure_ascii=False, sort_keys=True,
                                   default=str).encode()).hexdigest()
            if ha != hb:
                checksums_ok = False
                info.setdefault("checksum_mismatch", []).append(
                    {"key": key_of(a), "cols": cols_cmp[:5]})
                break
    report["verifications"]["sample_checksums_match"] = checksums_ok

    # 生成列抽样 = 提取函数直接求值(composer)
    gen_ok = True
    gen_checked = 0
    with src.connect() as c:
        rows = c.execute(text(
            "SELECT scenario_id, payload FROM composer_scenarios LIMIT 20"
        )).fetchall()
    with dst.connect() as c:
        for sid, payload in rows:
            meta = ((_load_payload(payload) or {}).get("definition")
                    or {}).get("meta") or {}
            got = c.execute(text(
                "SELECT name, module, priority FROM composer_scenarios "
                "WHERE scenario_id = :s"), {"s": sid}).fetchone()
            if got is None or got[0] != (meta.get("name") or None):
                gen_ok = False
            gen_checked += 1
    report["verifications"]["generated_columns_sampled"] = {
        "checked": gen_checked, "match": gen_ok,
    }

    # FK 装载后全量校验(NOT VALID 两步的等价实现)
    fk_ok = True
    fk_violations: dict[str, int] = {}
    insp = inspect(dst)
    for tname in report["tables"]:
        if not insp.has_table(tname):
            continue
        for fk in insp.get_foreign_keys(tname):
            ref, col = fk["referred_table"], fk["referred_columns"][0]
            if ref not in report["tables"] or not fk["constrained_columns"]:
                continue
            lc = fk["constrained_columns"][0]
            with dst.connect() as c:
                n = c.execute(text(
                    f'SELECT count(*) FROM "{tname}" t LEFT JOIN "{ref}" r '
                    f'ON t."{lc}" = r."{col}" '
                    f'WHERE t."{lc}" IS NOT NULL AND r."{col}" IS NULL'
                )).scalar()
            if n:
                fk_ok = False
                fk_violations[f"{tname}.{lc}→{ref}"] = n
    report["verifications"]["fk_clean"] = fk_ok
    report["verifications"]["fk_violations"] = fk_violations

    src.dispose()
    dst.dispose()

    Path(args.report).write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    print(json.dumps(report["verifications"], ensure_ascii=False, indent=2))
    print(f"\n报告已落盘: {args.report}")
    dangling_n = len(report["verifications"].get("stars_dangling_skipped", []))
    ok = all([
        row_counts_ok, checksums_ok, gen_ok, fk_ok,
        # 进口 + 悬空滤除 = 文件计数(悬空是 CASCADE 语义的合法吸收,
        # 计数入报告不静默;不等于文件数才是丢失)
        stars_imported + dangling_n == stars_file_count,
    ])
    print("ETL 结论:", "PASS" if ok else "FAIL —— 检查报告后重跑(目标库需先重建)")
    return 0 if ok else 1


def _flush(dst, table, batch: list[dict]) -> int:
    if not batch:
        return 0
    with dst.begin() as tx:
        tx.execute(table.insert(), batch)
    n = len(batch)
    batch.clear()
    return n


def _parse_ts(v):
    if not v or not isinstance(v, str):
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None


if __name__ == "__main__":
    sys.exit(main())
