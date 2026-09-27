# -*- coding: utf-8 -*-
"""对账脚本：同场景新旧链（-o json vs -o jsonl）执行结果逐字段一致（v2.1 §4.4 验收门）。

用法: python scripts/reconcile.py [--count N] [--timeout T]
输出: 对账报告（逐 case 逐字段 diff + 汇总结论）
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "src" / "gimbal-platform" / "backend"))

from app.services.gimbal_launcher import parse_run_result  # noqa: E402


def run_gimbal(case_path: str, output_format: str, timeout: float = 60) -> dict:
    """跑一次 gimbal run launch，返回 {exit_code, parsed, stdout_tail}。"""
    env = dict(os.environ, PYTHONPATH=str(REPO / "src"))
    try:
        r = subprocess.run(
            [sys.executable, "-m", "gimbal.cli.main", "run", "launch",
             case_path, "-o", output_format, "--log-level", "error"],
            capture_output=True, text=True, env=env, timeout=timeout,
        )
        parsed = parse_run_result(r.stdout or "")
        return {"exit_code": r.returncode, "parsed": parsed,
                "stdout_tail": (r.stdout or "")[-200:]}
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "parsed": None, "stdout_tail": "TIMEOUT"}
    except Exception as exc:
        return {"exit_code": -2, "parsed": None, "stdout_tail": str(exc)[:200]}


def compare_verdicts(old: dict | None, new: dict | None) -> list[str]:
    """逐字段 diff；返回差异列表（空 = 一致）。"""
    if old is None and new is None:
        return []
    if old is None or new is None:
        return [f"一方解析失败: old={'有' if old else 'None'} new={'有' if new else 'None'}"]
    diffs = []
    for key in ("exit_code", "total", "passed", "failed", "skipped"):
        if old.get(key) != new.get(key):
            diffs.append(f"{key}: old={old.get(key)} new={new.get(key)}")
    # details 结构对齐（scenario_id + status）
    old_details = {(d.get("scenario_id"), d.get("status")) for d in old.get("details", [])}
    new_details = {(d.get("scenario_id"), d.get("status")) for d in new.get("details", [])}
    if old_details != new_details:
        diffs.append(f"details 不一致: old={sorted(old_details)} new={sorted(new_details)}")
    return diffs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--count", type=int, default=10, help="对账 case 数量")
    parser.add_argument("--timeout", type=float, default=60, help="单次执行超时")
    parser.add_argument("--report", type=Path, help="报告写入路径")
    args = parser.parse_args()

    # ── 对账集：本地 HTTP 正向场景 + 平台已迁移的存量 case ──
    cases = []

    # 正向场景：本地 HTTP（构造一个必然 pass 的 case）
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"code": 0}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *a): pass

    server = HTTPServer(("127.0.0.1", 18901), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    positive_case = REPO / "gimbal-tmp" / "_recon_positive.json"
    meta = {"name": "t", "description": "d", "module": "m", "priority": 1,
            "author": "a", "owner": "o", "tags": [], "version": "1.0",
            "createTime": "2026-09-27T00:00:00Z", "expire": False, "requirementRef": []}
    positive_case.write_text(json.dumps({
        "kind": "scenario", "scenarioId": "recon-positive", "meta": meta,
        "config": {"services": {"svc": "http://127.0.0.1:18901"}},
        "resource": {},
        "steps": [{"kind": "step",
                   "call": {"kind": "call", "protocol": "http", "service": "svc",
                            "method": "GET", "path": "/health"},
                   "request": {"kind": "request", "body": {}},
                   "strategy": [{"kind": "assertion", "name": "a",
                                 "target": "$.call.response.status",
                                 "operator": "eq", "expected": 200}]}],
    }, ensure_ascii=False), encoding="utf-8")
    cases.append(("正向(本地HTTP)", str(positive_case)))

    # 负向场景：本地 HTTP 断言失败
    negative_case = REPO / "gimbal-tmp" / "_recon_negative.json"
    negative_case.write_text(json.dumps({
        "kind": "scenario", "scenarioId": "recon-negative", "meta": meta,
        "config": {"services": {"svc": "http://127.0.0.1:18901"}},
        "resource": {},
        "steps": [{"kind": "step",
                   "call": {"kind": "call", "protocol": "http", "service": "svc",
                            "method": "GET", "path": "/health"},
                   "request": {"kind": "request", "body": {}},
                   "strategy": [{"kind": "assertion", "name": "a",
                                 "target": "$.call.response.status",
                                 "operator": "eq", "expected": 500}]}],
    }, ensure_ascii=False), encoding="utf-8")
    cases.append(("负向(断言失败)", str(negative_case)))

    # 连接失败场景
    unreachable = REPO / "gimbal-tmp" / "_recon_unreachable.json"
    unreachable.write_text(json.dumps({
        "kind": "scenario", "scenarioId": "recon-unreachable", "meta": meta,
        "config": {"services": {"dead": "http://127.0.0.1:19999"}},
        "resource": {},
        "steps": [{"kind": "step",
                   "call": {"kind": "call", "protocol": "http", "service": "dead",
                            "method": "GET", "path": "/x"},
                   "request": {"kind": "request", "body": {}},
                   "strategy": []}],
    }, ensure_ascii=False), encoding="utf-8")
    cases.append(("连接失败", str(unreachable)))

    # 存量已迁移 case（两类：平台 data/runs + gimbal-tmp 语料）
    # 平台侧：有 .bak 的 = 被脚本写入过的 = 合法 case
    platform_bak = sorted(glob.glob(str(REPO / "src" / "gimbal-platform" / "backend" /
                                         "data" / "runs" / "cases" / "**" / "case.json.bak"),
                                    recursive=True))
    for p in platform_bak[:max(0, args.count // 2)]:
        cases.append(("平台存量", p.replace(".bak", "")))

    # gimbal-tmp 语料（已全部迁移为 call 形态的合法 case）
    tmp_cases = sorted(glob.glob(str(REPO / "gimbal-tmp" / "*.json")))
    tmp_cases = [p for p in tmp_cases if not p.endswith(".bak")]
    # 用 RunUnion 校验过滤出合法 case
    from pydantic import TypeAdapter
    from gimbal.schema.scenario import RunUnion
    ta = TypeAdapter(RunUnion)
    valid_tmp = []
    for p in tmp_cases:
        try:
            ta.validate_python(json.load(open(p, encoding="utf-8")))
            valid_tmp.append(p)
        except Exception:
            pass
    step = max(1, len(valid_tmp) // max(1, args.count - 3 - len(platform_bak)))
    for p in valid_tmp[::step][:max(0, args.count - 3 - len(platform_bak))]:
        cases.append(("tmp语料", p))

    # ── 对账执行 ──
    results = []
    all_match = True
    for label, path in cases:
        old = run_gimbal(path, "json", args.timeout)
        new = run_gimbal(path, "jsonl", args.timeout)
        diffs = compare_verdicts(old["parsed"], new["parsed"])
        match = not diffs and old["exit_code"] == new["exit_code"]
        if not match:
            all_match = False
        results.append({
            "label": label, "file": Path(path).name,
            "old_exit": old["exit_code"], "new_exit": new["exit_code"],
            "old_verdict": old["parsed"], "new_verdict": new["parsed"],
            "diffs": diffs, "match": match,
        })
        status = "✅" if match else "❌ " + "; ".join(diffs)
        o, n = old["parsed"] or {}, new["parsed"] or {}
        print(f"  {status} {label:12s} {Path(path).name[:30]:30s} "
              f"old={o.get('exit_code','?')}/{o.get('total','?')}/{o.get('passed','?')} "
              f"new={n.get('exit_code','?')}/{n.get('total','?')}/{n.get('passed','?')}")

    # 清理
    for f in (positive_case, negative_case, unreachable):
        f.unlink(missing_ok=True)
    server.shutdown()

    # ── 汇总 ──
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total": len(results),
        "matched": sum(1 for r in results if r["match"]),
        "mismatched": sum(1 for r in results if not r["match"]),
        "all_match": all_match,
        "results": results,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
        print(f"\nreport → {args.report}")

    print(f"\n[对账] total={report['total']} matched={report['matched']} "
          f"mismatched={report['mismatched']} → {'✅ 全部一致' if all_match else '❌ 存在差异'}")
    return 0 if all_match else 1


if __name__ == "__main__":
    raise SystemExit(main())
