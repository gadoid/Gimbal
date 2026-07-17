"""explore.py — 亿海融 SyncLogorder/ajaxGetList 接口的探索测试驱动器。

设计：
  1. 用 httpx 直接复刻 YHR 认证 + HTTP GET，不依赖 gimbal 也能拿到完整响应体。
  2. 先跑一次基线空查询，提取真实样本（订单号/客户名/起运港...）作为关键字探针的输入。
  3. 根据"参数矩阵"生成若干探针，每个探针只改一个字段；分别用直发 GET 拿到响应，
     并把对应的 gimbal scenario 写到 cases/ 下沉淀。
  4. 全部探针结果汇总到 probes/manifest.jsonl + probes/<id>.json (含完整 body)。

不做任何"改进/扩展"原 Scenario_Test_yhrtest.json；所有产物落在本目录。
"""
from __future__ import annotations
import json
import os
import re
import sys
import time
import copy
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx

# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent          # gimbal-tmp/explore
REPO = HERE.parent.parent                        # D:/Gimbal/Gimbal
SRC_SCENARIO = REPO / "gimbal-tmp" / "Scenario_Test_yhrtest.json"
PROBES_DIR = HERE / "probes"
CASES_DIR = HERE / "cases"
PROBES_DIR.mkdir(parents=True, exist_ok=True)
CASES_DIR.mkdir(parents=True, exist_ok=True)

# 业务常量
BASE_URL = "https://test.21eline.com"
LOGIN_URL = f"{BASE_URL}/newshopadmin-tidb/Home/Public/index.html"
LIST_URL = f"{BASE_URL}/newshopadmin-tidb/SyncLogorder/ajaxGetList.html"
USERNAME = "yhxjsx"
PASSWORD = "Codfish1234!"

# 日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(HERE / "explore.log", encoding="utf-8"),
              logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("explore")


# ---------------------------------------------------------------------------
# 基线 body —— 复刻原 scenario 里的全字段默认（保持探索的最小变更原则）
# ---------------------------------------------------------------------------
BASE_BODY: Dict[str, Any] = {
    "page": 1,
    "port": "",
    "wd": "",
    "search_company": "",
    "work_no": "",
    "order_customer_real": "",
    "booking_agent_bp": "",
    "booking_agent_bp_real": "",
    "order_business_no": "",
    "size": 15,
    "ship_company": "",
    "sale": "",
    "client": "",
    "release_status": "",
    "financing_status": "",
    "asset_verify_status": "",
    "company_funds": "",
    "funds": "",
    "shipment_ifautoquota": "",
    "booking_mbl_delivery_mode": "",
    "order_remarks": "",
    "delivery_status": "",
    "schedule_line_category": "",
    "line_type": "",
    "premium_warn_status": "",
    "receipt_status": "",
    "insured_status": "",
    "order_terminated_shutout_status": 1,
    "is_backtrack": "",
    "cancel_remark": "",
    "limit_status": "",
    "search_time[schedule_actual_delivery_date]": "",
    "search_time[order_updated_date]": "",
    "search_time[charge_rec_date]": "",
    "search_time[charge_rec_date_ext]": "",
    "search_time[charge_pay_date]": "",
    "search_time[schedule_estimate_delivery_date]": "",
    "search_time[receipt_pay_ts]": "",
    "search_time[charge_rec_receipt_ts]": "",
    "search_time[charge_pay_payment_ts]": "",
    "search_time[file_customs_upload_ts]": "",
    "search_time[ocean_freight_ts]": "",
    "search_time[supplier_bill_time]": "",
    "search_time[customer_bill_time]": "",
    "search_time[get_customs_time]": "",
    "search_time[invoice_rec_ts]": "",
    "search_time[first_file_upload_time]": "",
    "search_time[second_file_upload_time]": "",
    "search_time[full_information_time]": "",
    "search_time[first_loan_time]": "",
    "search_time[second_loan_time]": "",
    "search_time[invoice_cny_apply_ts]": "",
    "search_time[invoice_usd_apply_ts]": "",
    "search_time[supplement_update_ts]": "",
    "search_time[decl_create_ts]": "",
    "search_time[decl_release_ts]": "",
    "search_time[track_atd]": "",
    "search_time[order_created_date]": "",
    "other_remarks": "",
    "order_ids": "",
    "bulk_query_type": 1,
    "bulk_shutout_status": "",
    "bulk_query": 0,
    "is_exceed": "",
    "handle_exceed": "",
    "finance_file_status": "",
    "finance_file_result": "",
    "loan_remark_type_select": "",
    "need_buy_back": "",
    "batch_exchange_query": "",
}

