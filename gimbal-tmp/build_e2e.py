"""
Build a data-driven e2e scenario JSON file for the order->AR->writeoff flow.

Strategy:
 - bl_no is the single source of truth (config.vars.bl_no); referenced via ${var.bl_no}
 - dynamic IDs are captured via extract (after_request, scope=scenario) the first
   time they appear, then assigned (before_request) to subsequent request bodies
 - order index: 0 = earliest assign; -1 / -2 ... = applied after (so they can
   build on previous assigns without re-reading the raw body)
 - Every step asserts response_status == 200
"""

import json
import os

# ---------------------------------------------------------------------------
# 1. helpers
# ---------------------------------------------------------------------------
def api(path, method="POST"):
    return {
        "kind": "api",
        "service": "tidb-test-service",
        "method": method,
        "path": path,
        "headers": {"Authorization": "${auth.codfish.token}"},
        "timeout": 30,
    }

def req(body):
    return {"kind": "request", "body": body}

def assert200(name, msg):
    return {
        "kind": "assertion",
        "name": name,
        "phase": "verifying",
        "order": 0,
        "enabled": True,
        "onFailure": "abort",
        "target": "response_status",
        "operator": "eq",
        "expected": 200,
        "message": msg,
        "soft": False,
    }

def extract(name, expression, target, scope="scenario", order=0):
    s = {
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
    }
    if scope:
        s["scope"] = scope
    return s

def assign(name, source, target, order):
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

def step(api_def, body, strategy, api_ref=None):
    s = {"kind": "step"}
    if api_ref is not None:
        s["api"] = api_ref
    else:
        s["api"] = api_def
    s["request"] = req(body)
    s["strategy"] = strategy
    return s

# ---------------------------------------------------------------------------
# 2. data templates
# ---------------------------------------------------------------------------
BLNO = "${var.bl_no}"

# initial order (step 1 / 2) – blank supplier ids, action = check/submit
ORDER_INITIAL = {
    "client_expand_name": "孙硕", "client_expand_id": "250", "m_delivery_type": "1",
    "customer_id": "16", "customer_name": "", "service_id": "55", "service_name": "曲静霞",
    "operator_id": "327", "operator_name": "", "customer_contact_id": "1547",
    "customer_contact_name": "", "main_sort": "易汇智-易航道", "policy_id": "112",
    "policy_name": "【SPV对客】易汇智", "policy_type": "JSZX",
    "service_items": ["booking_space"], "business_type": "1", "trade_term": "CIF",
    "carrier": "ACL", "carrier_id": "1", "bl_no": BLNO, "etd": 1781020800, "atd": 1781020800,
    "ship_name": BLNO, "voy": BLNO, "pol": "QINGDAO,CHINA", "pot": "QINGDAO,CHINA",
    "pod": "QINGDAO,CHINA", "del": "QINGDAO,CHINA", "country_name": "CHINA",
    "airline_type": "中国", "ocean_type": "近洋", "terms_payment": "T/T",
    "terms_transport": "CY/CY", "pay_type": "FREIGHT PREPAID",
    "customer_order_sn": BLNO, "terms_shipment": BLNO, "shipper": BLNO,
    "consignee": BLNO, "notifier": BLNO, "ship_mark": BLNO, "commodity": BLNO,
    "notes": BLNO, "cargo_type": "goods", "packer": "", "num": "1",
    "gross_weight": "100", "bulk": "100", "sea_trans_cost": "100.00", "teu": "",
    "volume": "1*40HQ", "volume_desc": "普柜", "order_sn": "", "status": "1",
    "sea_trans_currency": "USD",
    "container": [{"box_type": "40HQ", "box_num": "1", "box_no": ["1"], "seal_number": [""],
                    "sea_trans_unit_price": "100"}],
    "message_board": [], "customer_file_list": [],
    "supplier": [{"is_manual": "", "is_primary": "1", "isset_fee": "0",
                  "isset_supplier": "1", "order_id": "", "order_supplier_id": "",
                  "service_item": "booking_space", "service_item_name": "订舱",
                  "settle_object_id": "", "settlement_date": None, "supplier_id": "8",
                  "supplier_name": "上海华运船务有限公司青岛分公司",
                  "supplier_pay_date": None, "supplier_period": None,
                  "user_id": "16", "user_name": "荣洋"}],
    "remark": "", "policy_type_name": "", "main_ids": "31,1",
    "pol_cn": "青岛流亭机场", "pol_port_name": "QINGDAO,CHINA", "pol_country_id": "1",
    "pol_country": "CHINA", "pol_country_cn": "中国", "pot_cn": "青岛港",
    "pot_port_name": "QINGDAO,CHINA", "pod_cn": "青岛港", "pod_port_name": "QINGDAO,CHINA",
    "del_cn": "青岛港", "del_port_name": "QINGDAO,CHINA", "country_id": "1",
    "country_name_cn": "中国", "action": "check", "entrust_status": 1, "order_file": [],
}

# distribute / orderAdd payload (after we know order_id + supplier ids)
ORDER_DIST = {
    "client_expand_name": "孙硕", "client_expand_id": "250", "m_delivery_type": "1",
    "customer_id": "16", "customer_name": "兰森玻璃（青岛）有限公司",
    "service_id": "55", "service_name": "曲静霞", "operator_id": "327",
    "operator_name": "王晓涵", "customer_contact_id": "1547",
    "customer_contact_name": "周经理", "main_sort": "易汇智,易航道",
    "policy_id": "112", "policy_name": "【SPV对客】易汇智", "policy_type": "JSZX",
    "service_items": ["booking_space"], "business_type": "1", "trade_term": "CIF",
    "carrier": "ACL", "carrier_id": "1", "bl_no": BLNO, "etd": 1781020800,
    "atd": 1781020800, "ship_name": BLNO, "voy": BLNO, "pol": "QINGDAO,CHINA",
    "pot": "QINGDAO,CHINA", "pod": "QINGDAO,CHINA", "del": "QINGDAO,CHINA",
    "country_name": "CHINA", "airline_type": "中国", "ocean_type": "近洋",
    "terms_payment": "T/T", "terms_transport": "CY/CY", "pay_type": "FREIGHT PREPAID",
    "customer_order_sn": BLNO, "terms_shipment": BLNO, "shipper": BLNO,
    "consignee": BLNO, "notifier": BLNO, "ship_mark": BLNO, "commodity": BLNO,
    "notes": BLNO, "cargo_type": "goods", "packer": "", "num": "1",
    "gross_weight": "100.000", "bulk": "100.000", "sea_trans_cost": "100.00",
    "teu": "2", "volume": "1*40HQ", "volume_desc": "普柜", "order_sn": "",
    "status": "1", "sea_trans_currency": "USD",
    "container": [{"order_container_id": "PLACEHOLDER_OC", "box_type": "40HQ",
                    "box_num": "1", "box_no": ["1"], "seal_number": [""],
                    "sea_trans_unit_price": 100}],
    "message_board": [], "customer_file_list": [],
    "supplier": [{"order_supplier_id": "PLACEHOLDER_OSID",
                  "order_id": "PLACEHOLDER_OID", "isset_supplier": "1",
                  "is_primary": "1", "supplier_id": "8",
                  "supplier_name": "上海华运船务有限公司青岛分公司",
                  "settle_object_id": "39", "user_id": "16", "user_name": "荣洋",
                  "service_item": "booking_space", "supplier_period": "30",
                  "settlement_date": "20", "supplier_pay_date": "0", "is_manual": "0",
                  "sys_upttime": "2026-06-10 11:00:53",
                  "supplier_label": "上海华运船务有限公司青岛分公司-订舱",
                  "service_item_name": "订舱", "isset_fee": False}],
    "remark": "", "order_id": "PLACEHOLDER_OID",
    "order_no": "PLACEHOLDER_ONO", "customer_category": ",2,",
    "customer_tax_number": "91370283591262431N",
    "customer_address_cn": "山东省青岛市平度市南村镇东王府庄村",
    "customer_contact_phone": "18561657088", "customer_main_id": "31",
    "customer_main_name": "青岛易汇智供应链管理有限公司", "business_main_id": "1",
    "business_main_name": "青岛易航道物流科技有限公司", "fund_code": "", "fund_name": None,
    "track_atd": "0", "finance_date": "1781020800",
    "pol_cn": "青岛流亭机场", "pol_country_id": "1", "pol_country": "CHINA",
    "pol_country_cn": "中国", "pod_cn": "青岛港", "pot_cn": "青岛港",
    "del_cn": "青岛港", "country_id": "1", "country_name_cn": "中国",
    "customer_period": "60", "customer_settlement_date": "10", "period_rule": "0",
    "term_rule_name": None, "customer_due_date": "0", "customer_put_date": "0",
    "customer_payment_collection_date": None, "customer_put_date_manual": "0",
    "customer_put_writeoff_date": "", "supplier_due_date": "0",
    "discount_start": "0", "discount_rule": "", "discount_end": "0",
    "discount_ratio": "", "discount_status": "2", "discount_currency": "",
    "book_upload_date": "0", "trans_cost_put_preserve_date": "0",
    "bl_no_upload_date": "0", "supplier_invoice_date": "0",
    "supplier_invoice_taketime": "", "real_cost_date": "0",
    "customer_invoice_request_date": "0", "first_financing_doc_ok_date": "0",
    "second_financing_doc_ok_date": "0", "insurance_doc_ok_date": "0",
    "customer_confirm_date": "0", "is_delayed_recovery": "否",
    "delayed_recovery_usd": "", "delayed_recovery_cny": "", "delayed_time": "",
    "expect_fee_status": "0", "real_fee_status": "0", "fee_lock_status": "0",
    "pay_account_status": "0", "account_status": "0", "real_pay_usd": "0.00",
    "real_pay_cny": "0.00", "real_put_usd": "0.00", "real_put_cny": "0.00",
    "real_put_discount_rate": "0.00", "exchange_rate": "0.0000",
    "folde_pay_usd": "0.00", "folde_put_usd": "0.00", "folde_pay_total": "0.00",
    "folde_put_total": "0.00", "gross_margin": "0.00", "gross_margin_rate": "0.00",
    "is_special_pay": "0", "is_loan_before_invoice": "0", "is_fee_miss": "0",
    "fee_miss_name": "", "cancel_remark": "", "cancel_time": "0",
    "effective_id": "0", "effective_by": "", "effective_time": "0",
    "create_id": "828", "create_by": "GIMBAL", "create_time": "1781060453",
    "update_id": "828", "update_by": "GIMBAL", "update_time": "1781060453",
    "delete_time": "0", "business_time": "0", "main_ids": "31,1",
    "reverse_status": "0", "proprietary_business_status": "0",
    "loan_status": None, "first_status": None, "second_status": None,
    "loan_pay_status": "", "change_type": "0", "copy_order_id": "0",
    "real_fee_locked": False, "is_usd_project": "2", "pay_status": "1",
    "is_sync_es": "0", "expect_discount_status": "0", "real_discount_status": "0",
    "entrust_status": 2, "audit_type": "", "is_system_generate": "0",
    "is_financing": "0", "confirm_status": "0", "is_traverse": "0",
    "financing_apply_amount": "0.00", "financing_apply_amount_cny": "0.00",
    "financing_apply_amount_usd": "0.00", "sys_upttime": "2026-06-10 11:00:53",
    "reverse_status_name": "否", "is_delayed_recovery_name": "否",
    "order_finance_arr": [], "order_main_bank_arr": [], "order_sub": [],
    "order_sub_no": "",
    "service_project": {"booking_space": False, "customs_clearance": False,
                         "manifest": False, "insurance": False, "trucking": False},
    "service_project_amount": {"booking_space": False, "customs_clearance": False,
                                 "manifest": False, "insurance": False, "trucking": False},
    "finance_status": True, "main_ids_name": "易汇智,易航道",
    "policy_main_arr": [{"fee_main_id": "31", "main_name": "青岛易汇智供应链管理有限公司"},
                        {"fee_main_id": "1", "main_name": "青岛易航道物流科技有限公司"}],
    "policy_type_name": "结算业务", "business_type_name": "海运整箱",
    "cargo_type_name": "普货", "period_rule_name": "", "trade_term_name": "CIF",
    "carrier_name": "大西洋航运", "terms_transport_name": "CY/CY",
    "terms_payment_name": "T/T", "pay_type_name": "FREIGHT PREPAID",
    "m_delivery_type_name": "正本", "audit": [], "enable": "1", "policy_match": "semi",
    "policy_match_name": "手动选择", "real_discount_status_name": "—",
    "expect_discount_status_name": "—", "expect_policy_status_name": "",
    "policy_status_name": "", "subsidy_category_name": "—",
    "expect_subsidy_category_name": "—", "real_subsidy_category_name": "—",
    "action": "check", "order_file": [],
}

