"""冷化判定查询（Release v4.4 §9 / 开发计划 T5.2）。

冷化 = 把不再被引用的修订移出 plate 进程的可装载范围（构件分支检出中的
归档目录），manifest 保留在构件分支历史中。本模块只做**判定查询**（R10），
不执行移动。

「仍被引用」（不出现在冷化清单中）：
1. 被任一场景（含已归档场景）的 ``meta.plate`` 引用（已验证修订本身）
2. 位于这些已验证修订与其版本线最新修订**之间**（可能成为生效修订，
   D-5 可用集合语义——中间修订可能因结构「改了又改回」而成为生效修订）
3. 被未清理的执行记录的 ``plate_pins`` 引用
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gimbal_plate.release.release import latest_revision_manifest
from gimbal_plate.release.read import list_lines


def list_cold_archivable(
    artifacts_root: Path,
    *,
    referenced_revisions: dict[str, list[str]],
    pinned_revisions: dict[str, list[str]],
) -> list[dict[str, Any]]:
    """列出可冷化的修订。

    Args:
        artifacts_root: 构件根（构件分支检出或本地演练目录）。
        referenced_revisions: 各系统的**已验证修订**列表
           （``{系统: ["<line>#<n>", ...]}``，来自场景 meta.plate）。
        pinned_revisions: 各系统的**执行记录钉住**修订列表
           （``{系统: ["<line>#<n>", ...]}``，来自 executions.plate_pins）。

    Returns:
        冷化候选列表（按系统分组，含各修订的 manifest 摘要）。
    """
    # 1. 构建受保护修订集合（含「之间」的闭包）
    protected: dict[str, set[int]] = {}   # 系统 → 受保护的修订号集合

    for system, refs in referenced_revisions.items():
        for ref in refs:
            kind, line, n = _parse(ref)
            if kind != "revision":
                continue
            # a) 已验证修订本身
            protected.setdefault(f"{line}", set()).add(n)
            # b) 从已验证到最新的全部中间修订（可能成为生效修订）
            latest = latest_revision_manifest(artifacts_root, system, line)
            if latest:
                for mid in range(n, latest[0] + 1):
                    protected.setdefault(f"{line}", set()).add(mid)

    for system, refs in pinned_revisions.items():
        for ref in refs:
            kind, line, n = _parse(ref)
            if kind != "revision":
                continue
            protected.setdefault(f"{line}", set()).add(n)

    # 2. 扫描全部修订，排除受保护的
    out: list[dict[str, Any]] = []
    for system_dir in sorted(artifacts_root.iterdir()):
        if not system_dir.is_dir() or system_dir.name == "objects":
            continue
        system = system_dir.name
        lines_info = list_lines(artifacts_root, system)
        for line_info in lines_info:
            line = line_info["line"]
            line_dir = system_dir / "lines" / line
            if not line_dir.is_dir():
                continue
            for rev_dir in sorted(line_dir.iterdir()):
                if not (rev_dir.is_dir() and rev_dir.name.isdigit()):
                    continue
                n = int(rev_dir.name)
                if n in protected.get(line, set()):
                    continue
                manifest_path = rev_dir / "manifest.json"
                if not manifest_path.is_file():
                    continue
                try:
                    m = json.loads(manifest_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                out.append({
                    "system": system,
                    "revision": f"{line}#{n}",
                    "released_at": m.get("released_at", ""),
                    "signed_by": m.get("signed_by", ""),
                    "summary": m.get("summary", {}),
                    "corrections": m.get("corrections", []),
                })
    return out


def _parse(ref: str) -> tuple[str, str | None, int | None]:
    """ref 解析（轻量——不引入 read.parse_ref 的异常语义）。"""
    ref = (ref or "").strip()
    if not ref or ref == "working":
        return ("working", None, None)
    if "#" in ref:
        line, _, n = ref.rpartition("#")
        if line and n.isdigit():
            return ("revision", line, int(n))
    return ("line", ref, None)


__all__ = ["list_cold_archivable"]
