# 对照报告(生成 vs 手建 ground truth)

## fin.audit.audit_detail

- missing(1):
  - [capture](1): audit_id

## fin.audit.audit_execute

- missing(3):
  - [capture](3): audit_ids, audit_status, audit_remark

## fin.audit.audit_page

- missing(6):
  - [capture](6): page_no, page_size, active_tab, sort_field, sort_order, params

## fin.customer.part

- missing(1):
  - [capture](1): customer_id

## fin.customer.policy

- missing(2):
  - [capture](2): customer_id, status

## fin.order.check_generate_order_sub

- missing(1):
  - [capture](1): order_id

## fin.order.generate_order_sub

- missing(1):
  - [capture](1): order_id

## fin.order.order_add

- missing(240):
  - [capture](240): bl_no, order_id, order_no, track_bl_no, entrust_status, action, customer_file_list, order_file, client_expand_name, m_delivery_type, customer_id, customer_name, service_id, service_name, sale_id, sale_name, operator_id, operator_name, customer_contact_id, customer_contact_name, main_sort, policy_id, policy_name, policy_type, settle_type, settle_type_name, customer_product_id, product_name, deposit_type, deposit_type_name, period_delay_type, period_delay_type_name, service_items, business_type, trade_term, carrier, carrier_id, etd, atd, ship_name, voy, pol, pot, pod, del, country_name, airline_type, ocean_type, terms_payment, terms_transport, pay_type, customer_order_sn, terms_shipment, shipper, consignee, notifier, ship_mark, commodity, notes, cargo_type, packer, num, gross_weight, bulk, sea_trans_cost, teu, volume, volume_desc, order_sn, status, sea_trans_currency, message_board, supplier, container, customer_category, customer_tax_number, customer_address_cn, client_expand_id, customer_contact_phone, customer_main_id, customer_main_name, business_main_id, business_main_name, fund_code, fund_name, track_atd, track_eta, track_ata, track_stcs, track_ship_name, track_voy, finance_date, pol_cn, pol_country_id, pol_country, pol_country_cn, pod_cn, pot_cn, del_cn, country_id, country_name_cn, customer_period, customer_settlement_date, period_rule, term_rule_name, customer_due_date, customer_put_date, customer_payment_collection_date, customer_put_date_manual, customer_put_writeoff_date, supplier_due_date, discount_start, discount_rule, discount_end, discount_ratio, discount_status, discount_currency, book_upload_date, trans_cost_put_preserve_date, bl_no_upload_date, supplier_invoice_date, supplier_invoice_taketime, real_cost_date, customer_invoice_request_date, first_financing_doc_ok_date, second_financing_doc_ok_date, insurance_doc_ok_date, customer_confirm_date, is_delayed_recovery, delayed_recovery_usd, delayed_recovery_cny, delayed_time, expect_fee_status, real_fee_status, fee_lock_status, pay_account_status, account_status, real_pay_usd, real_pay_cny, real_put_usd, real_put_cny, real_put_discount_rate, exchange_rate, folde_pay_usd, folde_put_usd, folde_pay_total, folde_put_total, gross_margin, gross_margin_rate, is_special_pay, is_loan_before_invoice, is_fee_miss, fee_miss_name, cancel_remark, cancel_time, effective_id, effective_by, effective_time, create_id, create_by, create_time, update_id, update_by, update_time, delete_time, business_time, main_ids, reverse_status, proprietary_business_status, loan_status, first_status, second_status, loan_pay_status, change_type, copy_order_id, real_fee_locked, is_usd_project, pay_status, is_sync_es, expect_discount_status, real_discount_status, remark, audit_type, is_system_generate, is_financing, confirm_status, is_traverse, financing_apply_amount, financing_apply_amount_cny, financing_apply_amount_usd, sys_upttime, receive_time_limit, customer_put_date_desc, deposit_refund_day, deposit_settlement_date, deposit_refund_month, payment_type, product_id, revoke_status, revoke_type, asset_status, revoke_failure_reason, repayment_date, repay_warn_time, reverse_status_name, is_delayed_recovery_name, order_finance_arr, order_main_bank_arr, order_sub, order_sub_no, service_project, service_project_amount, finance_status, main_ids_name, policy_main_arr, policy_type_name, business_type_name, cargo_type_name, period_rule_name, trade_term_name, carrier_name, terms_transport_name, terms_payment_name, pay_type_name, m_delivery_type_name, payment_type_name, audit, enable, policy_match, policy_match_name, real_discount_status_name, expect_discount_status_name, expect_policy_status_name, policy_status_name, subsidy_category_name, expect_subsidy_category_name, real_subsidy_category_name, revoke_status_name, revoke_type_name, asset_status_name

