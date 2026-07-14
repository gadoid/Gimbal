#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描所有 orderAdd / orderBook 步骤的 strategy，根据 assign 的 target 路径
自动补齐缺失的字段（值留空，由运行时 assign 注入）。"""
import json
import re
from pathlib import Path

DST = Path(r"D:\Gimbal\Gimbal\gimbal-tmp\Scenario_Test_15.json")
sc = json.loads(DST.read_text(encoding="utf-8"))

TARGET_PATHS = ("/api/order/order/orderAdd", "/api/order/orderEntrust/orderAdd",
                "/api/order/order/orderBook")

# 解析 target 路径如:
#   $.request_body.foo           -> body["foo"]
#   $.request_body.supplier[0].x -> body["supplier"][0]["x"]
#   $.request_body.customer_file_list[0].file_id -> ...
def parse_target(target):
    t = target.replace("$.request_body.", "")
    parts = []
    for m in re.finditer(r'([^.\[\]]+)|\[(\d+)\]', t):
        if m.group(1):
            parts.append(("key", m.group(1)))
        else:
            parts.append(("idx", int(m.group(2))))
    return parts


def get_path(body, parts):
    """根据 parts 返回 body 中嵌套的容器（最后一个 key 之前的路径）。"""
    cur = body
    for kind, val in parts[:-1]:
        if kind == "key":
            if val not in cur:
                return None, val
            cur = cur[val]
        else:  # idx
            if not isinstance(cur, list) or len(cur) <= val:
                return None, val
            cur = cur[val]
    return cur, parts[-1][1]


def ensure_path(body, parts, default_value):
    """确保 body 中按 parts 路径存在值，不存在则补 default_value。返回是否新增。"""
    cur = body
    for kind, val in parts[:-1]:
        if kind == "key":
            if val not in cur or cur[val] is None:
                if kind == "key":
                    cur[val] = {}
                cur = cur[val]
            else:
                cur = cur[val]
        else:  # idx
            if not isinstance(cur, list) or len(cur) <= val:
                # 如果路径上有 list 不存在，自动建一个 list
                return False
    last_kind, last_val = parts[-1]
    if last_kind == "key":
        if last_val not in cur:
            cur[last_val] = default_value
            return True
    else:  # idx for list
        if not isinstance(cur, list):
            return False
        while len(cur) <= last_val:
            cur.append({})
        return False
    return False


modified = []
for i, step in enumerate(sc["steps"]):
    path = step["api"]["path"]
    if not any(path.endswith(p) for p in TARGET_PATHS):
        continue
    body = step["request"]["body"]
    desc = step["description"]

    for s in step.get("strategy", []):
        if s.get("kind") != "assign":
            continue
        target = s.get("target", "")
        if not target.startswith("$.request_body."):
            continue
        parts = parse_target(target)

        # 检查路径是否存在
        container, last_key = get_path(body, parts)
        if container is None:
            # 路径断裂，需要补齐
            # 简化处理：直接在 body 顶层补 order_id / order_no
            if parts and parts[0][0] == "key" and parts[0][1] in ("order_id", "order_no"):
                body[parts[0][1]] = ""
                modified.append((i + 1, desc, parts[0][1], ""))
                continue
            # customer_file_list[0].file_id：补 customer_file_list = [{...}]
            if len(parts) == 3 and parts[0] == ("key", "customer_file_list") \
               and parts[1] == ("idx", 0) and parts[2] == ("key", "file_id"):
                if "customer_file_list" not in body:
                    body["customer_file_list"] = []
                if not isinstance(body["customer_file_list"], list) or len(body["customer_file_list"]) == 0:
                    body["customer_file_list"] = [{
                        "client_company_id": "16",
                        "client_company_name": "兰森玻璃（青岛）有限公司",
                        "trustee_company_id": "31",
                        "trustee_company_name": "青岛易汇智供应链管理有限公司",
                        "document_type": "BOOK_CUSTOMER",
                        "file_url": "",
                        "file_name": "",
                        "file_id": "",
                        "file_type": "PDF",
                        "_XID": "row_1263"
                    }]
                    modified.append((i + 1, desc, "customer_file_list", "[1 placeholder]"))
                continue
            print(f"  Step {i+1} 未处理 target={target}")

DST.write_text(json.dumps(sc, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"补齐字段 {len(modified)} 条:")
for s, d, k, v in modified:
    print(f"  Step {s}: {k} = {v!r}")
print(f"\n已写回 {DST}")