# orderAdd (status=2) for the second submission cycle (action=submit)
ORDER_ADD2 = {
    "client_expand_name": "孙硕", "m_delivery_type": "1", "customer_id": "16",
    "customer_name": "兰森玻璃（青岛）有限公司", "service_id": "55", "service_name": "曲静霞",
    "operator_id": "327", "operator_name": "王晓涵", "customer_contact_id": "1547",
    "customer_contact_name": "周经理", "main_sort": "易汇智,易航道",
    "policy_id": "112", "policy_name": "【SPV对客】易汇智", "policy_type": "JSZX",
    "service_items": ["booking_space"], "business_type": "1", "trade_term": "CIF",
    "carrier": "ACL", "carrier_id": "1", "bl_no": BLNO, "etd": 1781020800,
    "atd": 1781020800, "ship_name": BLNO, "voy": BLNO, "pol": "QINGDAO,CHINA",
    "pot": "QINGDAO,CHINA", "pod": "QINGDAO,CHINA", "del": "QINGDAO,CHINA",
    "country_name": "CHINA", "airline_type": "中国", "ocean_type": "近洋",
    "terms_payment": "T/T", "terms_transport": "CY/CY", "pay_type": "FREIGHT PREPAID",
    "customer_order_sn": BLNO, "terms_shipment": BLNO, "shipper": BLNO,
    "consignee": BLNO, "notifier": BLNO, "ship_mark": BLNO, "commodity": BLNO,
    "notes": BLNO, "cargo_type": "goods", "packer": "", "num": "1",
    "gross_weight": "100.000", "bulk": "100.000", "sea_trans_cost": "100.00",
    "teu": "2", "volume": "1*40HQ", "volume_desc": "普柜", "order_sn": "",
    "status": 2, "sea_trans_currency": "USD",
    "container": [{"order_container_id": "PLACEHOLDER_OC", "box_type": "40HQ",
                    "box_num": "1", "box_no": ["1"], "seal_number": [""],
                    "sea_trans_unit_price": 100}],
    "message_board": [], "customer_file_list": [],
    "supplier": [{"order_supplier_id": "PLACEHOLDER_OSID",
                  "order_id": "PLACEHOLDER_OID", "isset_supplier": "1",
                  "is_primary": "1", "supplier_id": "8",
                  "supplier_name": "上海华运船务有限公司青岛分公司",
                  "settle_object_id": "39", "user_id": "16", "user_name": "荣洋",
                  "service_item": "booking_space", "supplier_period": "30",
                  "settlement_date": "20", "supplier_pay_date": "0", "is_manual": "0",
                  "sys_upttime": "2026-06-10 11:00:53",
                  "supplier_label": "上海华运船务有限公司青岛分公司-订舱",
                  "service_item_name": "订舱", "isset_fee": False}],
    "order_id": "PLACEHOLDER_OID", "order_no": "PLACEHOLDER_ONO",
    "customer_category": ",2,", "customer_tax_number": "91370283591262431N",
    "customer_address_cn": "山东省青岛市平度市南村镇东王府庄村",
    "client_expand_id": "250", "customer_contact_phone": "18561657088",
    "customer_main_id": "31", "customer_main_name": "青岛易汇智供应链管理有限公司",
    "business_main_id": "1", "business_main_name": "青岛易航道物流科技有限公司",
    "fund_code": "", "fund_name": None, "track_atd": "0",
    "finance_date": "1781020800", "pol_cn": "青岛流亭机场",
    "pol_country_id": "1", "pol_country": "CHINA", "pol_country_cn": "中国",
    "pod_cn": "青岛港", "pot_cn": "青岛港", "del_cn": "青岛港",
    "country_id": "1", "country_name_cn": "中国", "customer_period": "60",
    "customer_settlement_date": "10", "period_rule": "0", "term_rule_name": None,
    "customer_due_date": "0", "customer_put_date": "0",
    "customer_payment_collection_date": None, "customer_put_date_manual": "0",
    "customer_put_writeoff_date": "", "supplier_due_date": "0",
    "discount_start": "0", "discount_rule": "", "discount_end": "0",
    "discount_ratio": "", "discount_status": "2", "discount_currency": "",
    "book_upload_date": "0", "trans_cost_put_preserve_date": "0",
    "bl_no_upload_date": "0", "supplier_invoice_date": "0",
    "supplier_invoice_taketime": "", "real_cost_date": "0",
    "customer_invoice_request_date": "0", "first_financing_doc_ok_date": "0",
    "second_financing_doc_ok_date": "0", "insurance_doc_ok_date": "0",
    "customer_confirm_date": "0", "is_delayed_recovery": "否",
    "delayed_recovery_usd": "", "delayed_recovery_cny": "", "delayed_time": "",
    "expect_fee_status": "0", "real_fee_status": "0", "fee_lock_status": "0",
    "pay_account_status": "0", "account_status": "0", "real_pay_usd": "0.00",
    "real_pay_cny": "0.00", "real_put_usd": "0.00", "real_put_cny": "0.00",
    "real_put_discount_rate": "0.00", "exchange_rate": "7.7000",
    "folde_pay_usd": "0.00", "folde_put_usd": "0.00", "folde_pay_total": "0.00",
    "folde_put_total": "0.00", "gross_margin": "0.00", "gross_margin_rate": "0.00",
    "is_special_pay": "0", "is_loan_before_invoice": "0", "is_fee_miss": "0",
    "fee_miss_name": "", "cancel_remark": "", "cancel_time": "0",
    "effective_id": "0", "effective_by": "", "effective_time": "0",
    "create_id": "828", "create_by": "GIMBAL", "create_time": "1781060453",
    "update_id": "828", "update_by": "GIMBAL", "update_time": "1781060750",
    "delete_time": "0", "business_time": "0", "main_ids": ",31,1,",
    "reverse_status": "0", "proprietary_business_status": "0",
    "loan_status": None, "first_status": None, "second_status": None,
    "loan_pay_status": "", "change_type": "0", "copy_order_id": "0",
    "real_fee_locked": False, "is_usd_project": "2", "pay_status": "1",
    "is_sync_es": "0", "expect_discount_status": "0", "real_discount_status": "0",
    "entrust_status": "2", "remark": "", "audit_type": "", "is_system_generate": "0",
    "is_financing": "0", "confirm_status": "0", "is_traverse": "0",
    "financing_apply_amount": "0.00", "financing_apply_amount_cny": "0.00",
    "financing_apply_amount_usd": "0.00", "sys_upttime": "2026-06-10 11:05:50",
    "reverse_status_name": "否", "is_delayed_recovery_name": "否",
    "order_finance_arr": [], "order_main_bank_arr": [], "order_sub": [],
    "order_sub_no": "",
    "service_project": {"booking_space": False, "customs_clearance": False,
                         "manifest": False, "insurance": False, "trucking": False},
    "service_project_amount": {"booking_space": False, "customs_clearance": False,
                                 "manifest": False, "insurance": False, "trucking": False},
    "finance_status": True, "main_ids_name": "易汇智,易航道",
    "policy_main_arr": [{"fee_main_id": "31", "main_name": "青岛易汇智供应链管理有限公司"},
                        {"fee_main_id": "1", "main_name": "青岛易航道物流科技有限公司"}],
    "policy_type_name": "结算业务", "business_type_name": "海运整箱",
    "cargo_type_name": "普货", "period_rule_name": "", "trade_term_name": "CIF",
    "carrier_name": "大西洋航运", "terms_transport_name": "CY/CY",
    "terms_payment_name": "T/T", "pay_type_name": "FREIGHT PREPAID",
    "m_delivery_type_name": "正本", "audit": [], "enable": "1", "policy_match": "semi",
    "policy_match_name": "手动选择", "real_discount_status_name": "—",
    "expect_discount_status_name": "—", "expect_policy_status_name": "",
    "policy_status_name": "", "subsidy_category_name": "—",
    "expect_subsidy_category_name": "—", "real_subsidy_category_name": "—",
    "action": "check", "order_file": [],
}