## fin.order.order_add_demo

- missing(240):
  - [capture](240): bl_no, order_id, order_no, track_bl_no, entrust_status, action, customer_file_list, order_file, client_expand_name, m_delivery_type, customer_id, customer_name, service_id, service_name, sale_id, sale_name, operator_id, operator_name, customer_contact_id, customer_contact_name, main_sort, policy_id, policy_name, policy_type, settle_type, settle_type_name, customer_product_id, product_name, deposit_type, deposit_type_name, period_delay_type, period_delay_type_name, service_items, business_type, trade_term, carrier, carrier_id, etd, atd, ship_name, voy, pol, pot, pod, del, country_name, airline_type, ocean_type, terms_payment, terms_transport, pay_type, customer_order_sn, terms_shipment, shipper, consignee, notifier, ship_mark, commodity, notes, cargo_type, packer, num, gross_weight, bulk, sea_trans_cost, teu, volume, volume_desc, order_sn, status, sea_trans_currency, message_board, supplier, container, customer_category, customer_tax_number, customer_address_cn, client_expand_id, customer_contact_phone, customer_main_id, customer_main_name, business_main_id, business_main_name, fund_code, fund_name, track_atd, track_eta, track_ata, track_stcs, track_ship_name, track_voy, finance_date, pol_cn, pol_country_id, pol_country, pol_country_cn, pod_cn, pot_cn, del_cn, country_id, country_name_cn, customer_period, customer_settlement_date, period_rule, term_rule_name, customer_due_date, customer_put_date, customer_payment_collection_date, customer_put_date_manual, customer_put_writeoff_date, supplier_due_date, discount_start, discount_rule, discount_end, discount_ratio, discount_status, discount_currency, book_upload_date, trans_cost_put_preserve_date, bl_no_upload_date, supplier_invoice_date, supplier_invoice_taketime, real_cost_date, customer_invoice_request_date, first_financing_doc_ok_date, second_financing_doc_ok_date, insurance_doc_ok_date, customer_confirm_date, is_delayed_recovery, delayed_recovery_usd, delayed_recovery_cny, delayed_time, expect_fee_status, real_fee_status, fee_lock_status, pay_account_status, account_status, real_pay_usd, real_pay_cny, real_put_usd, real_put_cny, real_put_discount_rate, exchange_rate, folde_pay_usd, folde_put_usd, folde_pay_total, folde_put_total, gross_margin, gross_margin_rate, is_special_pay, is_loan_before_invoice, is_fee_miss, fee_miss_name, cancel_remark, cancel_time, effective_id, effective_by, effective_time, create_id, create_by, create_time, update_id, update_by, update_time, delete_time, business_time, main_ids, reverse_status, proprietary_business_status, loan_status, first_status, second_status, loan_pay_status, change_type, copy_order_id, real_fee_locked, is_usd_project, pay_status, is_sync_es, expect_discount_status, real_discount_status, remark, audit_type, is_system_generate, is_financing, confirm_status, is_traverse, financing_apply_amount, financing_apply_amount_cny, financing_apply_amount_usd, sys_upttime, receive_time_limit, customer_put_date_desc, deposit_refund_day, deposit_settlement_date, deposit_refund_month, payment_type, product_id, revoke_status, revoke_type, asset_status, revoke_failure_reason, repayment_date, repay_warn_time, reverse_status_name, is_delayed_recovery_name, order_finance_arr, order_main_bank_arr, order_sub, order_sub_no, service_project, service_project_amount, finance_status, main_ids_name, policy_main_arr, policy_type_name, business_type_name, cargo_type_name, period_rule_name, trade_term_name, carrier_name, terms_transport_name, terms_payment_name, pay_type_name, m_delivery_type_name, payment_type_name, audit, enable, policy_match, policy_match_name, real_discount_status_name, expect_discount_status_name, expect_policy_status_name, policy_status_name, subsidy_category_name, expect_subsidy_category_name, real_subsidy_category_name, revoke_status_name, revoke_type_name, asset_status_name

