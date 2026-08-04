"""gimbal-tmp/_normalize_paths.py

外层归一脚本 —— 把 endpoint 定义 / scenario JSON 里 IOFieldBinding.path 的
"短名"形态统一收敛为 JSONPath 形态（$.xxx）。

不修改 plate 源码（在 gimbal-tmp 中运行），通过直接读取 endpoint 模块 + 调用
utils/path.py::normalize 实现统一。运行后在 stdout 打印每个被改写的位置。

用法:
    python _normalize_paths.py <endpoint_module> [--write]

其中 <endpoint_module> 是 endpoint 定义所在模块路径,如:
    python _normalize_paths.py systems.tidb.endpoints --write
"""
from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path
from typing import Any

# 把 src 加入 sys.path,确保能 import plate
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gimbal_plate.utils.path import is_valid_path, normalize, last_segment  # noqa: E402


def _needs_normalize(path: str) -> bool:
    """判断 path 是否仍处于短名形态(需要归一)。"""
    return isinstance(path, str) and is_valid_path(path) and not path.startswith("$")


def normalize_iobinding(io: dict[str, Any]) -> tuple[str, str] | None:
    """对单个 IOFieldBinding dict 归一;返回 (old, new) 或 None(无需改)。"""
    p = io.get("path")
    if not _needs_normalize(p):
        return None
    new = normalize(p)
    # 一致性兜底:name 与末段应一致;不一致时拒绝改写,以免破坏 schema 校验
    seg = last_segment(new)
    if seg is not None and io.get("name") != seg:
        return None
    return (p, new)


def normalize_endpoint_dict(ep: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    """对单个 endpoint dict 归一所有 IOFieldBinding.path。
    返回 [(location, old, new, name), ...] 列表。
    """
    diffs: list[tuple[str, str, str, str]] = []
    req = ep.get("request") or {}
    for f in req.get("fields", []) or []:
        d = normalize_iobinding(f)
        if d:
            diffs.append(("request", d[0], d[1], str(f.get("name"))))
            f["path"] = d[1]
    for status, resp in (ep.get("responses") or {}).items():
        for f in resp.get("fields", []) or []:
            d = normalize_iobinding(f)
            if d:
                diffs.append((f"response[{status}]", d[0], d[1], str(f.get("name"))))
                f["path"] = d[1]
    return diffs


def normalize_endpoint_module(module_path: str, *, write: bool) -> int:
    """加载指定模块,扫描其导出的 EndpointSpec 列表并归一。"""
    mod = importlib.import_module(module_path)
    # 约定:模块需暴露 ENDPOINTS 或 endpoints 列表
    eps = getattr(mod, "ENDPOINTS", None) or getattr(mod, "endpoints", None)
    if not eps:
        print(f"[!] 模块 {module_path!r} 未导出 ENDPOINTS / endpoints", file=sys.stderr)
        return 1

    total = 0
    for ep in eps:
        # 兼容 dict / pydantic 对象两种形态
        if hasattr(ep, "model_dump"):
            ep_dict = ep.model_dump()
        else:
            ep_dict = ep
        diffs = normalize_endpoint_dict(ep_dict)
        for loc, old, new, name in diffs:
            print(f"  [{ep_dict.get('id', '?')}] {loc}.{name}: {old!r} -> {new!r}")
            total += 1
        if diffs and write and hasattr(ep, "model_validate"):
            new_ep = type(ep).model_validate(ep_dict)
            # 用同模块同名属性替换(对 list 元素需原地 mutate)
            try:
                idx = eps.index(ep)
                eps[idx] = new_ep
            except ValueError:
                pass

    print(f"[i] 共归一 {total} 个 IOFieldBinding.path")
    return 0 if total >= 0 else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="归一 IOFieldBinding.path 的短名为 JSONPath")
    p.add_argument("module", help="endpoint 定义所在 Python 模块路径")
    p.add_argument("--write", action="store_true",
                   help="原地改写(否则只 diff,不修改)")
    args = p.parse_args(argv)
    return normalize_endpoint_module(args.module, write=args.write)


if __name__ == "__main__":
    raise SystemExit(main())