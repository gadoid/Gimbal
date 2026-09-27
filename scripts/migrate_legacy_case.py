#!/usr/bin/env python
"""迁移脚本：存量 case 旧形式 → v2.1 新形式（批次 F 正式执行；本脚本先行干跑）。

迁移内容（幂等，可重复执行）：
  1. step ``api`` 语法糖 → ``call: {protocol: "http", ...}``（删除 api 键）；
  2. 策略字段中的旧 scratch 路径 → call 信封路径（边界安全：仅匹配
     键名后跟 ``.`` / ``[`` / 串尾）：
       $.response_body    → $.call.response.body
       $.response_status  → $.call.response.status
       $.response_headers → $.call.response.meta.headers
       $.request_body     → $.call.request.body
       $.request_method   → $.call.request.method
       $.request_url      → $.call.request.url
       $.request_headers  → $.call.request.headers
       $.duration_ms      → $.call.elapsed_ms
  3. setup/teardown 非空 → 记 warning（LifecycleEntry 随批次 F 生命周期插槽
     落地，当前保留原样）。

支持 Scenario / Suite（嵌入式）/ Graph 三种形态递归迁移；非 RunUnion 文件
跳过并报告。平台存储的 case.json 用 ``migrate_payload``（同一入口）。

用法：
    python scripts/migrate_legacy_case.py <file|dir>... [--write] [--out DIR] [--report FILE]

默认干跑（不写文件）；--write 原地改写（.bak 备份）；--out 写到目录。
验收：干跑两轮报告逐字节一致（幂等）+ 迁移产物可过 RunUnion 校验。
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

PATH_REWRITES: dict[str, str] = {
    "$.response_body": "$.call.response.body",
    "$.response_status": "$.call.response.status",
    "$.response_headers": "$.call.response.meta.headers",
    "$.request_body": "$.call.request.body",
    "$.request_method": "$.call.request.method",
    "$.request_url": "$.call.request.url",
    "$.request_headers": "$.call.request.headers",
    "$.duration_ms": "$.call.elapsed_ms",
}

# 边界安全：键名后必须跟 . [ 或串尾（$.response_bodyx 不匹配）
_RE = re.compile(
    r"\$\.(response_body|response_status|response_headers|request_body|"
    r"request_method|request_url|request_headers|duration_ms)(?=[.\[]|$)"
)


@dataclass
class MigrateResult:
    """一次迁移的结果（结构化，供报告与幂等校验）。"""
    changes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def change_count(self) -> int:
        return len(self.changes)


def _rewrite_paths_in_strings(node: Any, result: MigrateResult, where: str) -> Any:
    """递归重写字符串值中的旧路径（仅策略面：expression/target/source 等）。"""
    if isinstance(node, str):
        def _sub(m: re.Match) -> str:
            old = "$." + m.group(1)
            new = PATH_REWRITES[old]
            result.changes.append(f"{where}: {old} → {new}")
            return new
        return _RE.sub(_sub, node)
    if isinstance(node, dict):
        return {k: _rewrite_paths_in_strings(v, result, where) for k, v in node.items()}
    if isinstance(node, list):
        return [_rewrite_paths_in_strings(v, result, where) for v in node]
    return node


def _migrate_step(step: dict, result: MigrateResult, where: str) -> dict:
    if not isinstance(step, dict):
        return step
    out = dict(step)
    # 1. api 糖 → call
    api = out.get("api")
    if api is not None and out.get("call") is None:
        fields = {k: v for k, v in api.items() if k != "kind"}
        out["call"] = {"kind": "call", "protocol": "http", **fields}
        del out["api"]
        result.changes.append(f"{where}: api → call(protocol=http)")
    # 2. 策略面路径重写
    if "strategy" in out:
        out["strategy"] = _rewrite_paths_in_strings(out["strategy"], result, where)
    return out


def _migrate_scenario(scenario: dict, result: MigrateResult, where: str) -> dict:
    if not isinstance(scenario, dict):
        return scenario
    out = dict(scenario)
    if "steps" in out:
        out["steps"] = [
            _migrate_step(s, result, f"{where}.steps[{i}]")
            for i, s in enumerate(out["steps"] or [])
        ]
    config = out.get("config")
    if isinstance(config, dict):
        for key in ("setup", "teardown"):
            if config.get(key):
                result.warnings.append(
                    f"{where}.config.{key} 非空：LifecycleEntry 迁移随批次 F "
                    f"生命周期插槽落地，当前保留原样（{len(config[key])} 条）"
                )
    return out


def migrate_payload(payload: dict) -> tuple[dict, MigrateResult]:
    """迁移一个 RunUnion dict（Scenario/Suite/Graph）。幂等；不改入参。"""
    result = MigrateResult()
    out = copy.deepcopy(payload)
    kind = out.get("kind")
    if kind == "scenario":
        out = _migrate_scenario(out, result, "scenario")
    elif kind == "suite":
        # v2.1 批次 F-2b：嵌入式 Suite schema 已删除 → desugar 为 graph aggregate
        suite = out.get("suite") or []
        migrated = [
            _migrate_scenario(s, result, f"suite[{i}]") for i, s in enumerate(suite)
        ]
        execution = out.get("execution") or {}
        out = {
            "kind": "graph",
            "mode": "aggregate",
            "units": [{"ref": s.get("scenarioId") or f"u{i}", "scenario": s}
                      for i, s in enumerate(migrated)],
            "policy": ({"parallel": execution.get("maxWorkers", 4),
                        "fail_fast": execution.get("failFast")}
                       if execution.get("parallel") else {}),
        }
        if not out["units"]:
            result.warnings.append("suite.suite 为空：迁移为空 units 的 graph（编译会报错）")
        result.changes.append("kind=suite → kind=graph(aggregate)")
    elif kind == "graph":
        for section in ("before", "units", "after"):
            decls = out.get(section) or []
            for i, d in enumerate(decls):
                if isinstance(d, dict) and "scenario" in d:
                    d["scenario"] = _migrate_scenario(
                        d["scenario"], result, f"graph.{section}[{i}].scenario")
        # graph 的 execution/needs/inputs 不含旧路径
    else:
        result.warnings.append(f"未知 kind={kind!r}，原样返回")
    return out, result


def validate_payload(payload: dict) -> Optional[str]:
    """迁移产物可过 RunUnion 校验；失败返回错误描述。"""
    try:
        from pydantic import TypeAdapter
        from gimbal.schema.scenario import RunUnion
        TypeAdapter(RunUnion).validate_python(payload)
        return None
    except Exception as exc:  # noqa: BLE001
        return str(exc)[:300]


# ── 文件批处理与报告 ─────────────────────────────────────────

def iter_case_files(paths: list[str]):
    for p in paths:
        path = Path(p)
        if path.is_dir():
            for f in sorted(path.rglob("*.json")):
                yield f
        else:
            yield path


def migrate_file(path: Path, *, write: bool, out_dir: Optional[Path]) -> dict:
    """单文件迁移（默认干跑）。返回报告条目。"""
    entry: dict = {"file": str(path)}
    try:
        raw = path.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        entry.update(status="skipped", reason=f"unreadable/not-json: {exc}")
        return entry
    if not isinstance(payload, dict) or "kind" not in payload:
        entry.update(status="skipped", reason="no-kind (not a RunUnion case)")
        return entry
    if payload.get("kind") not in ("scenario", "suite", "graph"):
        entry.update(status="skipped",
                     reason=f"kind={payload.get('kind')!r} 非 gimbal RunUnion（平台侧格式）")
        return entry

    migrated, result = migrate_payload(payload)
    err = validate_payload(migrated)
    # 幂等自检：迁移产物再迁移一遍应零变更
    _, second = migrate_payload(migrated)
    idempotent = second.change_count == 0

    entry.update(
        status="ok" if err is None else "invalid",
        kind=payload.get("kind"),
        changes=result.change_count,
        change_samples=result.changes[:5],
        warnings=result.warnings,
        idempotent=idempotent,
        valid_after=err is None,
        validation_error=err,
    )
    if err is None and write and result.change_count > 0:
        bak = path.with_suffix(path.suffix + ".bak")
        bak.write_text(raw, encoding="utf-8")
        path.write_text(json.dumps(migrated, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        entry["written"] = str(path)
        entry["backup"] = str(bak)
    elif err is None and out_dir is not None and result.change_count > 0:
        target = out_dir / path.name
        target.write_text(json.dumps(migrated, ensure_ascii=False, indent=2),
                          encoding="utf-8")
        entry["written"] = str(target)
    return entry


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="+", help="case 文件或目录")
    parser.add_argument("--write", action="store_true", help="原地改写（.bak 备份）")
    parser.add_argument("--out", type=Path, help="迁移产物写到该目录（不改原文件）")
    parser.add_argument("--report", type=Path, help="报告 JSON 写入路径（默认 stdout）")
    args = parser.parse_args(argv)

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)

    entries = [migrate_file(f, write=args.write, out_dir=args.out)
               for f in iter_case_files(args.paths)]
    report = {
        "total": len(entries),
        "migrated": sum(1 for e in entries if e.get("changes", 0) > 0),
        "skipped": sum(1 for e in entries if e.get("status") == "skipped"),
        "invalid": sum(1 for e in entries if e.get("status") == "invalid"),
        "non_idempotent": sum(1 for e in entries if not e.get("idempotent", True)),
        "mode": "write" if args.write else ("out" if args.out else "dry-run"),
        "entries": entries,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
        print(f"report → {args.report}")
    else:
        print(text)

    ok = report["invalid"] == 0 and report["non_idempotent"] == 0
    print(f"[summary] total={report['total']} migrated={report['migrated']} "
          f"skipped={report['skipped']} invalid={report['invalid']} "
          f"non_idempotent={report['non_idempotent']}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
