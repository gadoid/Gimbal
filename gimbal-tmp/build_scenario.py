"""
Build the GIMBAL scenario for fin1-1782135896.ndjson.

Pattern (aligned with e2e.json):
  - request.body is the captured literal (no ${var.x} placeholders, except bl_no)
  - dynamic values are injected via `assign` strategy on each consumer step
  - producer steps use `extract` to publish values to scenario scope

Only `${var.bl_no}` remains as a template literal (from config.vars).
"""

import json
import copy

# ---- helpers ---------------------------------------------------------------

def parse_body(rec):
    return json.loads(rec["body"]) if rec.get("body") else {}

def parse_resp(rec):
    return json.loads(rec["response_body"]) if rec.get("response_body") else {}

def deep_clone(o):
    return copy.deepcopy(o)


records_arr = json.load(open("D:/Gimbal/Gimbal/gimbal-tmp/keep_records.json", encoding="utf-8"))
rec_by_idx = {r["idx"]: r for r in records_arr}


def step_api(service, path):
    return {
        "kind": "api",
        "service": service,
        "method": "POST",
        "path": path,
        "headers": {"Authorization": "${auth.codfish.token}"},
        "timeout": 30,
    }


def assertion(message):
    return {
        "kind": "assertion",
        "name": "assert_status_200",
        "phase": "verifying",
        "order": 0,
        "enabled": True,
        "onFailure": "abort",
        "target": "$.response_status",
        "operator": "eq",
        "expected": 200,
        "message": message,
        "soft": False,
    }


def extract(name, expression, target, order=0):
    return {
        "kind": "extract",
        "name": name,
        "phase": "after_request",
        "order": order,
        "enabled": True,
        "onFailure": "abort",
        "expression": expression,
        "target": target,
        "required": True,
        "default": None,
        "scope": "scenario",
    }


def assign(name, source, target, order=0):
    return {
        "kind": "assign",
        "name": name,
        "phase": "before_request",
        "order": order,
        "enabled": True,
        "onFailure": "abort",
        "source": source,
        "target": target,
        "scope": "scenario",
    }


def make_step(path, body, message, strategy):
    return {
        "kind": "step",
        "api": step_api("tidb-test-service", path),
        "request": {"kind": "request", "body": body},
        "strategy": [assertion(message)] + strategy,
    }


def body_for(idx):
    body = parse_body(rec_by_idx[idx])
    return deep_clone(body)


