"""M2 步骤 0 存量预检（M2 方案 v2.4 §8/§10；开发计划 T1.1）。

只读连接平台 PG，不写任何表。产出写入 --out 目录（缺省 ``gimbal-tmp/m2_step0/``）：

1. 场景定义的扩展/未知字段分布——对照 M4 白名单（view_hints / field_states /
   steps[].id / meta.scenarioId / meta.updateTime）与 M6 并入项（meta.system），
   白名单以外的未知字段逐项列出（步骤 0 要求「逐项定迁移规则」）；
2. ``scope: session`` 存量清单（Scope 取值级漂移：执行器已退役该值）；
3. 运行方案执行参数键清单 + ``nRuns``/``parallel`` 超 RunOptions 上限（64）的
   存量值（Q4 的决策数据）；
4. ``suites.mode_config`` 键清单、报告定义键清单、适配批次状态分布；
5. ``systems/`` 源树 ``gimbal:defaults`` 块清单（M2 §8 迁移项）;
6. 全量语料导出（场景定义 / 运行方案 / Suite）——T1.3 往返验收语料。

用法::

    python scripts/m2_step0_audit.py [--dsn DSN] [--out DIR]

DSN 缺省取 ``src/gimbal-platform/backend/.env`` 的 ``DATABASE_URL``（剥离
``+asyncpg``），再退回 ``postgresql://gimbal:gimbal@127.0.0.1:15432/gimbal``。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]

# ── 已知字段集：以执行器 schema 为基准（反转基准，M2 §3）──────────────
from gimbal.schema import (  # noqa: E402
    Assertion,
    Assign,
    Config as ExecConfig,
    Extract,
    Meta as ExecMeta,
    Request,
    Scenario as ExecScenario,
    Setup,
    Step as ExecStep,
)

KNOWN_TOP = set(ExecScenario.model_fields)
KNOWN_META = set(ExecMeta.model_fields)
KNOWN_CONFIG = set(ExecConfig.model_fields)
KNOWN_STEP = set(ExecStep.model_fields) | {"kind"}
KNOWN_REQUEST = set(Request.model_fields)
KNOWN_LIFECYCLE = set(Setup.model_fields)

_STRATEGY_BY_KIND = {
    cls.model_fields["kind"].default: cls  # type: ignore[index]
    for cls in (Extract, Assign, Assertion)
}
KNOWN_STRAT_COMMON = {"kind"}

# M4 白名单（已知平台扩展字段，迁移规则已定）+ M6 并入项
M4_WHITELIST = {"meta.scenarioId", "meta.updateTime", "steps[].field_states",
                "steps[].id", "steps[].call.view_hints"}
M6_MERGE = {"meta.system"}


def _default_dsn() -> str:
    env_file = _REPO / "src" / "gimbal-platform" / "backend" / ".env"
    if env_file.exists():
        m = re.search(r"^DATABASE_URL=(\S+)", env_file.read_text("utf-8"), re.M)
        if m:
            return m.group(1).replace("postgresql+asyncpg://", "postgresql://")
    return "postgresql://gimbal:gimbal@127.0.0.1:15432/gimbal"


def _bump(counter: Counter, key: str) -> None:
    counter[key] += 1


def _j(v: Any) -> Any:
    """asyncpg 对 JSON 列缺省返回 str——统一解码。"""
    if isinstance(v, str):
        try:
            return json.loads(v)
        except (TypeError, ValueError):
            return {}
    return v


def audit_definition(defn: Any, scenario_id: str, *,
                     unknown: Counter, m4: Counter, scope_session: list,
                     scope_values: Counter) -> None:
    """一个场景定义 → 字段分布 + scope 漂移。"""
    def _flag(path: str, known: set, data: dict) -> None:
        for k in data:
            full = f"{path}{k}"
            if full in M4_WHITELIST:
                _bump(m4, full)
            elif full in M6_MERGE or k in known:
                pass
            else:
                _bump(unknown, full)

    if not isinstance(defn, dict):
        return
    _flag("", KNOWN_TOP, defn)

    meta = defn.get("meta") or {}
    _flag("meta.", KNOWN_META, meta)
    config = defn.get("config") or {}
    _flag("config.", KNOWN_CONFIG, config)

    def _walk_scope(holder: Any, where: str) -> None:
        if not isinstance(holder, dict):
            return
        v = holder.get("scope")
        if v is not None:
            _bump(scope_values, str(v))
            if v == "session":
                scope_session.append(f"{scenario_id}:{where}")

    for entry in (config.get("setup") or []) + (config.get("teardown") or []):
        if isinstance(entry, dict):
            _flag("config.lifecycle.", KNOWN_LIFECYCLE, entry)
            _walk_scope(entry, f"lifecycle[{entry.get('kind')}]")

    for i, step in enumerate(defn.get("steps") or []):
        if not isinstance(step, dict):
            continue
        _flag(f"steps[{i}].", KNOWN_STEP, step)
        call = step.get("call") or {}
        if isinstance(call, dict) and "view_hints" in call:
            _bump(m4, "steps[].call.view_hints")  # Call 开放，只标记白名单项
        req = step.get("request") or {}
        if isinstance(req, dict):
            for k in req:
                if k not in KNOWN_REQUEST:
                    _bump(unknown, f"steps[{i}].request.{k}")
        for j, strat in enumerate(step.get("strategy") or []):
            if not isinstance(strat, dict):
                continue
            kind = strat.get("kind")
            model = _STRATEGY_BY_KIND.get(kind)
            known = (set(model.model_fields) if model else set()) | KNOWN_STRAT_COMMON
            for k in strat:
                if k not in known:
                    _bump(unknown, f"steps[{i}].strategy[{j}].{k}")
            _walk_scope(strat, f"steps[{i}].strategy[{j}]")


def audit_defaults_blocks() -> list[dict]:
    from gimbal_plate.dialect.parser import parse_markdown

    out: list[dict] = []
    for md in sorted((_REPO / "systems").rglob("*.md")):
        d = parse_markdown(md.read_text("utf-8"), source=str(md))
        for b in d.blocks("defaults"):
            out.append({
                "file": md.relative_to(_REPO).as_posix(),
                "line": b.line, "end_line": b.end_line, "review": b.review,
                "payload_keys": sorted(b.payload) if isinstance(b.payload, dict)
                else f"<list:{len(b.payload)}>",
            })
    return out


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dsn", default=_default_dsn())
    ap.add_argument("--out", default=str(_REPO / "gimbal-tmp" / "m2_step0"))
    args = ap.parse_args()
    out = Path(args.out)
    (out / "corpus" / "scenarios").mkdir(parents=True, exist_ok=True)
    (out / "corpus" / "run_schemes").mkdir(parents=True, exist_ok=True)
    (out / "corpus" / "suites").mkdir(parents=True, exist_ok=True)

    import asyncpg

    conn = await asyncpg.connect(args.dsn)
    report: dict[str, Any] = {}
    try:
        rows = await conn.fetch(
            "SELECT scenario_id, owner_name, visibility, payload "
            "FROM composer_scenarios ORDER BY id")
        unknown: Counter = Counter()
        m4: Counter = Counter()
        scope_session: list[str] = []
        scope_values: Counter = Counter()
        for r in rows:
            payload = _j(r["payload"]) or {}
            defn = payload.get("definition")
            audit_definition(defn, r["scenario_id"], unknown=unknown, m4=m4,
                             scope_session=scope_session,
                             scope_values=scope_values)
            (out / "corpus" / "scenarios" / f"{r['scenario_id']}.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=1),
                encoding="utf-8", newline="\n")
        report["scenarios"] = {
            "count": len(rows),
            "m4_whitelist_hits": dict(m4.most_common()),
            "unknown_fields": dict(unknown.most_common()),
            "scope_values": dict(scope_values.most_common()),
            "scope_session_list": scope_session,
        }

        schemes = await conn.fetch(
            "SELECT scheme_id, scenario_id, name, payload "
            "FROM composer_run_schemes ORDER BY id")
        keys: Counter = Counter()
        over_limit: list[dict] = []
        for r in schemes:
            p = _j(r["payload"]) or {}
            for k in p:
                _bump(keys, k)
            for k in ("nRuns", "parallel"):
                v = p.get(k)
                if isinstance(v, int) and v > 64:
                    over_limit.append({"scheme_id": r["scheme_id"], "key": k,
                                       "value": v})
            (out / "corpus" / "run_schemes" / f"{r['scheme_id']}.json").write_text(
                json.dumps(p, ensure_ascii=False, indent=1),
                encoding="utf-8", newline="\n")
        report["run_schemes"] = {
            "count": len(schemes), "payload_keys": dict(keys.most_common()),
            "over_runoptions_limit_gt64": over_limit,
        }

        suites = await conn.fetch(
            "SELECT id, name, mode, mode_config FROM suites ORDER BY id")
        mc_keys: Counter = Counter()
        for r in suites:
            for k in (_j(r["mode_config"]) or {}):
                _bump(mc_keys, k)
            (out / "corpus" / "suites" / f"{r['id']}.json").write_text(
                json.dumps({"name": r["name"], "mode": r["mode"],
                            "mode_config": _j(r["mode_config"])},
                           ensure_ascii=False, indent=1),
                encoding="utf-8", newline="\n")
        report["suites"] = {"count": len(suites),
                            "mode_config_keys": dict(mc_keys.most_common())}

        report["adaptation_batches"] = {
            str(s["status"]): s["n"] for s in await conn.fetch(
                "SELECT status, COUNT(*) AS n FROM adaptation_batches "
                "GROUP BY status")}
        report["adaptation_snapshots"] = await conn.fetchval(
            "SELECT COUNT(*) FROM adaptation_snapshots")

        # 本地库可能尚未建表（如 report_definitions）——按存在性容错
        existing = {
            r["table_name"] for r in await conn.fetch(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public'")}
        report["tables_present"] = sorted(existing)

        if "report_definitions" in existing:
            rd = await conn.fetch(
                "SELECT id, definition FROM report_definitions")
            rd_keys: Counter = Counter()
            for r in rd:
                for k in (_j(r["definition"]) or {}):
                    _bump(rd_keys, k)
            report["report_definitions"] = {
                "count": len(rd), "keys": dict(rd_keys.most_common())}
        else:
            report["report_definitions"] = {"count": None, "note": "表不存在（本地库未建）"}
    finally:
        await conn.close()

    report["gimbal_defaults_blocks"] = audit_defaults_blocks()
    (out / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1),
        encoding="utf-8", newline="\n")

    print(f"== M2 步骤 0 存量预检（语料与明细见 {out}）==")
    print(f"场景 {report['scenarios']['count']} | 运行方案 "
          f"{report['run_schemes']['count']} | Suite {report['suites']['count']}"
          f" | 报告定义 {report['report_definitions']['count']}")
    print(f"M4 白名单命中: {report['scenarios']['m4_whitelist_hits']}")
    print(f"白名单以外未知字段: {report['scenarios']['unknown_fields'] or '无'}")
    print(f"scope 取值分布: {report['scenarios']['scope_values'] or '无'}")
    print(f"scope:session 存量: {report['scenarios']['scope_session_list'] or '无'}")
    print(f"运行方案键分布: {report['run_schemes']['payload_keys']}")
    print(f"RunOptions 超限(>64): "
          f"{report['run_schemes']['over_runoptions_limit_gt64'] or '无'}")
    print(f"suite mode_config 键: {report['suites']['mode_config_keys']}")
    print(f"适配批次状态: {report['adaptation_batches']} | "
          f"快照 {report['adaptation_snapshots']} 行")
    print(f"gimbal:defaults 块: {len(report['gimbal_defaults_blocks'])} 个")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