# fee edit / lock payload (uses order_fee_real_id)
FEE_EDIT_BODY = {
    "action": "check", "order_id": "PLACEHOLDER_OID", "discount_ratio": "",
    "service_project": "booking_space", "import_status": 0,
    "to_customer": {"put_amount": {"standard_list": [{
        "order_fee_real_id": None, "fee_type": 0, "policy_sub_id": "365",
        "service_project": "booking_space", "cost_id": "17",
        "settle_object_id": "37", "subsidy_category": "0", "currency": "USD",
        "unit_price": "100", "unit": "box", "specs": "40HQ", "num": "1",
        "remark": None, "discount_ratio": 100, "discount_amount": "100.00",
        "discount_status": "0", "policy_sub_status_name": "正常",
        "pay_sync_status": 1, "unique_id": "PLACEHOLDER_UID",
        "init_main_name": "青岛易汇智供应链管理有限公司",
        "main_name": "青岛易汇智供应链管理有限公司", "rowIndex": 0}]}},
    "to_supplier": {"pay_amount": {"standard_list": [{
        "order_fee_real_id": None, "fee_type": 0, "policy_sub_id": "365",
        "service_project": "booking_space", "cost_id": "17",
        "settle_object_id": "39", "subsidy_category": "0", "currency": "USD",
        "unit_price": "100", "unit": "box", "specs": "40HQ", "num": "1",
        "remark": None, "discount_ratio": 100, "discount_amount": "100.00",
        "discount_status": "0", "policy_sub_status_name": "异常",
        "pay_sync_status": 1, "unique_id": "PLACEHOLDER_UID",
        "init_main_name": "—", "main_name": "青岛易汇智供应链管理有限公司",
        "rowIndex": 0}]}}
}

# account confirm (uses finance_ids / bank_ids - empty by default, kept static)
ACCOUNT_CHECK = {"order_id": "PLACEHOLDER_OID", "action": "check"}
ACCOUNT_SUBMIT = {"action": "submit", "order_id": "PLACEHOLDER_OID",
                  "finance_ids": ["PLACEHOLDER_FIN1", "PLACEHOLDER_FIN2"],
                  "bank_ids": ["PLACEHOLDER_BANK1", "PLACEHOLDER_BANK2"]}

# change invoice apply (3 actions)
CHANGE_INVOICE = {"audit_note": "", "order_ids": ["PLACEHOLDER_OID"],
                  "action": "check",
                  "audit_msg": {"title": "业务订单ID", "code": "",
                                "msgs": ["未放款开票申请"]}}

# account / receivable list / select / confirm
FINPUTLIST_BODY = {"page_no": 1, "page_size": 50, "bl_nos": [], "bl_no": BLNO,
                   "operate_type": 1, "search_style": "account",
                   "account_simple_name": None, "account_type": "1",
                   "customer_id": ["16"], "put_settle_object_id": "665",
                   "main_id": "1", "pay_settle_object_id": None}

RECEIVE_EDIT = {
    "account_simple_name": None, "account_type": "1", "customer_id": ["16"],
    "put_settle_object_id": "665", "main_id": "1", "pay_settle_object_id": None,
    "selection_time": 1781073932, "action": "check", "operate_type": 1,
    "receive_account_id": None,
    "main_name": "青岛易航道物流科技有限公司",
    "put_settle_object": "青岛易汇智供应链管理有限公司",
    "pay_settle_object": None,
    "select_list": [{
        "order_id": "PLACEHOLDER_OID", "order_no": "PLACEHOLDER_ONO",
        "bl_no": BLNO, "customer_id": "16",
        "customer_name": "兰森玻璃（青岛）有限公司", "customer_main_id": "31",
        "customer_main_name": "青岛易汇智供应链管理有限公司",
        "business_main_id": "1", "business_main_name": "青岛易航道物流科技有限公司",
        "policy_type": "JSZX", "trade_term": "CIF", "customer_period": "60",
        "customer_put_date": "1786291200", "atd": "1781020800", "etd": "1781020800",
        "create_time": "1781060453", "finance_date": "1781020800",
        "fund_name": "青岛海发商业保理有限公司", "ship_name": BLNO, "voy": BLNO,
        "status": "2", "is_special_pay": "0", "pay_status": "0",
        "is_loan_before_invoice": "1", "customer_order_sn": BLNO,
        "order_sub_id": "PLACEHOLDER_OSUBID",
        "order_sub_no": "PLACEHOLDER_OSUBNO", "main_id": "1",
        "main_name": "青岛易航道物流科技有限公司", "service_project": "booking_space",
        "currency": "USD", "amount_total": "100.00", "pay_settle_object_type": "2",
        "put_settle_object_id": "665", "put_settle_object": "青岛易汇智供应链管理有限公司",
        "pay_settle_object": "上海华运船务有限公司青岛分公司",
        "book_supplier_period": "30", "book_supplier_pay_date": "1784476800",
        "book_supplier_name": "上海华运船务有限公司青岛分公司",
        "operable_amount": "100.00", "un_operable_amount": "0.00",
        "operable_flag": "all", "policy_type_name": "结算业务",
        "order_sub_currency": "USDPLACEHOLDER_OSUBID",
        "order_main_finance": "青岛银行股份有限公司江西路支行+USD+802051200001568",
        "order_error_messages": [], "order_error_message": "",
        "order_error_flag": False,
        "amount_list": [{
            "order_id": "PLACEHOLDER_OID", "order_no": "PLACEHOLDER_ONO",
            "customer_name": "兰森玻璃（青岛）有限公司", "bl_no": BLNO,
            "main_name": "青岛易航道物流科技有限公司",
            "order_sub_no": "PLACEHOLDER_OSUBNO",
            "order_sub_id": "PLACEHOLDER_OSUBID",
            "order_fee_real_id": "PLACEHOLDER_OFRID",
            "fee_real_no": "FY202606101285504", "fee_type": "0",
            "service_project": "booking_space", "fee_real_name": "海运费",
            "currency": "USD", "symbol": "1", "real_amount": "100.00",
            "supplier_id": None, "cost_no": "0001", "fee_status": "1",
            "account_no": "", "pay_account_no": "", "account_status": "0",
            "pay_account_status": "0", "invoice_status": "0",
            "receive_invoice_batch_no": None, "pay_invoice_batch_no": None,
            "receive_invoice_apply_no": None, "pay_invoice_apply_no": None,
            "put_settle_object_id": "665",
            "put_settle_object": "青岛易汇智供应链管理有限公司",
            "pay_settle_object_id": "39",
            "pay_settle_object": "上海华运船务有限公司青岛分公司",
            "writeoff_status": "1", "un_writeoff_amount": "100.00",
            "use_writeoff_amount": "0.00", "writeoff_nos": "",
            "pay_form_no": "", "pay_demand_no": "",
            "amount_error_messages": [], "amount_error_message": "",
            "amount_error_flag": False}]
    }]
}

RECEIVE_DETAIL = {"receive_account_id": "PLACEHOLDER_RAID"}
RECEIVE_CONF_LIST = {"confirm_type": 0, "receive_account_id": "PLACEHOLDER_RAID",
                     "order_ids": []}
ACCOUNT_CONFIRM = {
    "confirm_type": 0, "receive_account_id": "PLACEHOLDER_RAID",
    "confirm_list": [{
        "main_id": "31", "main_name": "青岛易汇智供应链管理有限公司",
        "symbol": "0", "settle_object_id": "1",
        "order_ids": "PLACEHOLDER_OID",
        "order_sub_ids": "PLACEHOLDER_OSUBID2",
        "order_sub_types": "0", "unique_ids": "PLACEHOLDER_UID",
        "receive_account_no": "", "account_simple_name": BLNO,
        "symbol_name": "应付", "settle_object": "青岛易航道物流科技有限公司",
        "account_batch_name": "青岛易汇智供应链管理有限公司+青岛易航道物流科技有限公司+26.06+USD100",
        "order_sub_type": 1, "only_adjust_status": 0,
        "real_amount_ids": ["PLACEHOLDER_OFRID2"],
        "currency_list": ["USD"], "_XID": "row_3720"}]
}

