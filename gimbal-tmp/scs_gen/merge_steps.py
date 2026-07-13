#!/usr/bin/env python3
"""merge_steps.py — splice the generated `steps.json` (test cases) onto
the scaffold's seed step, producing a complete scenario JSON.

Usage:
    python merge_steps.py <scenario_merged.json> <steps.json> <out.json>
"""
from __future__ import annotations

import copy
import json
import sys


def main(scaffold_path: str, steps_path: str, out_path: str) -> int:
    scaffold = json.load(open(scaffold_path, encoding="utf-8"))
    steps = json.load(open(steps_path, encoding="utf-8"))["steps"]
    merged = copy.deepcopy(scaffold)
    merged["steps"] = [merged["steps"][0]] + steps   # seed + generated
    json.dump(merged, open(out_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"merged: 1 seed + {len(steps)} generated steps -> {out_path}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit("usage: merge_steps.py <scaffold> <steps> <out>")
    sys.exit(main(*sys.argv[1:]))
