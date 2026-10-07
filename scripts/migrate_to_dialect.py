"""S1-A1 迁移工具：存量 Python 实例 → systems/<系统>/endpoints/*.md。

确定性转换（gimbal_plate.dialect.migrate），等价校验见
tests/plate/dialect/test_migrate_equivalence.py（149 接口全等，白名单归一）。
用法：python scripts/migrate_to_dialect.py [--out systems]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from gimbal_plate.dialect.migrate import (
    convert_endpoint,
    render_endpoint_markdown,
)
from gimbal_plate.systems.fin.endpoint import ALL_ENDPOINTS as FIN
from gimbal_plate.systems.platform.endpoint import ALL_ENDPOINTS as PLATFORM

ALL_OLD = [*FIN, *PLATFORM]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="systems")
    args = ap.parse_args()
    root = Path(args.out)
    count = 0
    for old in ALL_OLD:
        md = render_endpoint_markdown(convert_endpoint(old))
        target = root / old.system / "endpoints" / f"{old.id}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(md, encoding="utf-8", newline="\n")
        count += 1
    print(f"migrated {count} endpoints -> {root}/<system>/endpoints/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