## fin.order.order_book

- missing(240):
  - [capture](240): bl_no, order_id, order_no, track_bl_no, entrust_status, action, customer_file_list, client_expand_name, m_delivery_type, customer_id, customer_name, service_id, service_name, sale_id, sale_name, operator_id, operator_name, customer_contact_id, customer_contact_name, main_sort, policy_id, policy_name, policy_type, settle_type, settle_type_name, customer_product_id, product_name, deposit_type, deposit_type_name, period_delay_type, period_delay_type_name, service_items, business_type, trade_term, carrier, carrier_id, etd, atd, ship_name, voy, pol, pot, pod, del, country_name, airline_type, ocean_type, terms_payment, terms_transport, pay_type, customer_order_sn, terms_shipment, shipper, consignee, notifier, ship_mark, commodity, notes, cargo_type, packer, num, gross_weight, bulk, sea_trans_cost, teu, volume, volume_desc, order_sn, status, sea_trans_currency, message_board, supplier, container, customer_category, customer_tax_number, customer_address_cn, client_expand_id, customer_contact_phone, customer_main_id, customer_main_name, business_main_id, business_main_name, fund_code, fund_name, track_atd, track_eta, track_ata, track_stcs, track_ship_name, track_voy, finance_date, pol_cn, pol_country_id, pol_country, pol_country_cn, pod_cn, pot_cn, del_cn, country_id, country_name_cn, customer_period, customer_settlement_date, period_rule, term_rule_name, customer_due_date, customer_put_date, customer_payment_collection_date, customer_put_date_manual, customer_put_writeoff_date, supplier_due_date, discount_start, discount_rule, discount_end, discount_ratio, discount_status, discount_currency, book_upload_date, trans_cost_put_preserve_date, bl_no_upload_date, supplier_invoice_date, supplier_invoice_taketime, real_cost_date, customer_invoice_request_date, first_financing_doc_ok_date, second_financing_doc_ok_date, insurance_doc_ok_date, customer_confirm_date, is_delayed_recovery, delayed_recovery_usd, delayed_recovery_cny, delayed_time, expect_fee_status, real_fee_status, fee_lock_status, pay_account_status, account_status, real_pay_usd, real_pay_cny, real_put_usd, real_put_cny, real_put_discount_rate, exchange_rate, folde_pay_usd, folde_put_usd, folde_pay_total, folde_put_total, gross_margin, gross_margin_rate, is_special_pay, is_loan_before_invoice, is_fee_miss, fee_miss_name, cancel_remark, cancel_time, effective_id, effective_by, effective_time, create_id, create_by, create_time, update_id, update_by, update_time, delete_time, business_time, main_ids, reverse_status, proprietary_business_status, loan_status, first_status, second_status, loan_pay_status, change_type, copy_order_id, real_fee_locked, is_usd_project, pay_status, is_sync_es, expect_discount_status, real_discount_status, remark, audit_type, is_system_generate, is_financing, confirm_status, is_traverse, financing_apply_amount, financing_apply_amount_cny, financing_apply_amount_usd, sys_upttime, receive_time_limit, customer_put_date_desc, deposit_refund_day, deposit_settlement_date, deposit_refund_month, payment_type, product_id, revoke_status, revoke_type, asset_status, revoke_failure_reason, repayment_date, repay_warn_time, reverse_status_name, is_delayed_recovery_name, order_finance_arr, order_main_bank_arr, order_sub, order_sub_no, service_project, service_project_amount, finance_status, main_ids_name, policy_main_arr, policy_type_name, business_type_name, cargo_type_name, period_rule_name, trade_term_name, carrier_name, terms_transport_name, terms_payment_name, pay_type_name, m_delivery_type_name, payment_type_name, audit, enable, policy_match, policy_match_name, real_discount_status_name, expect_discount_status_name, expect_policy_status_name, policy_status_name, subsidy_category_name, expect_subsidy_category_name, real_subsidy_category_name, revoke_status_name, revoke_type_name, asset_status_name, order_file

