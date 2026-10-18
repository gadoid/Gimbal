"""合入闸(归一方案 v1.0 §1.10 规则 3):kind=integration 系统不得有 draft 块。

本地 check 对 draft 只出 warning(起草常态);主分支防线是本用例 —— 随
verify_all 第 1 步(gimbal+plate pytest)运行,合入前必过。扫描仓库真源
``systems/``,与生产同一 collect_system_tree。
"""
from __future__ import annotations

from pathlib import Path

from gimbal_plate.dialect.validation import collect_system_tree

REPO = Path(__file__).resolve().parents[2]


def _is_integration(system_root: Path) -> bool:
    tree = collect_system_tree(system_root, with_common=False)
    kinds = {sd.kind for sd in tree.service_definitions}
    return kinds == {"integration"}


def test_no_integration_system_has_draft_blocks():
    systems_root = REPO / "systems"
    offenders: list[str] = []
    for system_dir in sorted(systems_root.iterdir()):
        if not system_dir.is_dir() or not (system_dir / "system.md").is_file():
            continue
        try:
            if not _is_integration(system_dir):
                continue
        except Exception:
            continue  # 方言错误由 check/CI 另行拦截,本闸只管 draft
        if collect_system_tree(system_dir, with_common=False).has_draft_block:
            offenders.append(system_dir.name)
    assert not offenders, (
        f"kind=integration 系统存在 review: draft 块(主分支禁 draft,"
        f"评审后全部置 reviewed):{offenders}")
