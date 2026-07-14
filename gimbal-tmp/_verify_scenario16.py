#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Validate Scenario_Test16.json against README_order_add_field_changes.md"""

import json
from pathlib import Path

DST = Path(r"D:\Gimbal\Gimbal\gimbal-tmp\Scenario_Test16.json")

NEW_KEYS_BY_GROUP = {
    "P-A": ["receive_time_limit", "deposit_refund_day", "deposit_settlement_date"],
    "P-B": ["settle_type", "settle_type_name", "product_id", "product_name",
            "deposit_type", "deposit_type_name",
            "period_delay_type", "period_delay_type_name"],
    "P-C": ["track_bl_no"],
    "P-D": ["track_eta", "track_ata", "track_stcs", "track_ship_name", "track_voy"],
    "P-E": ["customer_put_date_desc", "deposit_refund_month", "payment_type"],
    "P-F": ["payment_type_name"],
}
FORBID = ["pol_port_name", "pod_port_name", "del_port_name"]
HEAD_FIX = ["customer_name", "operator_name", "main_sort"]


def main():
    with open(DST, "r", encoding="utf-8") as f:
        sc = json.load(f)

    overall_ok = True
    for i, step in enumerate(sc["steps"]):
        if "orderAdd" not in step["api"]["path"]:
            continue
        body = step["request"]["body"]
        is_full = all(k in body for k in ["fund_code", "track_atd", "finance_date"])
        is_light = "pol_port_name" in body
        ver = "完整版" if is_full else ("轻量版" if is_light else "未识别")
        print(f"Step {i+1} ({step['api']['path'].rsplit('/',1)[-1]}) | 版型: {ver}")

        # P-A / P-B / P-C (mandatory)
        for grp in ["P-A", "P-B", "P-C"]:
            miss = [k for k in NEW_KEYS_BY_GROUP[grp] if k not in body]
            status = "PASS" if not miss else f"MISS={miss}"
            print(f"  {grp}: {status}")
            if miss:
                overall_ok = False

        # P-D / P-E / P-F (full only)
        if is_full:
            for grp in ["P-D", "P-E", "P-F"]:
                miss = [k for k in NEW_KEYS_BY_GROUP[grp] if k not in body]
                status = "PASS" if not miss else f"MISS={miss}"
                print(f"  {grp}: {status}")
                if miss:
                    overall_ok = False

        # Forbidden residual
        residual = [k for k in FORBID if k in body]
        print(f"  残留: {'PASS' if not residual else residual}")
        if residual:
            overall_ok = False

        # Anchor order spot-check: ensure P-A sits AFTER customer_name
        keys = list(body.keys())
        try:
            ci = keys.index("customer_name")
            pa_end = max(keys.index(k) for k in NEW_KEYS_BY_GROUP["P-A"])
            ok = ci < pa_end
            print(f"  头部 P-A 锚点顺序: {'PASS' if ok else 'FAIL'}")
        except ValueError:
            print("  头部 P-A 锚点顺序: SKIP (anchor not found)")

        # For full: P-D after track_atd
        if is_full:
            keys = list(body.keys())
            try:
                ti = keys.index("track_atd")
                pd_end = max(keys.index(k) for k in NEW_KEYS_BY_GROUP["P-D"])
                ok = ti < pd_end
                print(f"  P-D 锚点顺序: {'PASS' if ok else 'FAIL'}")
            except ValueError:
                print("  P-D 锚点顺序: SKIP")

            try:
                si = keys.index("sys_upttime")
                pe_end = max(keys.index(k) for k in NEW_KEYS_BY_GROUP["P-E"])
                ok = si < pe_end
                print(f"  P-E 锚点顺序: {'PASS' if ok else 'FAIL'}")
            except ValueError:
                print("  P-E 锚点顺序: SKIP")

            try:
                mi = keys.index("m_delivery_type_name")
                pf_i = keys.index("payment_type_name")
                ok = mi < pf_i
                print(f"  P-F 锚点顺序: {'PASS' if ok else 'FAIL'}")
            except ValueError:
                print("  P-F 锚点顺序: SKIP")

        # bl_no preserved
        bl = body.get("bl_no")
        print(f"  bl_no: {bl!r}")

        # policy info preserved
        for k in ("policy_id", "policy_name", "policy_type"):
            v = body.get(k)
            print(f"  {k}: {v!r}")

        print()

    print("=" * 50)
    print("OVERALL:", "PASS" if overall_ok else "FAIL")


if __name__ == "__main__":
    main()