INVOICE_BATCH_QUERY = {"page_no": 1, "page_size": 50, "customer_id": "16",
                       "put_settle_object_id": "665",
                       "put_settle_object": "青岛易汇智供应链管理有限公司",
                       "main_id": "1", "bl_no": BLNO, "operate_type": 1,
                       "batch_type": 1, "search_style": "invoice",
                       "pay_settle_object_id": [], "account_type": "1",
                       "bl_nos": []}

INVOICE_CHECK_STEP_BASE = {
    "cny_file": [], "usd_file": [], "debitno_file": [], "style": "1",
    "apply_type": "1", "customer_id": "16",
    "customer_name": ["兰森玻璃（青岛）有限公司"],
    "put_settle_object_id": "665", "main_id": "1", "pay_settle_object_id": [],
    "merge_with_cny": "2", "selectRadio": "", "receive_invoice_batch_id": "",
    "batch_apply_name": "", "invoice_form": "", "invoice_type": "",
    "invoice_items": "", "invoice_rate_type": "", "rate_type": "",
    "usd_is_turn": "",
    "order_fee_real_id": ["PLACEHOLDER_OFRID"],
    "usd_requireinvoice_form": "", "usd_requireinvoice_type": "",
    "usd_requiretruck_remark": "", "usd_requireinvoice_items_count": "",
    "usd_requireinvoice_items": "", "usd_requireinvoice_rate": "",
    "usd_requireinvoice_rate_type": "", "usd_requireseller_name": "",
    "cny_requireinvoice_form": "", "cny_requireinvoice_type": "",
    "cny_requiretruck_remark": "", "cny_requireinvoice_items_count": "",
    "cny_requireinvoice_items": "", "cny_requireinvoice_rate": "",
    "cny_requireinvoice_rate_type": "", "cny_requireseller_name": "",
    "usd_require": {"fast_remark": [], "currency": "", "amount_total_usd": "",
                    "amount_total_cny": "", "rate": "",
                    "turn_amount_total_cny": "", "turn_amount_total_usd": "",
                    "turn_amount_total": "", "invoice_apply_name": "",
                    "invoice_apply_simple": "", "invoice_form": "",
                    "invoice_type": "", "purchaser_id": "",
                    "purchaser_head_cn": "", "purchaser_tax_number": "",
                    "seller_id": "", "seller_name": "", "bank_account": "",
                    "seller_info": "", "invoice_items": "",
                    "invoice_rate_type": "", "invoice_rate": "",
                    "require_other": "", "remark": "", "rate_list": []},
    "cny_require": {"fast_remark": [], "currency": "", "amount_total_usd": "",
                    "amount_total_cny": "", "rate": "",
                    "turn_amount_total_cny": "", "turn_amount_total_usd": "",
                    "turn_amount_total": "", "invoice_apply_name": "",
                    "invoice_apply_simple": "", "invoice_form": "",
                    "invoice_type": "", "purchaser_id": "",
                    "purchaser_head_cn": "", "purchaser_tax_number": "",
                    "seller_id": "", "seller_name": "", "bank_account": "",
                    "seller_info": "", "invoice_items": "",
                    "invoice_rate_type": "", "invoice_rate": "",
                    "require_other": "", "remark": "", "rate_list": []},
    "usd_file_id": [], "cny_file_id": [], "debitno_file_id": [],
    "batch_order_remark": [], "batch_type": "1", "cost_usd": "100.00",
    "cost_cny": "0.00",
    "put_settle_object": "青岛易汇智供应链管理有限公司",
    "main_name_cn": "青岛易航道物流科技有限公司",
    "order_sub_id": ["PLACEHOLDER_OSUBID"]
}

INVOICE_APPLY_PAGE = {"page_no": 1, "page_size": 20, "order_no": "",
                      "create_time": [1765296000000, 1781107199000],
                      "cancel_status": [], "bl_nos": [BLNO],
                      "sort_field": "create_time", "sort_order": "desc",
                      "params": {}, "create_time_start": "1765296000",
                      "create_time_end": "1781107199"}

INVOICE_BATCH_DETAIL = {"receive_invoice_batch_id": "PLACEHOLDER_RIBID"}
INVOICE_APPLY_DETAIL = {"receive_invoice_apply_id": "PLACEHOLDER_RIAPID"}

INVOICE_ADD_CHECK = {
    "invoice_number": "25922000000029755889", "invoice_type": "1",
    "invoice_amount": "50000", "invoice_tax_amount": "0.00",
    "invoice_date": 1771603200, "currency": "CNY", "usd_amount": "",
    "invoice_exchange_rate": "1",
    "invoice_original": {"file_id": "PLACEHOLDER_FID",
                         "file_name": "6a2925594f5ea.pdf", "file_type": "pdf",
                         "original_name": "电子发票（普通发票）5.pdf",
                         "file_url": "http://192.168.20.102:8001/file/o/MTA2NDc="},
    "buyer_chinese_header": "青岛易汇智供应链管理有限公司",
    "buyer_identifier_no": "91370202MAEWF5RN7G",
    "buyer_identity": "main", "isbuyer_identity": "main",
    "seller_chinese_header": "青岛易航道物流科技有限公司",
    "seller_identifier_no": "91370202MABU30PK3F",
    "seller_identity": "main", "invoice_image_name": "6a29255d33aca.png",
    "file_path": "http://192.168.20.102:8001/file/o/MTA2NDc=",
    "main_name": "青岛易航道物流科技有限公司", "invoice_apply_type": "1",
    "put_settle_object": "青岛易汇智供应链管理有限公司"}

INVOICE_ADD = [{
    "invoice_number": "25922000000029755889", "invoice_type": "1",
    "invoice_type_name": "增值税数电普通发票", "invoice_amount": "50000.00",
    "invoice_tax_amount": "0.00", "invoice_date": 1771603200,
    "currency": "CNY", "usd_amount": "", "invoice_exchange_rate": "1.0000",
    "invoice_original": {"file_id": "PLACEHOLDER_FID",
                         "file_name": "6a2925594f5ea.pdf", "file_type": "pdf",
                         "original_name": "电子发票（普通发票）5.pdf",
                         "file_url": "http://192.168.20.102:8001/file/o/MTA2NDc="},
    "buyer_chinese_header": "青岛易汇智供应链管理有限公司",
    "buyer_identifier_no": "91370202MAEWF5RN7G",
    "buyer_identity": "main", "isbuyer_identity": "main",
    "seller_chinese_header": "青岛易航道物流科技有限公司",
    "seller_identifier_no": "91370202MABU30PK3F",
    "seller_identity": "main", "invoice_image_name": "6a29255d33aca.png",
    "file_path": "http://192.168.20.102:8001/file/o/MTA2NDc="}]

ALLOC_INVOICE = {"receive_invoice_apply_id": "PLACEHOLDER_RIAPID",
                 "invoice_arr": [{"receive_invoice_id": "PLACEHOLDER_RINVID",
                                  "invoice_amount_use": "770.00"}],
                 "action": "check"}

# writeoff flow
PUT_ORDER_ITEM = {"order_no": "", "create_time": [1765296000000, 1781107199000],
                  "main_id": ["31"], "settle_object_id": ["37"],
                  "bl_nos": [BLNO], "sort_field": "order_create_time",
                  "sort_order": "desc", "params": {},
                  "create_time_start": "1765296000",
                  "create_time_end": "1781107199"}

FEE_CHECK = {"order_fee_real_ids": ["PLACEHOLDER_OFRID"]}
ORDER_FEE_PAGE = {"order_fee_real_ids": ["PLACEHOLDER_OFRID"]}

WRITEOFF_BODY = {
    "writeoff_object": [{"order_fee_real_id": "PLACEHOLDER_OFRID",
                         "un_writeoff_amount": "100.00",
                         "use_writeoff_amount": "0.00"}],
    "writeoff_name": "", "fee_match_type": "1", "writeoff_type": "1",
    "writeoff_mode": "order", "currency": "",
    "un_writeoff_amount_usd_total": "0.00",
    "un_writeoff_amount_cny_total": "0.00",
    "use_writeoff_amount_usd_total": "100.00",
    "use_writeoff_amount_cny_total": "0.00",
    "statement_amount_cny_total": "770.00",
    "statement_amount_usd_total": "0.00",
    "statement": [{"is_exchange": "", "statement_currency": "CNY",
                   "statement_amount": "770", "writeoff_amount_cny": "0.00",
                   "writeoff_amount_usd": "100.00", "exchange_rate": 7.7,
                   "ischangeRate": True, "main_bank_id": "10",
                   "receipt_time": 1781020800, "receipt_voucher": "",
                   "use_statement_amount_cny_total": None,
                   "use_statement_amount_usd_total": None}],
    "main_id": "1", "main_name": "青岛易航道物流科技有限公司",
    "select_node_user": []}