# 探索维度：(mutated_field, value, description, category)
ENUM_PROBES: List[Tuple[str, Any, str, str]] = [
    # page / size
    ("page", 1, "首页(page=1)", "pagination"),
    ("page", 2, "第二页(page=2)", "pagination"),
    ("page", 9999, "超大页码", "pagination"),
    ("size", 5, "size=5", "pagination"),
    ("size", 50, "size=50", "pagination"),
    # 状态枚举
    ("order_terminated_shutout_status", 0, "非终止", "status"),
    ("order_terminated_shutout_status", 1, "仅终止(原默认)", "status"),
    ("order_terminated_shutout_status", 2, "仅甩柜", "status"),
    ("is_backtrack", "1", "回退单", "status"),
    ("is_backtrack", "0", "非回退", "status"),
    ("bulk_query_type", 1, "批量查询类型=1", "bulk"),
    ("bulk_query_type", 2, "批量查询类型=2", "bulk"),
    ("bulk_query", 1, "启用批量查询", "bulk"),
    ("bulk_query", 0, "禁用批量查询", "bulk"),
    ("bulk_shutout_status", 1, "批量甩柜=1", "bulk"),
    # 业务开关
    ("shipment_ifautoquota", "1", "自动配额=是", "switch"),
    ("shipment_ifautoquota", "0", "自动配额=否", "switch"),
    ("booking_mbl_delivery_mode", "1", "MBL放单模式=1", "switch"),
    ("booking_mbl_delivery_mode", "2", "MBL放单模式=2", "switch"),
    ("need_buy_back", "1", "需要买回=1", "switch"),
    ("need_buy_back", "0", "不需要买回=0", "switch"),
    ("is_exceed", "1", "超额=1", "switch"),
    ("handle_exceed", "1", "处理超额=1", "switch"),
    ("batch_exchange_query", "1", "批量兑换查询=1", "switch"),
    # 财务状态枚举
    ("release_status", "1", "放单状态=1", "finance"),
    ("release_status", "2", "放单状态=2", "finance"),
    ("financing_status", "1", "融资状态=1", "finance"),
    ("financing_status", "2", "融资状态=2", "finance"),
    ("asset_verify_status", "1", "资产校验=1", "finance"),
    ("company_funds", "1", "公司资金=1", "finance"),
    ("funds", "1", "资金=1", "finance"),
    ("delivery_status", "1", "放货状态=1", "finance"),
    ("schedule_line_category", "1", "航线分类=1", "finance"),
    ("line_type", "1", "线路类型=1", "finance"),
    ("premium_warn_status", "1", "溢价预警=1", "finance"),
    ("receipt_status", "1", "签收状态=1", "finance"),
    ("insured_status", "1", "投保状态=1", "finance"),
    ("limit_status", "1", "额度状态=1", "finance"),
    # 文件状态
    ("finance_file_status", "1", "财务文件=1", "file"),
    ("finance_file_result", "1", "财务文件结果=1", "file"),
    ("loan_remark_type_select", "1", "借款备注类型=1", "file"),
]

# 时间区间探针（相对今天生成）
def _today_range() -> str:
    """生成一个能覆盖大多数订单创建日期的 1 年时间区间字符串。"""
    y = time.strftime("%Y")
    return f"['{y}-01-01','{y}-12-31']"

def _narrow_range() -> str:
    today = time.strftime("%Y-%m-%d")
    y_first = f"{time.strftime('%Y')}-01-01"
    return f"['{y_first}','{today}']"

