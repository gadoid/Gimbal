#!/usr/bin/env python
"""C13（P3-03）双链对账：同一配方在 legacy / server 两条执行链各跑一次，
逐字段对比单元状态、计数与事件量级。

用法（backend 目录）::

    python ../../scripts/reconcile_chain.py --scenario sc-xxx \
        [--dataset ds-1] [--injection inj-1] [--n-runs 1] [--timeout 600]

前提：
* 后端 DB 可达（复用 backend 的 SessionLocal / settings）；
* plate / gimbal 引擎可用（server 链会真实拉起 ``gimbal run server``）；
* 场景归属某平台用户 —— 用 --owner 指定该用户的用户名（默认第一个用户）。

输出：JSON 报告（verdict=match|mismatch + 逐字段差异），退出码
0=一致 / 1=不一致 / 2=执行失败。灰度回滚路径 = EXEC_CHAIN 开关关闭
（legacy），与本脚本无关。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "src" / "gimbal-platform" / "backend"
sys.path.insert(0, str(_BACKEND))


async def _dispatch(chain: str, args, user_id: int) -> int:
    from app.core import db as db_module
    from app.schemas.scenario_composer import RunRequest
    from app.services import run_dispatcher

    req = RunRequest(
        scenarioId=args.scenario,
        dataSetIds=args.dataset or [],
        injectionEntryIds=args.injection or [],
        nRuns=args.n_runs,
    )
    async with db_module.SessionLocal() as session:
        resp = await run_dispatcher.dispatch_run(
            session, user_id, req, chain_override=chain)
        await session.commit()
    return resp.execution_id


async def _wait_final(execution_id: int, timeout_s: float) -> dict | None:
    from sqlalchemy import select
    from app.core import db as db_module
    from app.models.execution import Execution

    import time
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        async with db_module.SessionLocal() as session:
            ex = (await session.execute(
                select(Execution).where(Execution.id == execution_id)
            )).scalar_one_or_none()
            if ex is not None and ex.status in ("done", "failed", "canceled"):
                return {
                    "status": ex.status, "total": ex.total_runs,
                    "passed": ex.passed, "failed": ex.failed,
                    "skipped": ex.skipped,
                }
        await asyncio.sleep(1.0)
    return None


async def _rows(execution_id: int) -> list[dict]:
    from sqlalchemy import select
    from app.core import db as db_module
    from app.models.execution import ExecutionRow

    async with db_module.SessionLocal() as session:
        rows = (await session.execute(
            select(ExecutionRow)
            .where(ExecutionRow.execution_id == execution_id)
            .order_by(ExecutionRow.seq))).scalars().all()
        return [{"unit": r.unit_id, "status": r.status,
                 "attempts": r.attempts} for r in rows]


async def _event_counts(execution_id: int) -> dict:
    from sqlalchemy import select, func
    from app.core import db as db_module
    from app.models.execution import ExecutionEvent

    async with db_module.SessionLocal() as session:
        rows = (await session.execute(
            select(ExecutionEvent.event_type, func.count())
            .where(ExecutionEvent.execution_id == execution_id)
            .group_by(ExecutionEvent.event_type))).all()
        return {et: n for et, n in rows}


def _diff(a: dict, b: dict, path: str = "", out: list | None = None) -> list:
    out = out if out is not None else []
    keys = set(a) | set(b)
    for k in sorted(keys):
        va, vb = a.get(k, "<absent>"), b.get(k, "<absent>")
        if isinstance(va, dict) and isinstance(vb, dict):
            _diff(va, vb, f"{path}{k}.", out)
        elif va != vb:
            out.append(f"{path}{k}: legacy={va!r} server={vb!r}")
    return out


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--dataset", action="append", default=[])
    ap.add_argument("--injection", action="append", default=[])
    ap.add_argument("--n-runs", type=int, default=1)
    ap.add_argument("--timeout", type=float, default=600.0)
    ap.add_argument("--owner", default=None, help="场景归属用户名（默认第一个用户）")
    args = ap.parse_args()

    from app.core import db as db_module
    from app.models.user import User
    from sqlalchemy import select

    from app.core.db import init_db
    await init_db()

    async with db_module.SessionLocal() as session:
        q = select(User)
        if args.owner:
            q = q.where(User.username == args.owner)
        user = (await session.execute(q.order_by(User.id))).scalars().first()
        if user is None:
            print("owner user not found", file=sys.stderr)
            return 2
        user_id = user.id

    print("dispatch legacy ...")
    eid_legacy = await _dispatch("legacy", args, user_id)
    print("dispatch server ...")
    eid_server = await _dispatch("server", args, user_id)

    summary_l = await _wait_final(eid_legacy, args.timeout)
    summary_s = await _wait_final(eid_server, args.timeout)
    report: dict = {"legacy": {"executionId": eid_legacy, "summary": summary_l},
                    "server": {"executionId": eid_server, "summary": summary_s}}
    if summary_l is None or summary_s is None:
        report["verdict"] = "timeout"
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    rows_l, rows_s = await _rows(eid_legacy), await _rows(eid_server)
    ev_l, ev_s = await _event_counts(eid_legacy), await _event_counts(eid_server)
    report["legacy"].update(rows=rows_l, events=ev_l)
    report["server"].update(rows=rows_s, events=ev_s)

    diffs = _diff({"summary": summary_l, "rows": rows_l},
                  {"summary": summary_s, "rows": rows_s})
    # 事件量级：类型集合一致 + 每类型数量同量级（server 链多 run.meta 等
    # 会话事件,允许 ≤3 的类型差;同类型数量差 >20% 记差异）
    types_l, types_s = set(ev_l), set(ev_s)
    if types_l - types_s or types_s - types_l:
        diffs.append(f"event types: legacy-only={sorted(types_l - types_s)} "
                     f"server-only={sorted(types_s - types_l)}")
    for t in types_l & types_s:
        a, b = ev_l[t], ev_s[t]
        if max(a, b) and abs(a - b) / max(a, b) > 0.2:
            diffs.append(f"events[{t}]: legacy={a} server={b}")

    report["diffs"] = diffs
    report["verdict"] = "match" if not diffs else "mismatch"
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not diffs else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