WRITEOFF_PAGE = {"page_no": 1, "page_size": 20,
                 "create_time": [1765296000000, 1781107199000],
                 "main_id": [], "receive_settle_object_id": [],
                 "bl_nos": [BLNO], "sort_field": "create_time",
                 "sort_order": "desc", "params": {},
                 "create_time_start": "1765296000",
                 "create_time_end": "1781107199"}

# ---------------------------------------------------------------------------
# 3. steps
# ---------------------------------------------------------------------------
steps = []

# ---- step 1: orderAdd check ----
body = dict(ORDER_INITIAL, action="check")
steps.append(step(api("/api/order/orderEntrust/orderAdd"), body,
                  [assert200("assert_status_200_step1", "订单创建检查应返回200"),
                   extract("extract_request_body_1", "$.request_body",
                            "request_body", scope=None)]))

# ---- step 2: orderAdd submit ----
body = dict(ORDER_INITIAL, action="submit")
steps.append(step(api("/api/order/orderEntrust/orderAdd"), body,
                  [assert200("assert_status_200_step2", "订单创建提交应返回200"),
                   extract("extract_response_body_2", "$.response_body",
                            "response_body", scope=None)]))

# ---- step 3: orderPage  (extract order_id + order_no) ----
steps.append(step(
    api("/api/order/orderEntrust/orderPage"),
    {"page_no": 1, "page_size": 20, "order_no": "", "customer_id": [],
     "bl_nos": [], "bl_no": BLNO, "sort_field": "update_time",
     "sort_order": "desc", "params": {}},
    [assert200("assert_status_200_step3", "查询订单分页应返回200"),
     extract("extract_order_id_3",
             "$.response_body.data.data[0].order_id", "order_id"),
     extract("extract_order_no_3",
             "$.response_body.data.data[0].order_no", "order_no",
             order=-1)]))

# ---- step 4: orderDetail (capture order_supplier_1_id, order_container_id, unique_id) ----
strat = [
    assert200("assert_status_200_step4", "查询订单详情应返回200"),
    assign("assign_order_id_4", "$.order_id", "$.request_body.order_id", 0),
    extract("extract_order_supplier_id_4",
            "$.response_body.data.supplier[0].order_supplier_id",
            "order_supplier_1_id", order=-1),
    extract("extract_order_container_id_4",
            "$.response_body.data.container[0].order_container_id",
            "order_container_id", order=-2),
    extract("extract_unique_id_4",
            "$.response_body.data.supplier[0].unique_id",
            "unique_id", order=-3),
]
steps.append(step(api("/api/order/order/orderDetail"), {"order_id": "PLACEHOLDER"},
                  strat))

# ---- step 5: distribute check (orderEntrust/orderAdd with full payload, action=check) ----
strat = [
    assert200("assert_status_200_step5", "分发检查应返回200"),
    assign("assign_order_id_5", "$.order_id", "$.request_body.order_id", 0),
    assign("assign_order_no_5", "$.order_no", "$.request_body.order_no", -1),
    assign("assign_order_supplier_id_5", "$.order_supplier_1_id",
            "$.request_body.supplier[0].order_supplier_id", -2),
    assign("assign_supplier_order_id_5", "$.order_id",
            "$.request_body.supplier[0].order_id", -3),
    assign("assign_container_id_5", "$.order_container_id",
            "$.request_body.container[0].order_container_id", -4),
    extract("extract_response_body_5", "$.response_body", "response_body",
            scope=None, order=-5),
]
body = dict(ORDER_DIST, action="check")
steps.append(step(api("/api/order/orderEntrust/orderAdd"), body, strat))

# ---- step 6: distribute submit (orderEntrust/orderAdd action=submit) ----
strat = [
    assert200("assert_status_200_step6", "分发提交应返回200"),
    assign("assign_order_id_6", "$.order_id", "$.request_body.order_id", 0),
    assign("assign_order_no_6", "$.order_no", "$.request_body.order_no", -1),
    assign("assign_order_supplier_id_6", "$.order_supplier_1_id",
            "$.request_body.supplier[0].order_supplier_id", -2),
    assign("assign_supplier_order_id_6", "$.order_id",
            "$.request_body.supplier[0].order_id", -3),
    assign("assign_container_id_6", "$.order_container_id",
            "$.request_body.container[0].order_container_id", -4),
    extract("extract_response_body_6", "$.response_body", "response_body",
            scope=None, order=-5),
]
body = dict(ORDER_DIST, action="submit")
steps.append(step(api("/api/order/orderEntrust/orderAdd"), body, strat))

# ---- step 7: orderAdd check (status=2) ----
strat = [
    assert200("assert_status_200_step7", "业务订单检查应返回200"),
    assign("assign_order_id_7", "$.order_id", "$.request_body.order_id", 0),
    assign("assign_order_no_7", "$.order_no", "$.request_body.order_no", -1),
    assign("assign_order_supplier_id_7", "$.order_supplier_1_id",
            "$.request_body.supplier[0].order_supplier_id", -2),
    assign("assign_supplier_order_id_7", "$.order_id",
            "$.request_body.supplier[0].order_id", -3),
    assign("assign_container_id_7", "$.order_container_id",
            "$.request_body.container[0].order_container_id", -4),
    extract("extract_response_body_7", "$.response_body", "response_body",
            scope=None, order=-5),
]
body = dict(ORDER_ADD2, action="check")
steps.append(step(api("/api/order/order/orderAdd"), body, strat))

# ---- step 8: orderBook (extract customer_file_list) ----
strat = [
    assert200("assert_status_200_step8", "托书确认应返回200"),
    assign("assign_order_id_8", "$.order_id", "$.request_body.order_id", 0),
    assign("assign_order_no_8", "$.order_no", "$.request_body.order_no", -1),
    assign("assign_order_supplier_id_8", "$.order_supplier_1_id",
            "$.request_body.supplier[0].order_supplier_id", -2),
    assign("assign_supplier_order_id_8", "$.order_id",
            "$.request_body.supplier[0].order_id", -3),
    assign("assign_container_id_8", "$.order_container_id",
            "$.request_body.container[0].order_container_id", -4),
    extract("extract_response_body_8", "$.response_body", "response_body",
            scope=None, order=-5),
    extract("extract_customer_file_list_8", "$.response_body.data",
            "customer_file_list", order=-6),
]
body = dict(ORDER_ADD2, action="check")
steps.append(step(api("/api/order/order/orderBook"), body, strat))

# ---- step 9: orderAdd submit (status=2) ----
strat = [
    assert200("assert_status_200_step9", "业务订单提交应返回200"),
    assign("assign_order_id_9", "$.order_id", "$.request_body.order_id", 0),
    assign("assign_order_no_9", "$.order_no", "$.request_body.order_no", -1),
    assign("assign_order_supplier_id_9", "$.order_supplier_1_id",
            "$.request_body.supplier[0].order_supplier_id", -2),
    assign("assign_supplier_order_id_9", "$.order_id",
            "$.request_body.supplier[0].order_id", -3),
    assign("assign_container_id_9", "$.order_container_id",
            "$.request_body.container[0].order_container_id", -4),
    assign("assign_customer_file_list_9", "$.customer_file_list",
            "$.request_body.customer_file_list", -5),
    extract("extract_response_body_9", "$.response_body", "response_body",
            scope=None, order=-6),
]
body = dict(ORDER_ADD2, action="submit")
steps.append(step(api("/api/order/order/orderAdd"), body, strat))

# ---- step 10: orderDetail again (capture order_sub_no, order_sub_id) ----
strat = [
    assert200("assert_status_200_step10", "查询订单详情应返回200"),
    assign("assign_order_id_10", "$.order_id", "$.request_body.order_id", 0),
    extract("extract_order_sub_no_10",
            "$.response_body.data.order_sub[0].order_sub_no", "order_sub_no",
            order=-1),
    extract("extract_order_sub_id_10",
            "$.response_body.data.order_sub[0].order_sub_id", "order_sub_id",
            order=-2),
    extract("extract_order_container_id_10b",
            "$.response_body.data.container[0].order_container_id",
            "order_container_id_2", order=-3),
    extract("extract_order_fee_real_id_10",
            "$.response_body.data.supplier[0].order_fee_real_id",
            "order_fee_real_id_2", order=-4),
    extract("extract_response_body_10", "$.response_body", "response_body",
            scope=None, order=-5),
]
steps.append(step(api("/api/order/order/orderDetail"), {"order_id": "PLACEHOLDER"},
                  strat))

# ---- step 11: bookRealAmountEdit check ----
strat = [
    assert200("assert_status_200_step11", "费用编辑检查应返回200"),
    assign("assign_order_id_11", "$.order_id", "$.request_body.order_id", 0),
    assign("assign_unique_id_11", "$.unique_id",
            "$.request_body.to_customer.put_amount.standard_list[0].unique_id", -1),
    assign("assign_unique_id_11b", "$.unique_id",
            "$.request_body.to_supplier.pay_amount.standard_list[0].unique_id", -2),
    extract("extract_response_body_11", "$.response_body", "response_body",
            scope=None, order=-3),
]
body = dict(FEE_EDIT_BODY, action="check")
steps.append(step(api("/api/order/orderFee/bookRealAmountEdit"), body, strat))

# ---- step 12: bookRealAmountEdit submit ----
strat = [
    assert200("assert_status_200_step12", "费用编辑提交应返回200"),
    assign("assign_order_id_12", "$.order_id", "$.request_body.order_id", 0),
    assign("assign_unique_id_12", "$.unique_id",
            "$.request_body.to_customer.put_amount.standard_list[0].unique_id", -1),
    assign("assign_unique_id_12b", "$.unique_id",
            "$.request_body.to_supplier.pay_amount.standard_list[0].unique_id", -2),
    extract("extract_response_body_12", "$.response_body", "response_body",
            scope=None, order=-3),
]
body = dict(FEE_EDIT_BODY, action="submit")
steps.append(step(api("/api/order/orderFee/bookRealAmountEdit"), body, strat))