def _empty_range() -> str:
    return ""

def _future_range() -> str:
    """未来区间，预期 0 条"""
    return "['2099-01-01','2099-12-31']"

TIME_PROBES: List[Tuple[str, Any, str, str]] = [
    ("search_time[order_created_date]", _today_range(), "订单创建时间=本年区间", "time"),
    ("search_time[order_updated_date]", _today_range(), "订单更新时间=本年区间", "time"),
    ("search_time[schedule_actual_delivery_date]", _narrow_range(), "实际送货日期=年初至今", "time"),
    ("search_time[charge_rec_date]", _today_range(), "应收开票日期=本年", "time"),
    ("search_time[charge_rec_date_ext]", _today_range(), "应收开票日期(扩展)=本年", "time"),
    ("search_time[charge_pay_date]", _today_range(), "应付开票日期=本年", "time"),
    ("search_time[track_atd]", _today_range(), "船开船时间=本年", "time"),
    ("search_time[decl_create_ts]", _today_range(), "报关创建时间=本年", "time"),
    ("search_time[decl_release_ts]", _today_range(), "报关放行时间=本年", "time"),
    ("search_time[invoice_rec_ts]", _today_range(), "发票接收时间=本年", "time"),
    ("search_time[order_created_date]", _future_range(), "订单创建时间=2099(预期空)", "time"),
    ("search_time[order_created_date]", _empty_range(), "订单创建时间=空字符串", "time"),
    # 多时间组合
    ("search_time[order_created_date]", _narrow_range(),
        "订单创建+更新时间=年初至今 (multi)", "time_multi"),
]

# ---------------------------------------------------------------------------
# HTTP 直发：登录 + GET
# ---------------------------------------------------------------------------
def login() -> str:
    """登录拿到 PHPSESSID cookie。"""
    body = f"data[username]={USERNAME}&data[password]={PASSWORD}"
    with httpx.Client(timeout=30) as c:
        r = c.post(LOGIN_URL,
                   content=body,
                   headers={"Accept": "application/json",
                            "Content-Type": "application/x-www-form-urlencoded",
                            "Host": "test.21eline.com"})
        r.raise_for_status()
        sc = r.headers.get("set-cookie", "")
    # 截取第一个 cookie 名字段
    m = re.search(r"PHPSESSID=[^;]+", sc)
    if not m:
        raise RuntimeError(f"登录未返回 PHPSESSID: {sc[:200]}")
    cookie = m.group(0)
    log.info("登录成功，cookie=%s...", cookie[:24])
    return cookie


def http_list(cookie: str, body: Dict[str, Any]) -> Tuple[int, float, Dict[str, Any] | None]:
    """GET 列表接口，返回 (status_code, duration_ms, json_or_None)。"""
    t0 = time.time()
    with httpx.Client(timeout=30) as c:
        r = c.get(LIST_URL,
                  params=body,
                  headers={"Cookie": cookie,
                           "Content-Type": "application/x-www-form-urlencoded",
                           "Accept": "*/*"})
    dur = (time.time() - t0) * 1000.0
    try:
        j = r.json()
    except Exception:
        j = None
    return r.status_code, dur, j


