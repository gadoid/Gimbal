"""T6.3 verify:产物自检 —— 逐文件 import(pydantic 构造期即校验)
+ id/path 唯一性 + 信封断言;出 verify_report.json。

产物不入册(用户裁决),verify 只读产物目录,零写入。
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

# verify_emit.py → twin_generator → tools → gimbal-plate → src → repo 根
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "src" / "gimbal-plate"))

_RE_ID = re.compile(r"^fin\.[a-z0-9_]+\.[a-z0-9_]+$")
_ENVELOPE_NAMES = {"code", "msg", "data", "request_id", "retCode", "retMsg"}


def _spec_type():
    from gimbal_plate.schema.endpoint import EndpointSpec
    return EndpointSpec


def verify_dir(target: Path) -> dict:
    """target 下全部 *.py 逐个 import + 契约断言 → report dict。"""
    EndpointSpec = _spec_type()
    report: dict = {"files": 0, "ok": 0, "errors": []}
    seen_ids: dict[str, str] = {}      # id → 文件(撞车定位)
    seen_paths: dict[str, str] = {}
    for f in sorted(target.glob("*.py")):
        if f.name.startswith("_"):
            continue
        report["files"] += 1
        errs: list[str] = []
        try:
            spec = importlib.util.spec_from_file_location(
                f"verify_{f.stem}", f)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)      # pydantic 构造期即校验
        except Exception as e:                # noqa: BLE001 — 报告制,不中断
            report["errors"].append(
                {"file": f.name, "errors": [f"import 失败: {e}"]})
            continue
        eps = [v for v in vars(mod).values()
               if isinstance(v, EndpointSpec)]
        if not eps:
            report["errors"].append(
                {"file": f.name, "errors": ["无 EndpointSpec 常量"]})
            continue
        for ep in eps:
            if not _RE_ID.match(ep.id):
                errs.append(f"id 形态非法: {ep.id!r}")
            if ep.id in seen_ids:
                errs.append(f"id 重复: {ep.id}(与 {seen_ids[ep.id]})")
            seen_ids.setdefault(ep.id, f.name)
            if ep.api.path in seen_paths:
                errs.append(f"path 重复: {ep.api.path}"
                            f"(与 {seen_paths[ep.api.path]})")
            seen_paths.setdefault(ep.api.path, f.name)
            resp = ep.responses.get(200)
            if resp is None:
                errs.append("responses 缺 200")
            else:
                names = {d.name for d in resp.declarations}
                if not names <= _ENVELOPE_NAMES:
                    errs.append(f"信封键越界: {sorted(names - _ENVELOPE_NAMES)}")
                if "data" not in names:
                    errs.append("信封缺 data")
                if not all(d.assertable for d in resp.declarations):
                    errs.append("信封存在非 assertable 条目")
        if errs:
            report["errors"].append({"file": f.name, "errors": errs})
        else:
            report["ok"] += 1
    return report