# ---- step 13: toggleRealAmount (extract order_fee_real_id) ----
strat = [
    assert200("assert_status_200_step13", "费用详情查询应返回200"),
    assign("assign_order_id_13", "$.order_id", "$.request_body.order_id", 0),
    extract("extract_order_fee_real_id_13",
            "$.response_body.data.to_customer[0].put_amount.standard_list[0].order_fee_real_id",
            "order_fee_real_id", order=-1),
    extract("extract_response_body_13", "$.response_body", "response_body",
            scope=None, order=-2),
]
steps.append(step(api("/api/order/orderFee/toggleRealAmount"),
                  {"order_id": "PLACEHOLDER"}, strat))

# ---- step 14: checkGenerateOrderSub ----
strat = [
    assert200("assert_status_200_step14", "检查生成子订单应返回200"),
    assign("assign_order_id_14", "$.order_id", "$.request_body.order_id", 0),
    extract("extract_response_body_14", "$.response_body", "response_body",
            scope=None, order=-1),
]
steps.append(step(api("/api/order/order/checkGenerateOrderSub"),
                  {"order_id": "PLACEHOLDER"}, strat))

# ---- step 15: generateOrderSub ----
strat = [
    assert200("assert_status_200_step15", "生成子订单应返回200"),
    assign("assign_order_id_15", "$.order_id", "$.request_body.order_id", 0),
    extract("extract_response_body_15", "$.response_body", "response_body",
            scope=None, order=-1),
]
steps.append(step(api("/api/order/order/generateOrderSub"),
                  {"order_id": "PLACEHOLDER"}, strat))

# ---- step 16: realAmountLockSubmit check ----
strat = [
    assert200("assert_status_200_step16", "费用锁定校验应返回200"),
    assign("assign_order_id_16", "$.order_id", "$.request_body.order_id", 0),
    assign("assign_order_fee_real_id_16", "$.order_fee_real_id",
            "$.request_body.order_fee_real_ids[0]", -1),
    extract("extract_response_body_16", "$.response_body", "response_body",
            scope=None, order=-2),
]
body = {"action": "check", "order_id": "PLACEHOLDER",
        "order_fee_real_ids": ["PLACEHOLDER_OFRID"]}
steps.append(step(api("/api/order/orderFee/realAmountLockSubmit"), body, strat))

# ---- step 17: realAmountLockSubmit audit ----
strat = [
    assert200("assert_status_200_step17", "费用审批应返回200"),
    assign("assign_order_id_17", "$.order_id", "$.request_body.order_id", 0),
    assign("assign_order_fee_real_id_17", "$.order_fee_real_id",
            "$.request_body.order_fee_real_ids[0]", -1),
    extract("extract_response_body_17", "$.response_body", "response_body",
            scope=None, order=-2),
]
body = {"action": "audit", "order_id": "PLACEHOLDER",
        "order_fee_real_ids": ["PLACEHOLDER_OFRID"]}
steps.append(step(api("/api/order/orderFee/realAmountLockSubmit"), body, strat))

# ---- step 18: realAmountLockSubmit submit (uses order_sub_no in audit_msg.code) ----
strat = [
    assert200("assert_status_200_step18", "费用提交应返回200"),
    assign("assign_order_id_18", "$.order_id", "$.request_body.order_id", 0),
    assign("assign_order_fee_real_id_18", "$.order_fee_real_id",
            "$.request_body.order_fee_real_ids[0]", -1),
    assign("assign_order_sub_no_18", "$.order_sub_no",
            "$.request_body.audit_msg.code", -2),
    extract("extract_response_body_18", "$.response_body", "response_body",
            scope=None, order=-3),
]
body = {"action": "submit", "order_id": "PLACEHOLDER",
        "order_fee_real_ids": ["PLACEHOLDER_OFRID"],
        "audit_msg": {"title": "业务订单ID", "code": "PLACEHOLDER_OSUBNO",
                       "msgs": ["费用锁定申请"]},
        "select_node_user": [{"node_sort": "0", "user_id": "828"}]}
steps.append(step(api("/api/order/orderFee/realAmountLockSubmit"), body, strat))

# ---- step 19: auditRecord (extract audit_id) ----
strat = [
    assert200("assert_status_200_step19", "查询审批记录应返回200"),
    assign("assign_order_id_19", "$.order_id", "$.request_body.relation_id", 0),
    extract("extract_audit_id_19",
            "$.response_body.data[0].audit_id", "audit_id", order=-1),
    extract("extract_response_body_19", "$.response_body", "response_body",
            scope=None, order=-2),
]
steps.append(step(api("/api/home/audit/auditRecord"),
                  {"relation_id": "PLACEHOLDER", "type": "order"}, strat))

# ---- step 20: auditDetail ----
strat = [
    assert200("assert_status_200_step20", "查询审批详情应返回200"),
    assign("assign_audit_id_20", "$.audit_id", "$.request_body.audit_id", 0),
    extract("extract_response_body_20", "$.response_body", "response_body",
            scope=None, order=-1),
]
steps.append(step(api("/api/home/audit/auditDetail"),
                  {"audit_id": "PLACEHOLDER"}, strat))

# ---- step 21: auditExecute approve (audit_status=2) ----
strat = [
    assert200("assert_status_200_step21", "审批批准应返回200"),
    assign("assign_audit_id_21", "$.audit_id", "$.request_body.audit_ids[0]", 0),
    extract("extract_response_body_21", "$.response_body", "response_body",
            scope=None, order=-1),
]
steps.append(step(api("/api/home/audit/auditExecute"),
                  {"audit_ids": ["PLACEHOLDER_AUDIT"], "audit_status": 2,
                   "audit_remark": None}, strat))

# ---- step 22: orderConfirmAccount check ----
strat = [
    assert200("assert_status_200_step22", "对账确认应返回200"),
    assign("assign_order_id_22", "$.order_id", "$.request_body.order_id", 0),
    extract("extract_response_body_22", "$.response_body", "response_body",
            scope=None, order=-1),
]
steps.append(step(api("/api/order/order/orderConfirmAccount"),
                  {"order_id": "PLACEHOLDER", "action": "check"}, strat))

# ---- step 23: orderConfirmAccount submit (uses finance_ids / bank_ids - left as placeholders) ----
strat = [
    assert200("assert_status_200_step23", "对账结果提交应返回200"),
    assign("assign_order_id_23", "$.order_id", "$.request_body.order_id", 0),
    extract("extract_response_body_23", "$.response_body", "response_body",
            scope=None, order=-1),
]
body = {"action": "submit", "order_id": "PLACEHOLDER",
        "finance_ids": ["PLACEHOLDER_FINANCE"],
        "bank_ids": ["PLACEHOLDER_BANK"]}
steps.append(step(api("/api/order/order/orderConfirmAccount"), body, strat))

# ---- step 24: changeInvoiceApply check ----
strat = [
    assert200("assert_status_200_step24", "未放款开票申请检查应返回200"),
    assign("assign_order_id_24", "$.order_id", "$.request_body.order_ids[0]", 0),
    extract("extract_response_body_24", "$.response_body", "response_body",
            scope=None, order=-1),
]
body = dict(CHANGE_INVOICE, action="check")
steps.append(step(api("/api/order/order/changeInvoiceApply"), body, strat))

# ---- step 25: changeInvoiceApply audit ----
strat = [
    assert200("assert_status_200_step25", "未放款开票审批应返回200"),
    assign("assign_order_id_25", "$.order_id", "$.request_body.order_ids[0]", 0),
    extract("extract_response_body_25", "$.response_body", "response_body",
            scope=None, order=-1),
]
body = dict(CHANGE_INVOICE, action="audit")
steps.append(step(api("/api/order/order/changeInvoiceApply"), body, strat))

# ---- step 26: changeInvoiceApply submit ----
strat = [
    assert200("assert_status_200_step26", "未放款开票提交应返回200"),
    assign("assign_order_id_26", "$.order_id", "$.request_body.order_ids[0]", 0),
    extract("extract_response_body_26", "$.response_body", "response_body",
            scope=None, order=-1),
]
body = {"audit_note": "", "order_ids": ["PLACEHOLDER"], "action": "submit",
        "audit_msg": {"title": "业务订单ID", "code": "", "msgs": ["未放款开票申请"]},
        "select_node_user": [{"node_sort": "0", "user_id": "828"}]}
steps.append(step(api("/api/order/order/changeInvoiceApply"), body, strat))

# ---- step 27: auditRecord again (extract audit_id_2) ----
strat = [
    assert200("assert_status_200_step27", "查询审批记录应返回200"),
    assign("assign_order_id_27", "$.order_id", "$.request_body.relation_id", 0),
    extract("extract_audit_id_27",
            "$.response_body.data[0].audit_id", "audit_id_2", order=-1),
    extract("extract_response_body_27", "$.response_body", "response_body",
            scope=None, order=-2),
]
steps.append(step(api("/api/home/audit/auditRecord"),
                  {"relation_id": "PLACEHOLDER", "type": "order"}, strat))