## fin.order.order_detail

- missing(1):
  - [capture](1): order_id

## fin.order.order_notice

- missing(4):
  - [capture](4): order_id, action, finance_ids, bank_ids

## fin.order.order_page

- missing(7):
  - [capture](7): bl_no, order_no, page_no, page_size, sort_field, sort_order, params

## fin.order_entrust.order_add

- missing(6):
  - [FE](2): payment_type_name, policy_type_name
  - [capture](4): pot_port_name, pol_port_name, del_port_name, pod_port_name
- extra(156): is_usd_project, order_module, order_no, customer_product_id, service_project, order_id, book_supplier_id, book_user_id, bill_supplier_id, bill_user_id, manifest_supplier_id, manifest_user_id, insurance_supplier_id, insurance_user_id, bl_nos, order_sub_no, customer_main_id, business_main_id, supplier_id, customer_period, customer_put_date, book_supplier_period, book_supplier_pay_date, atd_time, finance_time, currency, fee_type, cost_ids, track_bl_nos, business_no, put_settle_object_id, main_id, pay_settle_object_id, real_fee_status, fee_lock_status, finance_date, is_loan_before_invoice, is_special_pay, create_id, put_account_status, put_invoice_status, put_writeoff_status, pay_account_status, pay_invoice_status, pay_writeoff_status, pay_account_no, account_batch_name, account_simple_name, account_status, batch_identity, main_batch_no, account_by, account_time, receive_account_no, order_self_id, self_status, customerData, oldSupplierMap, customer_category, customer_tax_number, customer_address_cn, customer_contact_phone, customer_main_name, business_main_name, fund_code, fund_name, track_atd, track_eta, track_ata, track_stcs, track_ship_name, track_voy, customer_settlement_date, period_rule, term_rule_name, customer_due_date, customer_payment_collection_date, customer_put_date_manual, customer_put_writeoff_date, supplier_due_date, discount_start, discount_rule, discount_end, discount_ratio, discount_status, discount_currency, book_upload_date, trans_cost_put_preserve_date, bl_no_upload_date, supplier_invoice_date, supplier_invoice_taketime, real_cost_date, customer_invoice_request_date, first_financing_doc_ok_date, second_financing_doc_ok_date, insurance_doc_ok_date, customer_confirm_date, is_delayed_recovery, delayed_recovery_usd, delayed_recovery_cny, delayed_time, expect_fee_status, real_pay_usd, real_pay_cny, real_put_usd, real_put_cny, real_put_discount_rate, exchange_rate, folde_pay_usd, folde_put_usd, folde_pay_total, folde_put_total, gross_margin, gross_margin_rate, is_fee_miss, fee_miss_name, cancel_remark, cancel_time, effective_id, effective_by, effective_time, create_by, update_id, update_by, delete_time, business_time, reverse_status, proprietary_business_status, loan_status, first_status, second_status, loan_pay_status, change_type, copy_order_id, real_fee_locked, pay_status, is_sync_es, expect_discount_status, real_discount_status, audit_type, is_system_generate, is_financing, confirm_status, is_traverse, financing_apply_amount, financing_apply_amount_cny, financing_apply_amount_usd, sys_upttime, customer_put_date_desc, deposit_refund_month, revoke_status, revoke_type, asset_status, revoke_failure_reason, repayment_date, repay_warn_time
| 键 | 手建 | 生成 |
|---|---|---|
| bl_no | 手建 state=form required=False ui=text zh='' enum=None vs=('pending_orders', 'bl_no') | 生成 state=carry required=False ui=text zh='提单号' enum=None vs=('pending_orders', 'bl_no') |
| track_bl_no | 手建 state=form required=False ui=text zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='提单号' enum=None vs=None |
| action | 手建 state=form required=False ui=text zh='check[校验]/submit[提交]' enum=['check', 'submit'] vs=None | 生成 state=form required=False ui=select zh='操作' enum=['check', 'submit'] vs=None |
| client_expand_name | 手建 state=carry required=False ui=unknown zh='' enum=None vs=('customer_part', 'handover_form.client_expand_name') | 生成 state=carry required=False ui=text zh='直客拓展用户名称' enum=None vs=None |
| client_expand_id | 手建 state=carry required=False ui=unknown zh='' enum=None vs=('customer_part', 'handover_form.client_expand_id') | 生成 state=form required=False ui=number zh='直客拓展' enum=None vs=None |
| m_delivery_type | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='M放货方式' enum=None vs=None |
| customer_id | 手建 state=carry required=False ui=unknown zh='' enum=None vs=('customer_list', 'customer_id') | 生成 state=form required=False ui=select zh='客户ID' enum=None vs=None |
| customer_name | 手建 state=carry required=False ui=unknown zh='' enum=None vs=('customer_list', 'customer_name') | 生成 state=carry required=False ui=text zh='下单客户名称' enum=None vs=None |
| receive_time_limit | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=number zh='回款时效' enum=None vs=None |
| deposit_refund_day | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=number zh='保证金退还周期' enum=None vs=None |
| deposit_settlement_date | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=number zh='保证金结算日' enum=None vs=None |
| service_id | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=form required=False ui=number zh='客服ID' enum=None vs=None |
| service_name | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='客服' enum=None vs=None |
| sale_id | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=form required=False ui=number zh='销售ID' enum=None vs=None |
| sale_name | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='销售' enum=None vs=None |
| operator_id | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=form required=False ui=number zh='操作ID' enum=None vs=None |
| operator_name | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='操作人' enum=None vs=None |
| customer_contact_id | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=number zh='客户联系人id' enum=None vs=None |
| customer_contact_name | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='联系人' enum=None vs=None |
| main_sort | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='主体顺序' enum=None vs=None |
| policy_id | 手建 state=carry required=False ui=unknown zh='' enum=None vs=('customer_policy', 'policy_id') | 生成 state=form required=False ui=number zh='服务策略ID' enum=None vs=None |
| policy_name | 手建 state=carry required=False ui=unknown zh='' enum=None vs=('customer_policy', 'policy_name') | 生成 state=carry required=False ui=text zh='服务策略名字' enum=None vs=('customer_policy', 'policy_name') |
| policy_type | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=form required=False ui=text zh='政策类型' enum=None vs=None |
| settle_type | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=form required=False ui=number zh='结算方式' enum=None vs=None |
| settle_type_name | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='结算方式名称' enum=None vs=None |
| product_id | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=number zh='客户产品ID' enum=None vs=None |
| product_name | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='客户产品名称' enum=None vs=None |
| deposit_type | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=number zh='保证金类型  1有 2无' enum=None vs=None |
| deposit_type_name | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='' enum=None vs=None |
| period_delay_type | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=number zh='客户账期类型' enum=None vs=None |
| period_delay_type_name | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='客户账期类型名称' enum=None vs=None |
| service_items | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=form required=False ui=unknown zh='服务项目' enum=None vs=None |
| business_type | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='业务类型' enum=None vs=None |
| trade_term | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=form required=False ui=text zh='成交方式' enum=None vs=None |
| carrier | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='船公司/承运人' enum=None vs=None |
| carrier_id | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=number zh='船公司  / 承运人ID' enum=None vs=None |
| etd | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=number zh='预计开航日' enum=None vs=None |
| atd | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=form required=False ui=number zh='实际开航日' enum=None vs=None |
| ship_name | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='船名' enum=None vs=None |
| voy | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='航次' enum=None vs=None |
| pol | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='起运港' enum=None vs=None |
| pot | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='中转港' enum=None vs=None |
| pod | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='卸货港' enum=None vs=None |
| del | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='目的地' enum=None vs=None |
| country_name | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='卸货港国家' enum=None vs=None |
| airline_type | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=form required=False ui=text zh='航线分类' enum=None vs=None |
| ocean_type | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='远洋/近洋' enum=None vs=None |
| terms_payment | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='结汇方式' enum=None vs=None |
| terms_transport | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='运输条款' enum=None vs=None |
| pay_type | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='付款方式' enum=None vs=None |
| customer_order_sn | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='客户单号' enum=None vs=None |
| terms_shipment | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='装运条款' enum=None vs=None |
| shipper | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='发货人' enum=None vs=None |
| consignee | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='收货人' enum=None vs=None |
| notifier | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='通知人' enum=None vs=None |
| ship_mark | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='唛头' enum=None vs=None |
| commodity | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=textarea zh='品名' enum=None vs=None |
| notes | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='托书备注' enum=None vs=None |
| cargo_type | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='货物类型' enum=None vs=None |
| packer | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='包装' enum=None vs=None |
| num | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=number zh='件数' enum=None vs=None |
| gross_weight | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=number zh='毛重' enum=None vs=None |
| bulk | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=number zh='体积' enum=None vs=None |
| sea_trans_cost | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=number zh='结算海运费' enum=None vs=None |
| teu | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='折TEU' enum=None vs=None |
| volume | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='箱型箱量' enum=None vs=None |
| volume_desc | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=form required=False ui=text zh='箱型箱量描述' enum=None vs=None |
| order_sn | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='' enum=None vs=None |
| status | 手建 state=form required=False ui=unknown zh='' enum=None vs=None | 生成 state=form required=False ui=select zh='订单状态' enum=None vs=None |
| sea_trans_currency | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='海运费币制' enum=None vs=None |
| container | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=form required=False ui=text zh='箱型' enum=None vs=None |
| message_board | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='' enum=None vs=None |
| customer_file_list | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=file zh='' enum=None vs=None |
| supplier | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=form required=False ui=unknown zh='' enum=None vs=None |
| remark | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='备注' enum=None vs=None |
| payment_type | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=number zh='付款类型 1确定性付款 2非确定性付款' enum=None vs=None |
| main_ids | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='主体顺序ID' enum=None vs=None |
| pot_cn | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='中转港-中文' enum=None vs=None |
| pol_cn | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='起运港-中文' enum=None vs=None |
| pol_country_id | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=number zh='起运港国家ID' enum=None vs=None |
| pol_country | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='起运港国家' enum=None vs=None |
| pol_country_cn | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='起运港国家-中文' enum=None vs=None |
| del_cn | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='目的港-中文' enum=None vs=None |
| pod_cn | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='卸货港-中文' enum=None vs=None |
| country_id | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=number zh='目的地国家ID' enum=None vs=None |
| country_name_cn | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='目的地国家-中文' enum=None vs=None |
| entrust_status | 手建 state=form required=False ui=text zh='1是检查，2是分发' enum=None vs=None | 生成 state=form required=False ui=number zh='1未分发 2已分发' enum=None vs=None |
| order_file | 手建 state=carry required=False ui=unknown zh='' enum=None vs=None | 生成 state=form required=False ui=file zh='' enum=None vs=None |
| create_time | 手建 state=form required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=text zh='业务订单创建时间' enum=None vs=None |
| update_time | 手建 state=form required=False ui=unknown zh='' enum=None vs=None | 生成 state=carry required=False ui=number zh='更新时间' enum=None vs=None |