def templatize_bl_no(body):
    """Replace every "GIMBAL_TEST_1" string value with ${var.bl_no}."""
    def walk(obj):
        if isinstance(obj, dict):
            return {k: walk(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [walk(v) for v in obj]
        else:
            if obj == "GIMBAL_TEST_1":
                return "${var.bl_no}"
            return obj
    return walk(body)


# Build steps ----------------------------------------------------------------
steps = []

# === Step 1: idx 0 orderAdd (check) — initial ===
b = templatize_bl_no(parse_body(rec_by_idx[0]))
steps.append(make_step("/api/order/orderEntrust/orderAdd", b, "委托下单校验应返回200", []))

# === Step 2: idx 1 orderAdd (submit) ===
b = templatize_bl_no(parse_body(rec_by_idx[1]))
steps.append(make_step("/api/order/orderEntrust/orderAdd", b, "委托下单提交应返回200", []))

# === Step 3: idx 2 orderPage — extract order_id, order_no ===
b = templatize_bl_no(parse_body(rec_by_idx[2]))
steps.append(make_step(
    "/api/order/orderEntrust/orderPage",
    b,
    "委托单分页查询应返回200",
    [
        extract("extract_order_id", "$.response_body.data.data[0].order_id", "order_id"),
        extract("extract_order_no", "$.response_body.data.data[0].order_no", "order_no", order=1),
    ],
))

# === Step 4: idx 3 orderDetail — extract order_container_id, order_supplier_id ===
b = templatize_bl_no(parse_body(rec_by_idx[3]))
steps.append(make_step(
    "/api/order/order/orderDetail",
    b,
    "订单详情应返回200",
    [
        assign("assign_order_id_step4", "$.order_id", "$.request_body.order_id"),
        extract("extract_order_container_id_step4", "$.response_body.data.container[0].order_container_id", "order_container_id"),
        extract("extract_order_supplier_id_step4", "$.response_body.data.supplier[0].order_supplier_id", "order_supplier_id", order=1),
    ],
))

# === Step 5: idx 12 orderAdd (check) — re-check after containers ===
b = templatize_bl_no(parse_body(rec_by_idx[12]))
steps.append(make_step(
    "/api/order/orderEntrust/orderAdd",
    b,
    "委托下单校验(contain)应返回200",
    [
        assign("assign_order_id_step5", "$.order_id", "$.request_body.order_id"),
        assign("assign_order_no_step5", "$.order_no", "$.request_body.order_no", order=-1),
        assign("assign_order_container_id_step5", "$.order_container_id", "$.request_body.container[0].order_container_id", order=-2),
        assign("assign_order_supplier_id_step5", "$.order_supplier_id", "$.request_body.supplier[0].order_supplier_id", order=-3),
        assign("assign_order_id_supplier_step5", "$.order_id", "$.request_body.supplier[0].order_id", order=-4),
    ],
))

# === Step 6: idx 14 orderAdd (submit) ===
b = templatize_bl_no(parse_body(rec_by_idx[14]))
steps.append(make_step(
    "/api/order/orderEntrust/orderAdd",
    b,
    "委托下单提交(contain)应返回200",
    [
        assign("assign_order_id_step6", "$.order_id", "$.request_body.order_id"),
        assign("assign_order_no_step6", "$.order_no", "$.request_body.order_no", order=-1),
        assign("assign_order_container_id_step6", "$.order_container_id", "$.request_body.container[0].order_container_id", order=-2),
        assign("assign_order_supplier_id_step6", "$.order_supplier_id", "$.request_body.supplier[0].order_supplier_id", order=-3),
        assign("assign_order_id_supplier_step6", "$.order_id", "$.request_body.supplier[0].order_id", order=-4),
    ],
))

# === Step 7: idx 19 orderDetail — extract order_container_id_2 (second/new container) ===
b = templatize_bl_no(parse_body(rec_by_idx[19]))
steps.append(make_step(
    "/api/order/order/orderDetail",
    b,
    "订单详情(contain-update)应返回200",
    [
        assign("assign_order_id_step7", "$.order_id", "$.request_body.order_id"),
        extract("extract_order_container_id_step7", "$.response_body.data.container[0].order_container_id", "order_container_id_2"),
    ],
))

# === Step 8: idx 26 orderAdd (check) ===
b = templatize_bl_no(parse_body(rec_by_idx[26]))
steps.append(make_step(
    "/api/order/order/orderAdd",
    b,
    "订单新增校验(contain)应返回200",
    [
        assign("assign_order_id_step8", "$.order_id", "$.request_body.order_id"),
        assign("assign_order_no_step8", "$.order_no", "$.request_body.order_no", order=-1),
        assign("assign_order_container_id_step8", "$.order_container_id_2", "$.request_body.container[0].order_container_id", order=-2),
        assign("assign_order_supplier_id_step8", "$.order_supplier_id", "$.request_body.supplier[0].order_supplier_id", order=-3),
        assign("assign_order_id_supplier_step8", "$.order_id", "$.request_body.supplier[0].order_id", order=-4),
    ],
))

# === Step 9: idx 28 orderBook — extract file_id ===
b = templatize_bl_no(parse_body(rec_by_idx[28]))
steps.append(make_step(
    "/api/order/order/orderBook",
    b,
    "订舱应返回200",
    [
        assign("assign_order_id_step9", "$.order_id", "$.request_body.order_id"),
        assign("assign_order_no_step9", "$.order_no", "$.request_body.order_no", order=-1),
        assign("assign_order_container_id_step9", "$.order_container_id_2", "$.request_body.container[0].order_container_id", order=-2),
        assign("assign_order_supplier_id_step9", "$.order_supplier_id", "$.request_body.supplier[0].order_supplier_id", order=-3),
        assign("assign_order_id_supplier_step9", "$.order_id", "$.request_body.supplier[0].order_id", order=-4),
        extract("extract_file_id_step9", "$.response_body.data[0].file_id", "file_id"),
    ],
))

# === Step 10: idx 29 orderAdd (submit) ===
b = templatize_bl_no(parse_body(rec_by_idx[29]))
steps.append(make_step(
    "/api/order/order/orderAdd",
    b,
    "订单提交(订舱)应返回200",
    [
        assign("assign_order_id_step10", "$.order_id", "$.request_body.order_id"),
        assign("assign_order_no_step10", "$.order_no", "$.request_body.order_no", order=-1),
        assign("assign_order_container_id_step10", "$.order_container_id_2", "$.request_body.container[0].order_container_id", order=-2),
        assign("assign_order_supplier_id_step10", "$.order_supplier_id", "$.request_body.supplier[0].order_supplier_id", order=-3),
        assign("assign_order_id_supplier_step10", "$.order_id", "$.request_body.supplier[0].order_id", order=-4),
        assign("assign_file_id_step10", "$.file_id", "$.request_body.customer_file_list[0].file_id", order=-5),
    ],
))

# === Step 11: idx 30 orderPage — extract order_sub_no ===
b = templatize_bl_no(parse_body(rec_by_idx[30]))
steps.append(make_step(
    "/api/order/order/orderPage",
    b,
    "订单分页查询应返回200",
    [
        extract("extract_order_sub_no_step11", "$.response_body.data.data[0].order_sub_no", "order_sub_no"),
    ],
))

# === Step 12: idx 32 orderDetail — extract order_sub_id ===
b = templatize_bl_no(parse_body(rec_by_idx[32]))
steps.append(make_step(
    "/api/order/order/orderDetail",
    b,
    "订单详情(sub)应返回200",
    [
        assign("assign_order_id_step12", "$.order_id", "$.request_body.order_id"),
        extract("extract_order_sub_id_step12", "$.response_body.data.order_sub[0].order_sub_id", "order_sub_id"),
    ],
))

# === Step 13: idx 42 toggleRealAmount — first toggle (pre-fee-edit) ===
b = templatize_bl_no(parse_body(rec_by_idx[42]))
steps.append(make_step(
    "/api/order/orderFee/toggleRealAmount",
    b,
    "费用详情切换应返回200",
    [
        assign("assign_order_id_step13", "$.order_id", "$.request_body.order_id"),
    ],
))

# === Step 14: idx 56 bookRealAmountEdit (check) ===
b = templatize_bl_no(parse_body(rec_by_idx[56]))
steps.append(make_step(
    "/api/order/orderFee/bookRealAmountEdit",
    b,
    "费用编辑校验应返回200",
    [
        assign("assign_order_id_step14", "$.order_id", "$.request_body.order_id"),
    ],
))

# === Step 15: idx 57 bookRealAmountEdit (submit) ===
b = templatize_bl_no(parse_body(rec_by_idx[57]))
steps.append(make_step(
    "/api/order/orderFee/bookRealAmountEdit",
    b,
    "费用编辑提交应返回200",
    [
        assign("assign_order_id_step15", "$.order_id", "$.request_body.order_id"),
    ],
))

# === Step 16: idx 66 checkGenerateOrderSub ===
b = templatize_bl_no(parse_body(rec_by_idx[66]))
steps.append(make_step(
    "/api/order/order/checkGenerateOrderSub",
    b,
    "检查生成子订单应返回200",
    [
        assign("assign_order_id_step16", "$.order_id", "$.request_body.order_id"),
    ],
))

# === Step 17: idx 68 generateOrderSub ===
b = templatize_bl_no(parse_body(rec_by_idx[68]))
steps.append(make_step(
    "/api/order/order/generateOrderSub",
    b,
    "生成子订单应返回200",
    [
        assign("assign_order_id_step17", "$.order_id", "$.request_body.order_id"),
    ],
))

# === Step 18: idx 70 orderDetail — refresh ===
b = templatize_bl_no(parse_body(rec_by_idx[70]))
steps.append(make_step(
    "/api/order/order/orderDetail",
    b,
    "订单详情(sub-refresh)应返回200",
    [
        assign("assign_order_id_step18", "$.order_id", "$.request_body.order_id"),
    ],
))

# === Step 19: idx 72 toggleRealAmount — extract order_fee_real_id (final) ===
b = templatize_bl_no(parse_body(rec_by_idx[72]))
steps.append(make_step(
    "/api/order/orderFee/toggleRealAmount",
    b,
    "费用详情切换(最终)应返回200",
    [
        assign("assign_order_id_step19", "$.order_id", "$.request_body.order_id"),
        extract("extract_order_fee_real_id_step19", "$.response_body.data.to_customer[0].put_amount.standard_list[0].order_fee_real_id", "order_fee_real_id"),
    ],
))

# === Step 20: idx 90 realAmountLockSubmit (check) ===
b = templatize_bl_no(parse_body(rec_by_idx[90]))
steps.append(make_step(
    "/api/order/orderFee/realAmountLockSubmit",
    b,
    "费用锁定校验应返回200",
    [
        assign("assign_order_id_step20", "$.order_id", "$.request_body.order_id"),
        assign("assign_order_fee_real_id_step20", "$.order_fee_real_id", "$.request_body.order_fee_real_ids[0]", order=-1),
    ],
))

# === Step 21: idx 91 realAmountLockSubmit (audit) ===
b = templatize_bl_no(parse_body(rec_by_idx[91]))
steps.append(make_step(
    "/api/order/orderFee/realAmountLockSubmit",
    b,
    "费用审批应返回200",
    [
        assign("assign_order_id_step21", "$.order_id", "$.request_body.order_id"),
        assign("assign_order_fee_real_id_step21", "$.order_fee_real_id", "$.request_body.order_fee_real_ids[0]", order=-1),
    ],
))

# === Step 22: idx 92 realAmountLockSubmit (submit) ===
b = templatize_bl_no(parse_body(rec_by_idx[92]))
steps.append(make_step(
    "/api/order/orderFee/realAmountLockSubmit",
    b,
    "费用锁定提交应返回200",
    [
        assign("assign_order_id_step22", "$.order_id", "$.request_body.order_id"),
        assign("assign_order_fee_real_id_step22", "$.order_fee_real_id", "$.request_body.order_fee_real_ids[0]", order=-1),
        assign("assign_order_sub_no_step22", "$.order_sub_no", "$.request_body.audit_msg.code", order=-2),
    ],
))

# === Step 23: idx 96 orderDetail — extract audit_id ===
b = templatize_bl_no(parse_body(rec_by_idx[96]))
steps.append(make_step(
    "/api/order/order/orderDetail",
    b,
    "订单详情(audit)应返回200",
    [
        assign("assign_order_id_step23", "$.order_id", "$.request_body.order_id"),
        extract("extract_audit_id_step23", "$.response_body.data.audit[0].audit_id", "audit_id"),
    ],
))

# === Step 24: idx 151 auditExecute ===
b = templatize_bl_no(parse_body(rec_by_idx[151]))
steps.append(make_step(
    "/api/home/audit/auditExecute",
    b,
    "费用审批批准应返回200",
    [
        assign("assign_audit_id_step24", "$.audit_id", "$.request_body.audit_ids[0]"),
    ],
))

# === Step 25: idx 159 changeInvoiceApply (check) ===
b = templatize_bl_no(parse_body(rec_by_idx[159]))
steps.append(make_step(
    "/api/order/order/changeInvoiceApply",
    b,
    "未放款开票申请(校验)应返回200",
    [
        assign("assign_order_id_step25", "$.order_id", "$.request_body.order_ids[0]"),
    ],
))

# === Step 26: idx 160 changeInvoiceApply (audit) ===
b = templatize_bl_no(parse_body(rec_by_idx[160]))
steps.append(make_step(
    "/api/order/order/changeInvoiceApply",
    b,
    "未放款开票审批应返回200",
    [
        assign("assign_order_id_step26", "$.order_id", "$.request_body.order_ids[0]"),
    ],
))

# === Step 27: idx 161 changeInvoiceApply (submit) ===
b = templatize_bl_no(parse_body(rec_by_idx[161]))
steps.append(make_step(
    "/api/order/order/changeInvoiceApply",
    b,
    "未放款开票提交应返回200",
    [
        assign("assign_order_id_step27", "$.order_id", "$.request_body.order_ids[0]"),
    ],
))

# === Step 28: idx 163 auditPage — extract audit_id_loan_invoice ===
b = templatize_bl_no(parse_body(rec_by_idx[163]))
steps.append(make_step(
    "/api/home/audit/auditPage",
    b,
    "未放款开票审批列表应返回200",
    [
        extract("extract_audit_id_loan_invoice_step28", "$.response_body.data.data[0].audit_id", "audit_id_loan_invoice"),
    ],
))

# === Step 29: idx 176 auditExecute (loan-invoice) ===
b = templatize_bl_no(parse_body(rec_by_idx[176]))
steps.append(make_step(
    "/api/home/audit/auditExecute",
    b,
    "未放款开票审批批准应返回200",
    [
        assign("assign_audit_id_loan_invoice_step29", "$.audit_id_loan_invoice", "$.request_body.audit_ids[0]"),
    ],
))

# === Step 30: idx 187 financePutList — extract order_sub_currency ===
b = templatize_bl_no(parse_body(rec_by_idx[187]))
steps.append(make_step(
    "/api/finance/accountFee/financePutList",
    b,
    "对账查询应返回200",
    [
        extract("extract_order_sub_currency_step30", "$.response_body.data.data[0].order_sub_currency", "order_sub_currency"),
    ],
))

# === Step 31: idx 188 orderReceiveAccountEdit (check) ===
b = templatize_bl_no(parse_body(rec_by_idx[188]))
steps.append(make_step(
    "/api/finance/receiveAccount/orderReceiveAccountEdit",
    b,
    "对账编辑校验应返回200",
    [
        assign("assign_order_id_step31", "$.order_id", "$.request_body.select_list[0].order_id"),
        assign("assign_order_no_step31", "$.order_no", "$.request_body.select_list[0].order_no", order=-1),
        assign("assign_order_sub_id_step31", "$.order_sub_id", "$.request_body.select_list[0].order_sub_id", order=-2),
        assign("assign_order_sub_currency_step31", "$.order_sub_currency", "$.request_body.select_list[0].order_sub_currency", order=-3),
    ],
))

# === Step 32: idx 189 orderReceiveAccountEdit (submit) — extract receive_account_id ===
b = templatize_bl_no(parse_body(rec_by_idx[189]))
steps.append(make_step(
    "/api/finance/receiveAccount/orderReceiveAccountEdit",
    b,
    "对账编辑提交应返回200",
    [
        assign("assign_order_id_step32", "$.order_id", "$.request_body.select_list[0].order_id"),
        assign("assign_order_no_step32", "$.order_no", "$.request_body.select_list[0].order_no", order=-1),
        assign("assign_order_sub_id_step32", "$.order_sub_id", "$.request_body.select_list[0].order_sub_id", order=-2),
        assign("assign_order_sub_currency_step32", "$.order_sub_currency", "$.request_body.select_list[0].order_sub_currency", order=-3),
        extract("extract_receive_account_id_step32", "$.response_body.data.receive_account_id", "receive_account_id", order=1),
    ],
))

# === Step 33: idx 195 receiveConfirmList — extract confirm_list ===
b = templatize_bl_no(parse_body(rec_by_idx[195]))
steps.append(make_step(
    "/api/finance/receiveAccount/receiveConfirmList",
    b,
    "对账确认列表应返回200",
    [
        assign("assign_receive_account_id_step33", "$.receive_account_id", "$.request_body.receive_account_id"),
        extract("extract_confirm_list_step33", "$.response_body.data", "confirm_list", order=-1),
    ],
))

# === Step 34: idx 196 accountConfirm ===
b = templatize_bl_no(parse_body(rec_by_idx[196]))
steps.append(make_step(
    "/api/finance/receiveAccount/accountConfirm",
    b,
    "对账确认应返回200",
    [
        assign("assign_receive_account_id_step34", "$.receive_account_id", "$.request_body.receive_account_id"),
        assign("assign_confirm_list_step34", "$.confirm_list", "$.request_body.confirm_list", order=-1),
    ],
))


# === Assemble top-level scenario ===

scenario = {
    "kind": "scenario",
    "scenarioId": "fin1-费用锁定到对账确认",
    "meta": {
        "name": "订单费用锁定到对账确认-正常",
        "description": "从委托下单→订舱→费用锁定→费用审批→未放款开票→对账编辑→对账确认的端到端数据驱动用例（fin1 1782135896）",
        "module": "finance",
        "priority": 1,
        "author": "codfish",
        "owner": "codfish",
        "tags": ["e2e", "finance", "lock", "confirm"],
        "version": "1.0.0",
        "createTime": "2026-06-23T00:00:00",
        "expire": False,
        "requirementRef": [],
    },
    "config": {
        "setup": [],
        "teardown": [],
        "services": {
            "tidb-test-service": "https://fin-tidb.21eflag.com/",
        },
        "vars": {
            "bl_no": "GIMBAL_TEST_1",
        },
        "users": {
            "codfish": {
                "url": "https://fin-tidb.21eflag.com/",
                "username": "18180789652",
                "password": "yhd123456!",
                "expires_in": 7200,
                "token_type": "Authorization",
            }
        },
        "timePolicy": {"kind": "record"},
        "retry": None,
    },
    "resource": {},
    "steps": steps,
}

out_path = "D:/Gimbal/Gimbal/gimbal-tmp/fin1_scenario.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(scenario, f, ensure_ascii=False, indent=2)

print(f"wrote {out_path}")
print(f"steps: {len(steps)}")