# ---- step 28: auditExecute approve (audit_id_2) ----
strat = [
    assert200("assert_status_200_step28", "批准审批应返回200"),
    assign("assign_audit_id_28", "$.audit_id_2", "$.request_body.audit_ids[0]", 0),
    extract("extract_response_body_28", "$.response_body", "response_body",
            scope=None, order=-1),
]
steps.append(step(api("/api/home/audit/auditExecute"),
                  {"audit_ids": ["PLACEHOLDER_AUDIT2"], "audit_status": 2,
                   "audit_remark": None}, strat))

# ---- step 29: financePutList query (account) ----
strat = [
    assert200("assert_status_200_step29", "对账查询应返回200"),
    extract("extract_response_body_29", "$.response_body", "response_body",
            scope=None, order=-1),
]
steps.append(step(api("/api/finance/accountFee/financePutList"), FINPUTLIST_BODY,
                  strat))

# ---- step 30: orderReceiveAccountEdit check (uses order_sub_id, order_sub_no, order_fee_real_id) ----
strat = [
    assert200("assert_status_200_step30", "对账提交检查应返回200"),
    assign("assign_order_id_30", "$.order_id",
            "$.request_body.select_list[0].order_id", 0),
    assign("assign_order_no_30", "$.order_no",
            "$.request_body.select_list[0].order_no", -1),
    assign("assign_order_sub_id_30", "$.order_sub_id",
            "$.request_body.select_list[0].order_sub_id", -2),
    assign("assign_order_sub_no_30", "$.order_sub_no",
            "$.request_body.select_list[0].order_sub_no", -3),
    assign("assign_order_fee_real_id_30", "$.order_fee_real_id",
            "$.request_body.select_list[0].amount_list[0].order_fee_real_id", -4),
    extract("extract_response_body_30", "$.response_body", "response_body",
            scope=None, order=-5),
]
body = dict(RECEIVE_EDIT, action="check")
steps.append(step(api("/api/finance/receiveAccount/orderReceiveAccountEdit"), body,
                  strat))

# ---- step 31: orderReceiveAccountEdit submit ----
strat = [
    assert200("assert_status_200_step31", "对账提交应返回200"),
    assign("assign_order_id_31", "$.order_id",
            "$.request_body.select_list[0].order_id", 0),
    assign("assign_order_no_31", "$.order_no",
            "$.request_body.select_list[0].order_no", -1),
    assign("assign_order_sub_id_31", "$.order_sub_id",
            "$.request_body.select_list[0].order_sub_id", -2),
    assign("assign_order_sub_no_31", "$.order_sub_no",
            "$.request_body.select_list[0].order_sub_no", -3),
    assign("assign_order_fee_real_id_31", "$.order_fee_real_id",
            "$.request_body.select_list[0].amount_list[0].order_fee_real_id", -4),
    extract("extract_receive_account_id_31",
            "$.response_body.data.receive_account_id", "receive_account_id",
            order=-5),
    extract("extract_response_body_31", "$.response_body", "response_body",
            scope=None, order=-6),
]
body = dict(RECEIVE_EDIT, action="submit")
steps.append(step(api("/api/finance/receiveAccount/orderReceiveAccountEdit"), body,
                  strat))

# ---- step 32: receiveAccountDetail ----
strat = [
    assert200("assert_status_200_step32", "对账详情应返回200"),
    assign("assign_receive_account_id_32", "$.receive_account_id",
            "$.request_body.receive_account_id", 0),
    extract("extract_response_body_32", "$.response_body", "response_body",
            scope=None, order=-1),
]
steps.append(step(api("/api/finance/receiveAccount/receiveAccountDetail"),
                  {"receive_account_id": "PLACEHOLDER"}, strat))

# ---- step 33: receiveConfirmList ----
strat = [
    assert200("assert_status_200_step33", "对账查询2应返回200"),
    assign("assign_receive_account_id_33", "$.receive_account_id",
            "$.request_body.receive_account_id", 0),
    extract("extract_order_sub_id_33",
            "$.response_body.data[0].order_sub_id", "order_sub_id_2",
            order=-1),
    extract("extract_order_fee_real_id_33",
            "$.response_body.data[0].real_amount_ids[0]",
            "order_fee_real_id_2", order=-2),
    extract("extract_response_body_33", "$.response_body", "response_body",
            scope=None, order=-3),
]
steps.append(step(api("/api/finance/receiveAccount/receiveConfirmList"),
                  {"confirm_type": 0, "receive_account_id": "PLACEHOLDER",
                   "order_ids": []}, strat))

# ---- step 34: accountConfirm ----
strat = [
    assert200("assert_status_200_step34", "对账确认应返回200"),
    assign("assign_receive_account_id_34", "$.receive_account_id",
            "$.request_body.receive_account_id", 0),
    assign("assign_order_id_34", "$.order_id",
            "$.request_body.confirm_list[0].order_ids", -1),
    assign("assign_order_sub_id_34", "$.order_sub_id_2",
            "$.request_body.confirm_list[0].order_sub_ids", -2),
    assign("assign_unique_id_34", "$.unique_id",
            "$.request_body.confirm_list[0].unique_ids", -3),
    assign("assign_order_fee_real_id_34", "$.order_fee_real_id_2",
            "$.request_body.confirm_list[0].real_amount_ids[0]", -4),
    extract("extract_response_body_34", "$.response_body", "response_body",
            scope=None, order=-5),
]
body = dict(ACCOUNT_CONFIRM)
body["receive_account_id"] = "PLACEHOLDER"
steps.append(step(api("/api/finance/receiveAccount/accountConfirm"), body, strat))

# ---- step 35: financePutList (batch_type=1) ----
strat = [
    assert200("assert_status_200_step35", "开票批次管理应返回200"),
    extract("extract_response_body_35", "$.response_body", "response_body",
            scope=None, order=-1),
]
steps.append(step(api("/api/finance/accountFee/financePutList"),
                  INVOICE_BATCH_QUERY, strat))

# ---- step 36: checkStep1 ----
strat = [
    assert200("assert_status_200_step36", "开票批次检查1应返回200"),
    assign("assign_order_fee_real_id_36", "$.order_fee_real_id",
            "$.request_body.order_fee_real_id[0]", 0),
    assign("assign_order_sub_id_36", "$.order_sub_id",
            "$.request_body.order_sub_id[0]", -1),
    extract("extract_response_body_36", "$.response_body", "response_body",
            scope=None, order=-2),
]
body = dict(INVOICE_CHECK_STEP_BASE)
steps.append(step(api("/api/Finance/ReceiveInvoiceBatch/checkStep1"), body, strat))

# ---- step 37: checkStep2 ----
strat = [
    assert200("assert_status_200_step37", "开票批次检查2应返回200"),
    assign("assign_order_fee_real_id_37", "$.order_fee_real_id",
            "$.request_body.order_fee_real_id[0]", 0),
    assign("assign_order_sub_id_37", "$.order_sub_id",
            "$.request_body.order_sub_id[0]", -1),
    extract("extract_response_body_37", "$.response_body", "response_body",
            scope=None, order=-2),
]
body = dict(INVOICE_CHECK_STEP_BASE, turn_rate="7.7", rate_type="1",
            usd_is_turn="1")
steps.append(step(api("/api/Finance/ReceiveInvoiceBatch/checkStep2"), body, strat))

# ---- step 38: batchOrderEdit check ----
strat = [
    assert200("assert_status_200_step38", "开票提交检查应返回200"),
    assign("assign_order_fee_real_id_38", "$.order_fee_real_id",
            "$.request_body.order_fee_real_id[0]", 0),
    assign("assign_order_sub_id_38", "$.order_sub_id",
            "$.request_body.order_sub_id[0]", -1),
    extract("extract_response_body_38", "$.response_body", "response_body",
            scope=None, order=-2),
]
body = dict(INVOICE_CHECK_STEP_BASE, turn_rate="7.7", rate_type="1",
            usd_is_turn="1", action="check",
            fee_currency="USD", order_sub_customer_id=["16"])
steps.append(step(api("/api/Finance/ReceiveInvoiceBatch/batchOrderEdit"), body,
                  strat))

# ---- step 39: batchOrderEdit audit ----
strat = [
    assert200("assert_status_200_step39", "开票提交审批应返回200"),
    assign("assign_order_fee_real_id_39", "$.order_fee_real_id",
            "$.request_body.order_fee_real_id[0]", 0),
    assign("assign_order_sub_id_39", "$.order_sub_id",
            "$.request_body.order_sub_id[0]", -1),
    extract("extract_response_body_39", "$.response_body", "response_body",
            scope=None, order=-2),
]
body = dict(INVOICE_CHECK_STEP_BASE, turn_rate="7.7", rate_type="1",
            usd_is_turn="1", action="audit",
            fee_currency="USD", order_sub_customer_id=["16"])
steps.append(step(api("/api/Finance/ReceiveInvoiceBatch/batchOrderEdit"), body,
                  strat))

# ---- step 40: batchOrderEdit submit (extract receive_invoice_batch_id & receive_invoice_apply_id) ----
strat = [
    assert200("assert_status_200_step40", "开票提交应返回200"),
    assign("assign_order_fee_real_id_40", "$.order_fee_real_id",
            "$.request_body.order_fee_real_id[0]", 0),
    assign("assign_order_sub_id_40", "$.order_sub_id",
            "$.request_body.order_sub_id[0]", -1),
    extract("extract_receive_invoice_batch_id_40",
            "$.response_body.data.receive_invoice_batch_id",
            "receive_invoice_batch_id", order=-2),
    extract("extract_receive_invoice_apply_id_40",
            "$.response_body.data.receive_invoice_apply_id",
            "receive_invoice_apply_id", order=-3),
    extract("extract_response_body_40", "$.response_body", "response_body",
            scope=None, order=-4),
]
body = dict(INVOICE_CHECK_STEP_BASE, turn_rate="7.7", rate_type="1",
            usd_is_turn="1", action="submit",
            fee_currency="USD", order_sub_customer_id=["16"],
            audit_msg={"title": "开票批次ID", "code": None,
                        "msgs": ["应收开票批次申请"]},
            select_node_user=[])
