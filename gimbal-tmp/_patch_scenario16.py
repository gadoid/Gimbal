#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Apply README_order_add_field_changes.md v2.0 patches to Scenario_Test_11.
- DO NOT change original bl_no (提单号) or policy info (策略信息).
- Only ADD new fields; delete only the 3 *_port_name keys on light bodies.
- Write to Scenario_Test16.json
"""

import json
from collections import OrderedDict
from pathlib import Path

SRC = Path(r"D:\Gimbal\Gimbal\gimbal-tmp\Scenario_Test_11_OUHUA_YIHUILIAN.json")
DST = Path(r"D:\Gimbal\Gimbal\gimbal-tmp\Scenario_Test_16.json")

# Patch groups per README §2.1
PA = ["receive_time_limit", "deposit_refund_day", "deposit_settlement_date"]
PB = [
    "settle_type", "settle_type_name",
    "product_id", "product_name",
    "deposit_type", "deposit_type_name",
    "period_delay_type", "period_delay_type_name",
]
PC = ["track_bl_no"]
PD = ["track_eta", "track_ata", "track_stcs", "track_ship_name", "track_voy"]
PE = ["customer_put_date_desc", "deposit_refund_month", "payment_type"]
PF = ["payment_type_name"]
FORBID = ["pol_port_name", "pod_port_name", "del_port_name"]

# Insertion anchor pairs (anchor_key -> list of new keys to insert right after)
# For full body, also need P-D after track_atd, P-E after sys_upttime, P-F after m_delivery_type_name
ANCHORS_LIGHT = [
    ("customer_name", PA),
    ("policy_type", PB),
    ("bl_no", PC),
]
ANCHORS_FULL = [
    ("customer_name", PA),
    ("policy_type", PB),
    ("bl_no", PC),
    ("track_atd", PD),
    ("sys_upttime", PE),
    ("m_delivery_type_name", PF),
]


def reorder_body(body: dict, anchors: list, is_full: bool) -> dict:
    """Insert new keys right after the anchor key, preserving original order.
    Also remove forbidden keys if light body.
    Skip insertion if anchor key not present (defensive).
    """
    # First build a working list of (key, value) in current order
    items = list(body.items())

    # Remove forbidden keys (light only)
    if not is_full:
        items = [(k, v) for (k, v) in items if k not in FORBID]

    # Insert groups
    # Process from last to first so earlier indices remain valid
    for anchor_key, new_keys in reversed(anchors):
        if anchor_key not in body:
            # anchor not present; skip silently (defensive)
            continue
        # Find current position of anchor (may have shifted)
        idx = None
        for i, (k, _) in enumerate(items):
            if k == anchor_key:
                idx = i
                break
        if idx is None:
            continue
        # Skip if any new key already exists (defensive: do not duplicate)
        existing = {k for k, _ in items}
        to_insert = [(k, "") for k in new_keys if k not in existing]
        if not to_insert:
            continue
        items = items[: idx + 1] + to_insert + items[idx + 1 :]

    return OrderedDict(items)


def is_full_body(body: dict) -> bool:
    return all(k in body for k in ["fund_code", "track_atd", "finance_date"])


def is_light_body(body: dict) -> bool:
    return "pol_port_name" in body


def main():
    with open(SRC, "r", encoding="utf-8") as f:
        sc = json.load(f, object_pairs_hook=OrderedDict)

    changed = []
    for i, step in enumerate(sc["steps"]):
        path = step.get("api", {}).get("path", "")
        body = step["request"]["body"]
        full = is_full_body(body)
        light = is_light_body(body)
        # Trigger: any order-context body that is full (fund_code+track_atd+finance_date)
        # or light (has pol_port_name). This covers orderAdd AND orderBook and
        # any other endpoints that carry the full order body shape.
        if not (full or light):
            continue
        ver = "完整版" if full else "轻量版"
        anchors = ANCHORS_FULL if full else ANCHORS_LIGHT
        new_body = reorder_body(body, anchors, is_full=full)
        step["request"]["body"] = new_body
        changed.append((i + 1, path, ver, len(new_body)))

    # Update scenarioId minimally to reflect new file (keep name)
    # (No change to bl_no var or policy fields per requirement.)

    with open(DST, "w", encoding="utf-8") as f:
        json.dump(sc, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("=== Patch Summary ===")
    for idx, path, ver, n in changed:
        print(f"Step {idx:>2} | {path:<35} | {ver} | body keys: {n}")
    print(f"\nWritten to: {DST}")


if __name__ == "__main__":
    main()
