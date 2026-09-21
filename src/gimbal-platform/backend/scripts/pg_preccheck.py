"""pg_preccheck — SQLite 库切换前体检(PG迁移方案 §3.2,不改数据只出报告)。

跑法(backend 目录):
    python scripts/pg_preccheck.py [--db data/app.db] [--json out.json]

检查面:
 1. 类型亲和异常(Integer 列存 text 等 —— PG 侧会真报错,SQLite 无感)
 2. 变长列超长(保留的 VARCHAR(n) 短键对现网 max 长度)
 3. 孤儿行(FK 若真生效会被拒的行;executions.owner_id 孤儿**预期存在**,
    SET NULL 语义吸收)
 4. composer_scenarios.owner_id=0 批量清点(ETL 映射 NULL)
 5. display_name 重复(partial unique 会拒)
 6. payload 抽出面逐行校验(生成列把「脏数据读时修复」变「写入即拒」:
    meta.name 超 64 / priority 不可转换等会让 ETL 灌行当场炸)
 7. execution_rows 量级实测(JSONL 按 _replay_rows 折叠后的总行数 ——
    百万级则保留策略带参数上线)
 8. stars.json 计数与 int(k) 键(ETL 对账基线)
 9. 前置配置:JWT_SECRET / FERNET_KEY 非 ephemeral(跨库可解密前提)

报告人工过目后才允许 ETL(§3.2 的门禁)。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.db import Base  # noqa: E402
from app import models  # noqa: E402,F401
from app.core.config import settings  # noqa: E402


def typeof_check(engine, table_name: str, column: str, col_type) -> list[dict]:
    """SQLite typeof 与列声明类型不亲和的行(PG 会拒,SQLite 无感)。"""
    py_type = str(col_type).upper()
    if "INT" in py_type:
        good = ("integer", "null")
    elif "CHAR" in py_type or "TEXT" in py_type:
        good = ("text", "null", "integer", "real")  # 宽松:sqlite 数字也是合法文本
    elif "BOOL" in py_type:
        good = ("integer", "null")
    else:
        return []
    with engine.connect() as conn:
        rows = conn.execute(text(
            f"SELECT rowid, typeof([{column}]) AS t FROM [{table_name}] "
            f"WHERE typeof([{column}]) NOT IN "
            f"({','.join(repr(g) for g in good)})"
        )).fetchall()
    return [{"table": table_name, "column": column, "rowid": r[0], "typeof": r[1]}
            for r in rows]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(BACKEND_ROOT / "data" / "app.db"))
    ap.add_argument("--json", default=None, help="报告落盘路径(可选)")
    args = ap.parse_args()

    engine = create_engine(f"sqlite:///{args.db}")
    insp = inspect(engine)
    report: dict = {"source": args.db, "generated_at": datetime.now(timezone.utc).isoformat()}
    problems = 0

    # ── 1. 类型亲和 + 2. 变长列超长 ────────────────────────────────
    type_anomalies: list[dict] = []
    overlength: list[dict] = []
    with engine.connect() as c:
        for tname in Base.metadata.sorted_tables:
            if not insp.has_table(tname.name):
                continue
            for col in tname.columns:
                if col.computed is not None or col.primary_key:
                    continue
                type_anomalies.extend(
                    typeof_check(engine, tname.name, col.name, col.type))
                # 超长:VARCHAR(n) 的现网 max
                n = getattr(col.type, "length", None)
                if n:
                    row = c.execute(text(
                        f"SELECT max(length([{col.name}])) FROM [{tname.name}]"
                    )).scalar()
                    if row is not None and row > n:
                        overlength.append({
                            "table": tname.name, "column": col.name,
                            "max_len": row, "declared": n,
                        })
    report["type_anomalies"] = type_anomalies
    report["overlength"] = overlength
    problems += len(type_anomalies) + len(overlength)

    # ── 3. 孤儿行 + 4. owner_id=0 批 ───────────────────────────────
    orphans: dict[str, int] = {}
    with engine.connect() as c:
        checks = [
            ("executions.owner_id → users",  # 预期存在:SET NULL 吸收
             "SELECT count(*) FROM executions e LEFT JOIN users u "
             "ON e.owner_id = u.id WHERE e.owner_id IS NOT NULL AND u.id IS NULL"),
            ("composer_scenarios.owner_id=0(历史遗留,ETL 映射 NULL)",
             "SELECT count(*) FROM composer_scenarios WHERE owner_id = 0"),
            ("composer_scenarios.owner_id 孤儿",
             "SELECT count(*) FROM composer_scenarios s LEFT JOIN users u "
             "ON s.owner_id = u.id WHERE s.owner_id NOT IN (0) "
             "AND s.owner_id IS NOT NULL AND u.id IS NULL"),
            ("composer_data_sets.scenario_id 孤儿",
             "SELECT count(*) FROM composer_data_sets d LEFT JOIN "
             "composer_scenarios s ON d.scenario_id = s.scenario_id "
             "WHERE s.scenario_id IS NULL"),
            ("composer_run_schemes.scenario_id 孤儿",
             "SELECT count(*) FROM composer_run_schemes r LEFT JOIN "
             "composer_scenarios s ON r.scenario_id = s.scenario_id "
             "WHERE s.scenario_id IS NULL"),
            ("auth_sessions.owner_id 孤儿",
             "SELECT count(*) FROM auth_sessions a LEFT JOIN users u "
             "ON a.owner_id = u.id WHERE u.id IS NULL"),
            ("constant_entries.owner_id 孤儿",
             "SELECT count(*) FROM constant_entries k LEFT JOIN users u "
             "ON k.owner_id = u.id WHERE u.id IS NULL"),
            ("board_cards.author_id 孤儿",
             "SELECT count(*) FROM board_cards b LEFT JOIN users u "
             "ON b.author_id = u.id WHERE b.author_id IS NOT NULL AND u.id IS NULL"),
            ("service_aliases.owner_user_id 孤儿",
             "SELECT count(*) FROM service_aliases sa LEFT JOIN users u "
             "ON sa.owner_user_id = u.id WHERE sa.owner_user_id IS NOT NULL "
             "AND u.id IS NULL"),
            ("execution_snapshots.execution_id 孤儿",
             "SELECT count(*) FROM execution_snapshots es LEFT JOIN executions e "
             "ON es.execution_id = e.id WHERE e.id IS NULL"),
        ]
        for name, sql in checks:
            orphans[name] = c.execute(text(sql)).scalar() or 0
    report["orphans"] = orphans

    # ── 5. display_name 重复 ────────────────────────────────────────
    with engine.connect() as c:
        dup = c.execute(text(
            "SELECT display_name, count(*) n FROM users "
            "WHERE display_name <> '' GROUP BY display_name HAVING n > 1"
        )).fetchall()
    report["display_name_duplicates"] = [dict(r._mapping) for r in dup]
    problems += len(dup)

    # ── 6. payload 抽出面逐行校验(生成列写入即拒的面)────────────────
    from app.schemas.scenario_composer import ScenarioMeta
    meta_bad: list[dict] = []
    with engine.connect() as c:
        rows = c.execute(text(
            "SELECT scenario_id, payload FROM composer_scenarios"
        )).fetchall()
    for sid, payload in rows:
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                meta_bad.append({"scenario_id": sid,
                                 "error": "payload 不是合法 JSON"})
                continue
        meta = ((payload or {}).get("definition") or {}).get("meta") or {}
        try:
            ScenarioMeta.model_validate(meta)
        except Exception as e:  # noqa: BLE001
            meta_bad.append({"scenario_id": sid, "error": str(e)[:160]})
    report["payload_meta_invalid"] = meta_bad
    problems += len(meta_bad)

    # ── 7. execution_rows 量级实测(JSONL 折叠)──────────────────────
    from app.services.run_dispatcher import _replay_rows
    with engine.connect() as c:
        exec_ids = [r[0] for r in c.execute(text("SELECT id FROM executions"))]
    total_rows = 0
    per_exec_max = 0
    for eid in exec_ids:
        n = len(_replay_rows(eid))
        total_rows += n
        per_exec_max = max(per_exec_max, n)
    report["execution_rows"] = {
        "executions": len(exec_ids),
        "folded_total_rows": total_rows,
        "max_per_execution": per_exec_max,
        "retention_note": ("默认全保" if total_rows < 1_000_000
                           else "量级达百万级:上线即带保留参数(§2.2)"),
    }

    # ── 8. stars.json 计数与键型 ───────────────────────────────────
    stars_path = settings.DATA_DIR / "stars.json"
    stars_info: dict = {"path": str(stars_path)}
    if stars_path.is_file():
        raw = json.loads(stars_path.read_text(encoding="utf-8"))
        stars_info["users"] = len(raw)
        stars_info["total_marks"] = sum(len(v) for v in raw.values())
        stars_info["non_int_keys"] = [k for k in raw if not str(k).isdigit()]
    else:
        stars_info["missing"] = True
    report["stars_json"] = stars_info

    # ── 9. 前置配置(密钥)─────────────────────────────────────────
    report["config"] = {
        "jwt_secret_ephemeral": bool(settings.JWT_SECRET_EPHEMERAL),
        "fernet_key_ephemeral": bool(settings.FERNET_KEY_EPHEMERAL),
        "note": "两键必须已是固定配置(.env)—— 凭证密文跨库可解密的前提",
    }
    if settings.JWT_SECRET_EPHEMERAL or settings.FERNET_KEY_EPHEMERAL:
        problems += 1

    engine.dispose()

    # ── 输出 ────────────────────────────────────────────────────────
    report["blocking_problems"] = problems
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    if args.json:
        Path(args.json).write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8")
        print(f"\n报告已落盘: {args.json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