steps.append(step(api("/api/Finance/ReceiveInvoiceBatch/batchOrderEdit"), body,
                  strat))

# ---- step 41: applyPage query ----
strat = [
    assert200("assert_status_200_step41", "查询开票应返回200"),
    extract("extract_response_body_41", "$.response_body", "response_body",
            scope=None, order=-1),
]
steps.append(step(api("/api/Finance/ReceiveInvoiceBatch/applyPage"),
                  INVOICE_APPLY_PAGE, strat))

# ---- step 42: batchDetail (uses receive_invoice_batch_id) ----
strat = [
    assert200("assert_status_200_step42", "查询开票详情应返回200"),
    assign("assign_receive_invoice_batch_id_42", "$.receive_invoice_batch_id",
            "$.request_body.receive_invoice_batch_id", 0),
    extract("extract_response_body_42", "$.response_body", "response_body",
            scope=None, order=-1),
]
steps.append(step(api("/api/Finance/ReceiveInvoiceBatch/batchDetail"),
                  {"receive_invoice_batch_id": "PLACEHOLDER"}, strat))

# ---- step 43: applyDetail (uses receive_invoice_apply_id) ----
strat = [
    assert200("assert_status_200_step43", "查询开票申请详情应返回200"),
    assign("assign_receive_invoice_apply_id_43", "$.receive_invoice_apply_id",
            "$.request_body.receive_invoice_apply_id", 0),
    extract("extract_response_body_43", "$.response_body", "response_body",
            scope=None, order=-1),
]
steps.append(step(api("/api/Finance/ReceiveInvoiceBatch/applyDetail"),
                  {"receive_invoice_apply_id": "PLACEHOLDER"}, strat))

# ---- step 44: invoiceAddCheck (extract file_id) ----
strat = [
    assert200("assert_status_200_step44", "上传发票确认应返回200"),
    extract("extract_file_id_44",
            "$.response_body.data.file_id", "file_id", order=-1),
    extract("extract_response_body_44", "$.response_body", "response_body",
            scope=None, order=-2),
]
steps.append(step(api("/api/finance/receiveInvoice/invoiceAddCheck"),
                  INVOICE_ADD_CHECK, strat))

# ---- step 45: invoiceAdd (extract receive_invoice_id) ----
strat = [
    assert200("assert_status_200_step45", "发票添加应返回200"),
    assign("assign_file_id_45", "$.file_id",
            "$.request_body[0].invoice_original.file_id", 0),
    extract("extract_receive_invoice_id_45",
            "$.response_body.data[0].receive_invoice_id", "receive_invoice_id",
            order=-1),
    extract("extract_response_body_45", "$.response_body", "response_body",
            scope=None, order=-2),
]
body = json.loads(json.dumps(INVOICE_ADD))  # deep copy
body[0]["invoice_original"]["file_id"] = "PLACEHOLDER_FID"
steps.append(step(api("/api/finance/receiveInvoice/invoiceAdd"), body, strat))

# ---- step 46: allocationInvoiceFee check ----
strat = [
    assert200("assert_status_200_step46", "提交检查应返回200"),
    assign("assign_receive_invoice_apply_id_46", "$.receive_invoice_apply_id",
            "$.request_body.receive_invoice_apply_id", 0),
    assign("assign_receive_invoice_id_46", "$.receive_invoice_id",
            "$.request_body.invoice_arr[0].receive_invoice_id", -1),
    extract("extract_response_body_46", "$.response_body", "response_body",
            scope=None, order=-2),
]
body = {"receive_invoice_apply_id": "PLACEHOLDER",
        "invoice_arr": [{"receive_invoice_id": "PLACEHOLDER_RINVID",
                          "invoice_amount_use": "770.00"}],
        "action": "check"}
steps.append(step(api("/api/Finance/ReceiveInvoiceBatch/allocationInvoiceFee"),
                  body, strat))

# ---- step 47: allocationInvoiceFee submit ----
strat = [
    assert200("assert_status_200_step47", "提交确认应返回200"),
    assign("assign_receive_invoice_apply_id_47", "$.receive_invoice_apply_id",
            "$.request_body.receive_invoice_apply_id", 0),
    assign("assign_receive_invoice_id_47", "$.receive_invoice_id",
            "$.request_body.invoice_arr[0].receive_invoice_id", -1),
    extract("extract_response_body_47", "$.response_body", "response_body",
            scope=None, order=-2),
]
body = {"receive_invoice_apply_id": "PLACEHOLDER",
        "invoice_arr": [{"receive_invoice_id": "PLACEHOLDER_RINVID",
                          "invoice_amount_use": "770.00"}],
        "action": "submit"}
steps.append(step(api("/api/Finance/ReceiveInvoiceBatch/allocationInvoiceFee"),
                  body, strat))

# ---- step 48: putOrderItem (verification query) ----
strat = [
    assert200("assert_status_200_step48", "核销查询提单明细应返回200"),
    extract("extract_response_body_48", "$.response_body", "response_body",
            scope=None, order=-1),
]
steps.append(step(api("/api/order/orderFee/putOrderItem"), PUT_ORDER_ITEM, strat))

# ---- step 49: feeWriteoffCheck ----
strat = [
    assert200("assert_status_200_step49", "费用检查应返回200"),
    assign("assign_order_fee_real_id_49", "$.order_fee_real_id",
            "$.request_body.order_fee_real_ids[0]", 0),
    extract("extract_response_body_49", "$.response_body", "response_body",
            scope=None, order=-1),
]
steps.append(step(api("/api/finance/receiveWriteoff/feeWriteoffCheck"),
                  {"order_fee_real_ids": ["PLACEHOLDER_OFRID"]}, strat))

# ---- step 50: orderFeePage ----
strat = [
    assert200("assert_status_200_step50", "核销处理应返回200"),
    assign("assign_order_fee_real_id_50", "$.order_fee_real_id",
            "$.request_body.order_fee_real_ids[0]", 0),
    extract("extract_response_body_50", "$.response_body", "response_body",
            scope=None, order=-1),
]
steps.append(step(api("/api/finance/receiveWriteoff/orderFeePage"),
                  {"order_fee_real_ids": ["PLACEHOLDER_OFRID"]}, strat))

# ---- step 51: writeoffBatch check ----
strat = [
    assert200("assert_status_200_step51", "提交核销检查应返回200"),
    assign("assign_order_fee_real_id_51", "$.order_fee_real_id",
            "$.request_body.writeoff_object[0].order_fee_real_id", 0),
    extract("extract_response_body_51", "$.response_body", "response_body",
            scope=None, order=-1),
]
body = dict(WRITEOFF_BODY, action="check")
steps.append(step(api("/api/finance/receiveWriteoff/writeoffBatch"), body, strat))

# ---- step 52: writeoffBatch submit ----
strat = [
    assert200("assert_status_200_step52", "提交核销应返回200"),
    assign("assign_order_fee_real_id_52", "$.order_fee_real_id",
            "$.request_body.writeoff_object[0].order_fee_real_id", 0),
    extract("extract_response_body_52", "$.response_body", "response_body",
            scope=None, order=-1),
]
body = dict(WRITEOFF_BODY, action="submit")
steps.append(step(api("/api/finance/receiveWriteoff/writeoffBatch"), body, strat))

# ---- step 53: writeoffPage ----
strat = [
    assert200("assert_status_200_step53", "查询核销记录应返回200"),
    extract("extract_response_body_53", "$.response_body", "response_body",
            scope=None, order=-1),
]
steps.append(step(api("/api/finance/receiveWriteoff/writeoffPage"),
                  WRITEOFF_PAGE, strat))

# ---------------------------------------------------------------------------
# 4. final scenario
# ---------------------------------------------------------------------------
scenario = {
    "kind": "scenario",
    "scenarioId": "e2e订单到应收核销_full",
    "meta": {
        "name": "订单到应收核销-全流程数据驱动",
        "description": (
            "基于 order.md (56 个业务接口) 完整数据驱动还原:委托新建→分发→业务订单→托书→费用编辑→锁定→审批→对账→未放款开票→对账→开票批次→上传发票→核销。 "
            "bl_no 由 config.vars 注入,其余动态 ID 通过 extract(scope=scenario) 一次捕获、assign 按 order 索引注入下游请求体。"
        ),
        "module": "settlement",
        "priority": 1,
        "author": "codfish",
        "owner": "codfish",
        "tags": ["smoke", "settlement", "e2e", "datadriven"],
        "version": "1.0.0",
        "createTime": "2026-06-21T10:00:00",
        "expire": False,
        "requirementRef": [],
    },
    "config": {
        "setup": [],
        "teardown": [],
        "services": {"tidb-test-service": "https://fin-tidb.21eflag.com/"},
        "vars": {"bl_no": "codfishE2E_FULL_001"},
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

out_path = os.path.join(os.path.dirname(__file__), "e2e_full.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(scenario, f, ensure_ascii=False, indent=2)
print(f"wrote {out_path} with {len(steps)} steps")