# ---------------------------------------------------------------------------
# Gimbal scenario 生成（落盘到 cases/）
# ---------------------------------------------------------------------------
def build_scenario(cookie: str, body: Dict[str, Any], scenario_id: str, description: str) -> Dict[str, Any]:
    """基于原 Scenario_Test_yhrtest.json 复制一份 scenario，只替换 body 与断言。"""
    with open(SRC_SCENARIO, "r", encoding="utf-8") as f:
        sc = json.load(f)
    sc["scenarioId"] = scenario_id
    sc["meta"]["name"] = scenario_id
    sc["meta"]["description"] = description
    sc["meta"]["author"] = "explore"
    sc["meta"]["owner"] = "explore"
    sc["meta"]["createTime"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    sc["config"]["users"]["yhxjsx"]["token_type"] = "Cookie"
    # 第一次运行时 Gimbal 不会自动登录；这里我们直接用真实 cookie。
    # 用一个"shortcut"：把 users 替换为已经登录好的 token，方法是注入 header token。
    # Gimbal 的 Cookie 认证会发起 login，覆盖我们注入的；所以改 strategy：直接走 step 头部。
    sc["config"]["users"]["yhxjsx"]["url"] = BASE_URL + "/"
    sc["config"]["users"]["yhxjsx"]["username"] = USERNAME
    sc["config"]["users"]["yhxjsx"]["password"] = PASSWORD
    # step
    step = sc["steps"][0]
    step["api"]["path"] = "/newshopadmin-tidb/SyncLogorder/ajaxGetList.html"
    step["api"]["headers"]["Cookie"] = "${auth.yhxjsx.token}"
    step["request"]["body"] = body
    step["description"] = description
    # 断言：状态=200 + response_body.list 存在
    step["strategy"] = [
        {
            "kind": "assertion",
            "name": "assert_http_status_eq_200",
            "phase": "verifying",
            "order": 0,
            "enabled": True,
            "onFailure": "abort",
            "target": "$.response_status",
            "operator": "eq",
            "expected": 200,
            "message": f"{scenario_id} 应返回200",
            "soft": False,
        },
        {
            "kind": "extract",
            "name": "extract_list_len",
            "phase": "after_request",
            "order": 0,
            "enabled": True,
            "onFailure": "continue",
            "expression": "$.response_body.list",
            "target": "list",
            "required": False,
            "default": None,
            "scope": "scenario",
        },
    ]
    return sc


# ---------------------------------------------------------------------------
# 单个探针执行
# ---------------------------------------------------------------------------
def run_probe(cookie: str,
              probe_id: str,
              mutated_field: str,
              value: Any,
              description: str,
              category: str,
              manifest_fh) -> Dict[str, Any]:
    body = copy.deepcopy(BASE_BODY)
    if mutated_field is not None:
        body[mutated_field] = value
    # HTTP 直发拿真实数据
    try:
        status, dur, js = http_list(cookie, body)
    except Exception as e:
        log.error("[%s] HTTP 失败: %s", probe_id, e)
        status, dur, js = -1, -1.0, None

    list_len = 0
    first_order_no = None
    first_work_no = None
    first_business_no = None
    sample = None
    if isinstance(js, dict):
        lst = js.get("list") or []
        list_len = len(lst) if isinstance(lst, list) else 0
        if list_len:
            first = lst[0]
            first_order_no = first.get("order_no")
            first_work_no = first.get("work_no")
            first_business_no = first.get("order_business_no")
            # sample 只取 ASCII 关键字段，避免 GBK 编码问题
            sample = {k: first.get(k) for k in [
                "order_no", "work_no", "order_business_no", "bl_no",
                "order_id", "id", "schedule_from_terminal", "schedule_to_terminal",
                "schedule_carrier", "order_status", "delivery_status",
                "order_terminated_shutout_status", "limit_status",
                "order_created_date", "order_updated_date", "insured_status",
                "release_status", "financing_status", "asset_verify_status",
                "order_customer", "booking_agent_bp",
            ]}

    record = {
        "probe_id": probe_id,
        "category": category,
        "mutated_field": mutated_field,
        "value": value,
        "description": description,
        "http_status": status,
        "duration_ms": round(dur, 2) if dur >= 0 else None,
        "list_len": list_len,
        "first_order_no": first_order_no,
        "first_work_no": first_work_no,
        "first_business_no": first_business_no,
        "sample": sample,
        "scenario_id": f"case_{probe_id}",
    }
    manifest_fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    manifest_fh.flush()
    log.info("[%s] %s=%r  status=%s  list_len=%d  first=%s",
             probe_id, mutated_field, value, status, list_len, first_order_no)
    # 落盘 raw body
    raw_path = PROBES_DIR / f"{probe_id}.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump({
            "probe": record,
            "response_status": status,
            "response_body": js,
        }, f, ensure_ascii=False, indent=2)
    return record


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main() -> int:
    log.info("========== explore.py 启动 ==========")
    cookie = login()

    # 0) 基线 —— 空查询
    log.info("--- 基线空查询 ---")
    base_status, base_dur, base_js = http_list(cookie, BASE_BODY)
    base_list = (base_js or {}).get("list") or []
    log.info("基线: status=%s  list_len=%d  duration=%.1fms",
             base_status, len(base_list), base_dur)
    with open(PROBES_DIR / "baseline.json", "w", encoding="utf-8") as f:
        json.dump({"status": base_status, "duration_ms": base_dur, "body": base_js},
                  f, ensure_ascii=False, indent=2)
    if not base_list:
        log.error("基线查询无数据，无法驱动关键字类探针。")
        return 1
    first = base_list[0]

    # 真实样本（驱动关键字探针）
    sample_work_no = first.get("work_no") or ""
    sample_order_no = first.get("order_no") or ""
    sample_business_no = first.get("order_business_no") or ""
    sample_order_customer = first.get("order_customer") or ""
    sample_booking_bp = first.get("booking_agent_bp") or ""
    sample_from = first.get("schedule_from_terminal") or ""
    sample_to = first.get("schedule_to_terminal") or ""
    sample_sales = first.get("order_opt_sales") or ""
    sample_remarks = first.get("order_remarks") or ""
    sample_other_remarks = first.get("other_remarks") or ""
    log.info("样本: order_no=%s work_no=%s business_no=%s from=%s->%s",
             sample_order_no, sample_work_no, sample_business_no, sample_from, sample_to)

    # 探针列表：先枚举 + 时间，再关键字
    KEYWORD_PROBES: List[Tuple[str, Any, str, str]] = [
        # 精确 / 模糊
        ("order_ids", sample_order_no, "order_ids=首条订单号", "keyword"),
        ("order_ids", f"{sample_order_no},{sample_business_no}",
            "order_ids=多ID(订单号+业务号)", "keyword"),
        ("wd", sample_order_no, "wd=首条订单号", "keyword"),
        ("wd", sample_work_no, "wd=首条工作号", "keyword"),
        ("wd", sample_business_no, "wd=首条业务号", "keyword"),
        ("search_company", sample_order_customer, "search_company=首条客户", "keyword"),
        ("work_no", sample_work_no, "work_no=首条工作号(精确)", "keyword"),
        ("order_business_no", sample_business_no, "order_business_no=首条业务号", "keyword"),
        ("order_customer_real", sample_order_customer, "order_customer_real=首条真实客户", "keyword"),
        ("booking_agent_bp", sample_booking_bp, "booking_agent_bp=首条订舱代理", "keyword"),
        ("port", sample_from, "port=首条起运港", "keyword"),
        ("port", sample_to, "port=首条目的港", "keyword"),
        ("ship_company", first.get("schedule_carrier") or "ACL", "ship_company=首条船公司", "keyword"),
        ("sale", sample_sales, "sale=首条销售员", "keyword"),
        ("client", first.get("order_opt_client") or "", "client=首条客户经理", "keyword"),
        ("order_remarks", sample_remarks, "order_remarks=首条备注", "keyword"),
        ("other_remarks", sample_other_remarks, "other_remarks=首条其它备注", "keyword"),
        ("cancel_remark", first.get("cancel_remark") or "", "cancel_remark=首条取消备注", "keyword"),
        # 反例 / 边界
        ("wd", "NONEXIST_XXZZZ_9999", "wd=不存在的字符串", "keyword_negative"),
        ("work_no", "NOT_EXIST_WORK_999", "work_no=不存在的工号", "keyword_negative"),
        ("order_business_no", "YWDD_NOTEXIST_000", "order_business_no=不存在的业务号", "keyword_negative"),
        # 模糊前缀
        ("wd", sample_order_no[:8], "wd=订单号前缀", "keyword_partial"),
        ("search_company", sample_order_customer[:2], "search_company=客户名前2字", "keyword_partial"),
    ]

    # 合并所有探针
    all_probes: List[Tuple[str | None, Any, str, str, str]] = []  # (probe_id, field, value, desc, category)
    pid = 0
    for field, value, desc, cat in ENUM_PROBES:
        pid += 1
        all_probes.append((f"p{pid:03d}", field, value, desc, cat))
    for field, value, desc, cat in TIME_PROBES:
        pid += 1
        all_probes.append((f"p{pid:03d}", field, value, desc, cat))
    # 多时间组合（单独探针 + 第二个时间字段）
    for field, value, desc, cat in [
        ("search_time[order_updated_date]", _narrow_range(),
            "订单更新+订单创建=年初至今(组合)", "time_multi"),
    ]:
        pid += 1
        all_probes.append((f"p{pid:03d}", field, value, desc, cat))
    for field, value, desc, cat in KEYWORD_PROBES:
        pid += 1
        all_probes.append((f"p{pid:03d}", field, value, desc, cat))

    # 异常探针
    pid += 1
    all_probes.append((f"p{pid:03d}", "page", 0, "page=0 边界", "negative"))
    pid += 1
    all_probes.append((f"p{pid:03d}", "size", 0, "size=0 边界", "negative"))
    pid += 1
    all_probes.append((f"p{pid:03d}", "size", 1000, "size=1000 极限", "negative"))

    log.info("共 %d 个探针", len(all_probes))

    # 执行
    manifest_path = PROBES_DIR / "manifest.jsonl"
    with open(manifest_path, "w", encoding="utf-8") as mf:
        # 写基线记录
        baseline_record = {
            "probe_id": "baseline",
            "category": "baseline",
            "mutated_field": None,
            "value": None,
            "description": "基线空查询(全部默认参数)",
            "http_status": base_status,
            "duration_ms": round(base_dur, 2),
            "list_len": len(base_list),
            "first_order_no": first.get("order_no"),
            "first_work_no": first.get("work_no"),
            "first_business_no": first.get("order_business_no"),
            "sample": {k: first.get(k) for k in [
                "order_no","work_no","order_business_no","bl_no","order_id","id",
                "schedule_from_terminal","schedule_to_terminal","schedule_carrier",
                "order_status","delivery_status","order_terminated_shutout_status",
                "limit_status","order_created_date","order_updated_date",
                "insured_status","release_status","financing_status",
                "asset_verify_status","order_customer","booking_agent_bp",
            ]},
            "scenario_id": "case_baseline",
        }
        mf.write(json.dumps(baseline_record, ensure_ascii=False) + "\n")

        records: List[Dict[str, Any]] = []
        for probe_id, field, value, desc, cat in all_probes:
            try:
                rec = run_probe(cookie, probe_id, field, value, desc, cat, mf)
                records.append(rec)
            except Exception as e:
                log.error("探针 %s 异常: %s", probe_id, e)
            time.sleep(0.4)  # 轻节流

    # 沉淀为 gimbal scenario（cases/）
    log.info("--- 沉淀场景到 cases/ ---")
    base_record = baseline_record
    base_len = base_record["list_len"]
    # 选取规则：list_len 显著变化（相对 base）的探针 + 所有正向探针 + 异常探针
    for rec in records:
        pid = rec["probe_id"]
        sid = f"case_{pid}"
        desc = f"{rec['category']} | {rec['description']} | field={rec['mutated_field']} value={rec['value']!r}"
        body = copy.deepcopy(BASE_BODY)
        if rec["mutated_field"] is not None:
            body[rec["mutated_field"]] = rec["value"]
        sc = build_scenario(cookie, body, sid, desc)
        out = CASES_DIR / f"{sid}.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(sc, f, ensure_ascii=False, indent=2)
    # 基线 case
    sc = build_scenario(cookie, copy.deepcopy(BASE_BODY), "case_baseline", "基线空查询")
    with open(CASES_DIR / "case_baseline.json", "w", encoding="utf-8") as f:
        json.dump(sc, f, ensure_ascii=False, indent=2)

    log.info("========== explore.py 结束 ==========")
    log.info("manifest: %s", manifest_path)
    log.info("cases:    %s", CASES_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