## fin.order_entrust.order_customer_container

- missing(4):
  - [capture](4): customer_id, order_id, container, policy_type

## fin.order_entrust.order_dispatch

- missing(239):
  - [capture](239): bl_no, track_bl_no, order_id, order_no, entrust_status, action, client_expand_name, client_expand_id, m_delivery_type, customer_id, customer_name, receive_time_limit, deposit_refund_day, deposit_settlement_date, service_id, service_name, sale_id, sale_name, operator_id, operator_name, customer_contact_id, customer_contact_name, main_sort, policy_id, policy_name, policy_type, settle_type, settle_type_name, product_id, product_name, deposit_type, deposit_type_name, period_delay_type, period_delay_type_name, service_items, business_type, trade_term, carrier, carrier_id, etd, atd, ship_name, voy, pol, pot, pod, del, country_name, airline_type, ocean_type, terms_payment, terms_transport, pay_type, customer_order_sn, terms_shipment, shipper, consignee, notifier, ship_mark, commodity, notes, cargo_type, packer, num, gross_weight, bulk, sea_trans_cost, teu, volume, volume_desc, order_sn, status, sea_trans_currency, container, message_board, customer_file_list, supplier, remark, customer_category, customer_tax_number, customer_address_cn, customer_contact_phone, customer_main_id, customer_main_name, business_main_id, business_main_name, fund_code, fund_name, track_atd, track_eta, track_ata, track_stcs, track_ship_name, track_voy, finance_date, pol_cn, pol_country_id, pol_country, pol_country_cn, pod_cn, pot_cn, del_cn, country_id, country_name_cn, customer_period, customer_settlement_date, period_rule, term_rule_name, customer_due_date, customer_put_date, customer_payment_collection_date, customer_put_date_manual, customer_put_writeoff_date, supplier_due_date, discount_start, discount_rule, discount_end, discount_ratio, discount_status, discount_currency, book_upload_date, trans_cost_put_preserve_date, bl_no_upload_date, supplier_invoice_date, supplier_invoice_taketime, real_cost_date, customer_invoice_request_date, first_financing_doc_ok_date, second_financing_doc_ok_date, insurance_doc_ok_date, customer_confirm_date, is_delayed_recovery, delayed_recovery_usd, delayed_recovery_cny, delayed_time, expect_fee_status, real_fee_status, fee_lock_status, pay_account_status, account_status, real_pay_usd, real_pay_cny, real_put_usd, real_put_cny, real_put_discount_rate, exchange_rate, folde_pay_usd, folde_put_usd, folde_pay_total, folde_put_total, gross_margin, gross_margin_rate, is_special_pay, is_loan_before_invoice, is_fee_miss, fee_miss_name, cancel_remark, cancel_time, effective_id, effective_by, effective_time, create_id, create_by, create_time, update_id, update_by, update_time, delete_time, business_time, main_ids, reverse_status, proprietary_business_status, loan_status, first_status, second_status, loan_pay_status, change_type, copy_order_id, real_fee_locked, is_usd_project, pay_status, is_sync_es, expect_discount_status, real_discount_status, audit_type, is_system_generate, is_financing, confirm_status, is_traverse, financing_apply_amount, financing_apply_amount_cny, financing_apply_amount_usd, sys_upttime, customer_put_date_desc, deposit_refund_month, payment_type, revoke_status, revoke_type, asset_status, revoke_failure_reason, repayment_date, repay_warn_time, reverse_status_name, is_delayed_recovery_name, order_finance_arr, order_main_bank_arr, order_sub, order_sub_no, service_project, service_project_amount, finance_status, main_ids_name, policy_main_arr, policy_type_name, business_type_name, cargo_type_name, period_rule_name, trade_term_name, carrier_name, terms_transport_name, terms_payment_name, pay_type_name, m_delivery_type_name, payment_type_name, audit, enable, policy_match, policy_match_name, real_discount_status_name, expect_discount_status_name, expect_policy_status_name, policy_status_name, subsidy_category_name, expect_subsidy_category_name, real_subsidy_category_name, revoke_status_name, revoke_type_name, asset_status_name, order_file

## fin.order_entrust.order_page

- missing(7):
  - [capture](7): bl_no, order_no, page_no, page_size, sort_field, sort_order, params

## fin.order_fee.asset_push

- missing(4):
  - [capture](4): action, order_id, audit_msg, select_node_user

## fin.order_fee.book_real_amount_edit

- missing(7):
  - [capture](7): action, order_id, discount_ratio, service_project, import_status, to_customer, to_supplier

## fin.order_fee.real_amount_lock_submit

- missing(5):
  - [capture](5): action, order_id, order_fee_real_ids, audit_msg, select_node_user

## fin.order_fee.toggle_real_amount

- missing(1):
  - [capture](1): order_id

## fin.settlement.create_order

- missing(4):
  - [capture](4): order_id, amount, currency, remark
