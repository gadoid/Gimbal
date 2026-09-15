# 对照报告(生成 vs 手建 ground truth)

## fin.audit.audit_execute

| 键 | 手建 | 生成 |
|---|---|---|
| audit_status | 手建 state=form required=True zh='' enum=None vs=None | 生成 state=form required=True zh='审批状态 1待处理 2通过 3驳回 4撤销' enum=['2', '3'] vs=None |
| audit_remark | 手建 state=form required=True zh='' enum=None vs=None | 生成 state=form required=False zh='审批意见' enum=None vs=None |

## fin.audit.audit_page

- missing(3): sort_field, sort_order, params
- extra(24): is_all, create_id, create_time_start, create_time_end, audit_type, audit_no, audit_status, check_ids, audit_note, expedite_status, customer_id, supplier_id, bl_no, bl_nos, cancel_remark, invoice_batch_no, main_id, put_settle_object_id, pay_settle_object_id, invoice_apply_currency, writeoff_no, pay_demand_no, account_no, source_type
| 键 | 手建 | 生成 |
|---|---|---|
| page_no | 手建 state=form required=True zh='页码,从 1 开始' enum=None vs=None | 生成 state=form required=False zh='' enum=None vs=None |
| page_size | 手建 state=form required=True zh='每页条数,默认 20' enum=None vs=None | 生成 state=form required=False zh='' enum=None vs=None |
| active_tab | 手建 state=form required=True zh='审批页签: examine_wait=待审批 / examine_done=已审批' enum=['examine_wait', 'examine_done'] vs=None | 生成 state=form required=False zh='' enum=None vs=None |

## fin.customer.part

- missing(1): customer_id

## fin.customer.policy

- missing(2): customer_id, status

## fin.order.check_generate_order_sub

| 键 | 手建 | 生成 |
|---|---|---|
| order_id | 手建 state=form required=True zh='' enum=None vs=None | 生成 state=form required=True zh='业务订单ID' enum=None vs=None |

## fin.order.generate_order_sub

- extra(2): policy_id, customer_id
| 键 | 手建 | 生成 |
|---|---|---|
| order_id | 手建 state=form required=True zh='' enum=None vs=None | 生成 state=form required=True zh='业务订单ID' enum=None vs=None |

## fin.order.order_add

- missing(185): order_no, customer_file_list, order_file, client_expand_name, m_delivery_type, customer_name, service_name, sale_name, operator_name, customer_contact_name, settle_type_name, customer_product_id, product_name, deposit_type, deposit_type_name, period_delay_type, period_delay_type_name, carrier_id, ocean_type, teu, order_sn, message_board, customer_category, customer_tax_number, customer_address_cn, customer_contact_phone, customer_main_id, customer_main_name, business_main_id, business_main_name, fund_code, fund_name, track_atd, track_eta, track_ata, track_stcs, track_ship_name, track_voy, finance_date, pol_cn, pol_country_id, pol_country, pol_country_cn, pod_cn, pot_cn, del_cn, country_id, country_name_cn, customer_period, customer_settlement_date, period_rule, term_rule_name, customer_due_date, customer_put_date, customer_payment_collection_date, customer_put_date_manual, customer_put_writeoff_date, supplier_due_date, discount_start, discount_rule, discount_end, discount_ratio, discount_status, discount_currency, book_upload_date, trans_cost_put_preserve_date, bl_no_upload_date, supplier_invoice_date, supplier_invoice_taketime, real_cost_date, customer_invoice_request_date, first_financing_doc_ok_date, second_financing_doc_ok_date, insurance_doc_ok_date, customer_confirm_date, is_delayed_recovery, delayed_recovery_usd, delayed_recovery_cny, delayed_time, expect_fee_status, real_fee_status, fee_lock_status, pay_account_status, account_status, real_pay_usd, real_pay_cny, real_put_usd, real_put_cny, real_put_discount_rate, exchange_rate, folde_pay_usd, folde_put_usd, folde_pay_total, folde_put_total, gross_margin, gross_margin_rate, is_special_pay, is_loan_before_invoice, is_fee_miss, fee_miss_name, cancel_remark, cancel_time, effective_id, effective_by, effective_time, create_id, create_by, create_time, update_id, update_by, update_time, delete_time, business_time, main_ids, reverse_status, proprietary_business_status, loan_status, first_status, second_status, loan_pay_status, change_type, copy_order_id, real_fee_locked, pay_status, is_sync_es, expect_discount_status, real_discount_status, audit_type, is_system_generate, is_financing, confirm_status, is_traverse, financing_apply_amount, financing_apply_amount_cny, financing_apply_amount_usd, sys_upttime, receive_time_limit, customer_put_date_desc, deposit_refund_day, deposit_settlement_date, deposit_refund_month, payment_type, product_id, revoke_status, revoke_type, asset_status, revoke_failure_reason, repayment_date, repay_warn_time, reverse_status_name, is_delayed_recovery_name, order_finance_arr, order_main_bank_arr, order_sub, order_sub_no, service_project, service_project_amount, finance_status, main_ids_name, policy_main_arr, policy_type_name, business_type_name, cargo_type_name, period_rule_name, trade_term_name, carrier_name, terms_transport_name, terms_payment_name, pay_type_name, m_delivery_type_name, payment_type_name, audit, enable, policy_match, policy_match_name, real_discount_status_name, expect_discount_status_name, expect_policy_status_name, policy_status_name, subsidy_category_name, expect_subsidy_category_name, real_subsidy_category_name, revoke_status_name, revoke_type_name, asset_status_name
- extra(2): state, financing_continue
| 键 | 手建 | 生成 |
|---|---|---|
| bl_no | 手建 state=form required=False zh='' enum=None vs=None | 生成 state=carry required=True zh='提单号' enum=None vs=('pending_orders', 'bl_no') |
| order_id | 手建 state=form required=False zh='' enum=None vs=None | 生成 state=form required=False zh='业务订单ID' enum=None vs=None |
| track_bl_no | 手建 state=form required=False zh='' enum=None vs=None | 生成 state=carry required=True zh='提单号' enum=None vs=None |
| entrust_status | 手建 state=form required=False zh='' enum=None vs=None | 生成 state=form required=False zh='1未分发 2已分发' enum=None vs=None |
| action | 手建 state=form required=False zh='' enum=['check', 'submit'] vs=None | 生成 state=form required=False zh='操作目的' enum=None vs=None |
| customer_id | 手建 state=carry required=False zh='' enum=None vs=('customer_list', 'customer_id') | 生成 state=form required=True zh='客户ID' enum=None vs=None |
| service_id | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=True zh='客服ID' enum=None vs=None |
| sale_id | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='销售ID' enum=None vs=None |
| operator_id | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=True zh='操作ID' enum=None vs=None |
| customer_contact_id | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='客户联系人id' enum=None vs=None |
| main_sort | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=True zh='主体顺序' enum=None vs=None |
| policy_id | 手建 state=carry required=False zh='' enum=None vs=('customer_policy', 'policy_id') | 生成 state=form required=True zh='服务策略ID' enum=None vs=None |
| policy_name | 手建 state=carry required=False zh='' enum=None vs=('customer_policy', 'policy_name') | 生成 state=carry required=True zh='服务策略名字' enum=None vs=('customer_policy', 'policy_name') |
| policy_type | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=True zh='政策类型' enum=None vs=None |
| settle_type | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='1月结 2票结' enum=None vs=None |
| service_items | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=True zh='服务项目' enum=None vs=None |
| business_type | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=True zh='业务类型' enum=None vs=None |
| trade_term | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=True zh='成交方式' enum=None vs=None |
| carrier | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=True zh='船公司/承运人' enum=None vs=None |
| etd | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=True zh='预计开航日' enum=None vs=None |
| atd | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='实际开航日' enum=None vs=None |
| ship_name | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=True zh='船名' enum=None vs=None |
| voy | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=True zh='航次' enum=None vs=None |
| pol | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=True zh='起运港' enum=None vs=None |
| pot | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='中转港' enum=None vs=None |
| pod | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=True zh='卸货港' enum=None vs=None |
| del | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=True zh='目的地' enum=None vs=None |
| country_name | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='卸货港国家' enum=None vs=None |
| airline_type | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='航线分类' enum=None vs=None |
| terms_payment | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='结汇方式' enum=None vs=None |
| terms_transport | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='运输条款' enum=None vs=None |
| pay_type | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='付款方式' enum=None vs=None |
| customer_order_sn | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='客户单号' enum=None vs=None |
| terms_shipment | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='装运条款' enum=None vs=None |
| shipper | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='发货人' enum=None vs=None |
| consignee | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='收货人' enum=None vs=None |
| notifier | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='通知人' enum=None vs=None |
| ship_mark | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='唛头' enum=None vs=None |
| commodity | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='品名' enum=None vs=None |
| notes | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='托书备注' enum=None vs=None |
| cargo_type | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='货物类型' enum=None vs=None |
| packer | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='包装' enum=None vs=None |
| num | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=True zh='件数' enum=None vs=None |
| gross_weight | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=True zh='毛重' enum=None vs=None |
| bulk | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='体积' enum=None vs=None |
| sea_trans_cost | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='海运费总价' enum=None vs=None |
| volume | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='箱型箱量' enum=None vs=None |
| volume_desc | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='箱型箱量描述' enum=None vs=None |
| status | 手建 state=form required=False zh='' enum=None vs=None | 生成 state=form required=True zh='订单状态' enum=['1', '2'] vs=None |
| sea_trans_currency | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='海运费币制' enum=None vs=None |
| container | 手建 state=form required=False zh='' enum=None vs=None | 生成 state=form required=False zh='箱型' enum=None vs=None |
| client_expand_id | 手建 state=carry required=False zh='' enum=None vs=('customer_part', 'handover_form.client_expand_id') | 生成 state=carry required=False zh='直客拓展ID' enum=None vs=None |
| is_usd_project | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='是否USD项目' enum=None vs=None |
| remark | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='备注' enum=None vs=None |

## fin.order.order_add_demo

- missing(240): bl_no, order_id, order_no, track_bl_no, entrust_status, action, customer_file_list, order_file, client_expand_name, m_delivery_type, customer_id, customer_name, service_id, service_name, sale_id, sale_name, operator_id, operator_name, customer_contact_id, customer_contact_name, main_sort, policy_id, policy_name, policy_type, settle_type, settle_type_name, customer_product_id, product_name, deposit_type, deposit_type_name, period_delay_type, period_delay_type_name, service_items, business_type, trade_term, carrier, carrier_id, etd, atd, ship_name, voy, pol, pot, pod, del, country_name, airline_type, ocean_type, terms_payment, terms_transport, pay_type, customer_order_sn, terms_shipment, shipper, consignee, notifier, ship_mark, commodity, notes, cargo_type, packer, num, gross_weight, bulk, sea_trans_cost, teu, volume, volume_desc, order_sn, status, sea_trans_currency, message_board, supplier, container, customer_category, customer_tax_number, customer_address_cn, client_expand_id, customer_contact_phone, customer_main_id, customer_main_name, business_main_id, business_main_name, fund_code, fund_name, track_atd, track_eta, track_ata, track_stcs, track_ship_name, track_voy, finance_date, pol_cn, pol_country_id, pol_country, pol_country_cn, pod_cn, pot_cn, del_cn, country_id, country_name_cn, customer_period, customer_settlement_date, period_rule, term_rule_name, customer_due_date, customer_put_date, customer_payment_collection_date, customer_put_date_manual, customer_put_writeoff_date, supplier_due_date, discount_start, discount_rule, discount_end, discount_ratio, discount_status, discount_currency, book_upload_date, trans_cost_put_preserve_date, bl_no_upload_date, supplier_invoice_date, supplier_invoice_taketime, real_cost_date, customer_invoice_request_date, first_financing_doc_ok_date, second_financing_doc_ok_date, insurance_doc_ok_date, customer_confirm_date, is_delayed_recovery, delayed_recovery_usd, delayed_recovery_cny, delayed_time, expect_fee_status, real_fee_status, fee_lock_status, pay_account_status, account_status, real_pay_usd, real_pay_cny, real_put_usd, real_put_cny, real_put_discount_rate, exchange_rate, folde_pay_usd, folde_put_usd, folde_pay_total, folde_put_total, gross_margin, gross_margin_rate, is_special_pay, is_loan_before_invoice, is_fee_miss, fee_miss_name, cancel_remark, cancel_time, effective_id, effective_by, effective_time, create_id, create_by, create_time, update_id, update_by, update_time, delete_time, business_time, main_ids, reverse_status, proprietary_business_status, loan_status, first_status, second_status, loan_pay_status, change_type, copy_order_id, real_fee_locked, is_usd_project, pay_status, is_sync_es, expect_discount_status, real_discount_status, remark, audit_type, is_system_generate, is_financing, confirm_status, is_traverse, financing_apply_amount, financing_apply_amount_cny, financing_apply_amount_usd, sys_upttime, receive_time_limit, customer_put_date_desc, deposit_refund_day, deposit_settlement_date, deposit_refund_month, payment_type, product_id, revoke_status, revoke_type, asset_status, revoke_failure_reason, repayment_date, repay_warn_time, reverse_status_name, is_delayed_recovery_name, order_finance_arr, order_main_bank_arr, order_sub, order_sub_no, service_project, service_project_amount, finance_status, main_ids_name, policy_main_arr, policy_type_name, business_type_name, cargo_type_name, period_rule_name, trade_term_name, carrier_name, terms_transport_name, terms_payment_name, pay_type_name, m_delivery_type_name, payment_type_name, audit, enable, policy_match, policy_match_name, real_discount_status_name, expect_discount_status_name, expect_policy_status_name, policy_status_name, subsidy_category_name, expect_subsidy_category_name, real_subsidy_category_name, revoke_status_name, revoke_type_name, asset_status_name

## fin.order.order_book

- missing(187): order_id, order_no, entrust_status, action, customer_file_list, client_expand_name, m_delivery_type, service_name, sale_name, operator_name, customer_contact_name, settle_type_name, customer_product_id, product_name, deposit_type, deposit_type_name, period_delay_type, period_delay_type_name, carrier_id, airline_type, ocean_type, teu, order_sn, message_board, customer_category, customer_tax_number, customer_address_cn, client_expand_id, customer_contact_phone, customer_main_id, customer_main_name, business_main_id, business_main_name, fund_code, fund_name, track_atd, track_eta, track_ata, track_stcs, track_ship_name, track_voy, finance_date, pol_cn, pol_country_id, pol_country, pol_country_cn, pod_cn, pot_cn, del_cn, country_id, country_name_cn, customer_period, customer_settlement_date, period_rule, term_rule_name, customer_due_date, customer_put_date, customer_payment_collection_date, customer_put_date_manual, customer_put_writeoff_date, supplier_due_date, discount_start, discount_rule, discount_end, discount_ratio, discount_status, discount_currency, book_upload_date, trans_cost_put_preserve_date, bl_no_upload_date, supplier_invoice_date, supplier_invoice_taketime, real_cost_date, customer_invoice_request_date, first_financing_doc_ok_date, second_financing_doc_ok_date, insurance_doc_ok_date, customer_confirm_date, is_delayed_recovery, delayed_recovery_usd, delayed_recovery_cny, delayed_time, expect_fee_status, real_fee_status, fee_lock_status, pay_account_status, account_status, real_pay_usd, real_pay_cny, real_put_usd, real_put_cny, real_put_discount_rate, exchange_rate, folde_pay_usd, folde_put_usd, folde_pay_total, folde_put_total, gross_margin, gross_margin_rate, is_special_pay, is_loan_before_invoice, is_fee_miss, fee_miss_name, cancel_remark, cancel_time, effective_id, effective_by, effective_time, create_id, create_by, create_time, update_id, update_by, update_time, delete_time, business_time, reverse_status, proprietary_business_status, loan_status, first_status, second_status, loan_pay_status, change_type, copy_order_id, real_fee_locked, pay_status, is_sync_es, expect_discount_status, real_discount_status, audit_type, is_system_generate, is_financing, confirm_status, financing_apply_amount, financing_apply_amount_cny, financing_apply_amount_usd, sys_upttime, receive_time_limit, customer_put_date_desc, deposit_refund_day, deposit_settlement_date, deposit_refund_month, payment_type, product_id, revoke_status, revoke_type, asset_status, revoke_failure_reason, repayment_date, repay_warn_time, reverse_status_name, is_delayed_recovery_name, order_finance_arr, order_main_bank_arr, order_sub, order_sub_no, service_project, service_project_amount, finance_status, main_ids_name, policy_main_arr, policy_type_name, business_type_name, cargo_type_name, period_rule_name, trade_term_name, carrier_name, terms_transport_name, terms_payment_name, pay_type_name, m_delivery_type_name, payment_type_name, audit, enable, policy_match, policy_match_name, real_discount_status_name, expect_discount_status_name, expect_policy_status_name, policy_status_name, subsidy_category_name, expect_subsidy_category_name, real_subsidy_category_name, revoke_status_name, revoke_type_name, asset_status_name, order_file
- extra(2): book_supplier_name, book_supplier_id
| 键 | 手建 | 生成 |
|---|---|---|
| bl_no | 手建 state=form required=False zh='' enum=None vs=None | 生成 state=form required=True zh='提单号' enum=None vs=None |
| track_bl_no | 手建 state=form required=False zh='' enum=None vs=None | 生成 state=carry required=True zh='提单号' enum=None vs=None |
| customer_id | 手建 state=carry required=False zh='' enum=None vs=('customer_list', 'customer_id') | 生成 state=form required=True zh='客户ID' enum=None vs=None |
| customer_name | 手建 state=carry required=False zh='' enum=None vs=('customer_list', 'customer_name') | 生成 state=form required=False zh='客户名称' enum=None vs=None |
| service_id | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='客服ID' enum=None vs=None |
| sale_id | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='销售ID' enum=None vs=None |
| operator_id | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=True zh='操作ID' enum=None vs=None |
| customer_contact_id | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='客户联系人id' enum=None vs=None |
| main_sort | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=True zh='主体顺序' enum=None vs=None |
| policy_id | 手建 state=carry required=False zh='' enum=None vs=('customer_policy', 'policy_id') | 生成 state=form required=True zh='服务策略ID' enum=None vs=None |
| policy_name | 手建 state=carry required=False zh='' enum=None vs=('customer_policy', 'policy_name') | 生成 state=carry required=True zh='服务策略名字' enum=None vs=('customer_policy', 'policy_name') |
| policy_type | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=True zh='政策类型' enum=None vs=None |
| settle_type | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='1月结 2票结' enum=None vs=None |
| service_items | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=True zh='服务项目' enum=None vs=None |
| business_type | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='业务类型' enum=None vs=None |
| trade_term | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='成交方式' enum=None vs=None |
| carrier | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='船公司/承运人' enum=None vs=None |
| etd | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='预计开航日' enum=None vs=None |
| atd | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='实际开航日' enum=None vs=None |
| ship_name | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='船名' enum=None vs=None |
| voy | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='航次' enum=None vs=None |
| pol | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='起运港' enum=None vs=None |
| pot | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='中转港' enum=None vs=None |
| pod | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='卸货港' enum=None vs=None |
| del | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='目的地' enum=None vs=None |
| country_name | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='卸货港国家' enum=None vs=None |
| terms_payment | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='结汇方式' enum=None vs=None |
| terms_transport | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='运输条款' enum=None vs=None |
| pay_type | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='付款方式' enum=None vs=None |
| customer_order_sn | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='客户单号' enum=None vs=None |
| terms_shipment | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='装运条款' enum=None vs=None |
| shipper | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='发货人' enum=None vs=None |
| consignee | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='收货人' enum=None vs=None |
| notifier | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='通知人' enum=None vs=None |
| ship_mark | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='唛头' enum=None vs=None |
| commodity | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='品名' enum=None vs=None |
| notes | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='托书备注' enum=None vs=None |
| cargo_type | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='货物类型' enum=None vs=None |
| packer | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='包装' enum=None vs=None |
| num | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='件数' enum=None vs=None |
| gross_weight | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='毛重' enum=None vs=None |
| bulk | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='体积' enum=None vs=None |
| sea_trans_cost | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='海运费总价' enum=None vs=None |
| volume | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='箱型箱量' enum=None vs=None |
| volume_desc | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='箱型箱量描述' enum=None vs=None |
| status | 手建 state=form required=False zh='' enum=None vs=None | 生成 state=form required=False zh='订单状态' enum=None vs=None |
| sea_trans_currency | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='海运费币制' enum=None vs=None |
| container | 手建 state=form required=False zh='' enum=None vs=None | 生成 state=form required=False zh='箱型' enum=None vs=None |
| main_ids | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='主体顺序ID' enum=None vs=None |
| is_usd_project | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='是否USD项目' enum=None vs=None |
| remark | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='备注' enum=None vs=None |
| is_traverse | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='是否穿行  0未穿行  1已穿行' enum=None vs=None |

## fin.order.order_detail

- extra(74): order_sub_id, etd, atd, num, reverse_status_name, reverse_status, is_delayed_recovery_name, is_delayed_recovery, order_finance_arr, order_main_bank_arr, order_sub, order_sub_no, status, container, real_fee_locked, service_project, service_project_amount, finance_status, main_ids_name, main_sort, policy_main_arr, main_ids, policy_type_name, policy_type, business_type_name, business_type, cargo_type_name, cargo_type, period_rule_name, period_rule, trade_term_name, trade_term, carrier_name, carrier, terms_transport_name, terms_transport, terms_payment_name, terms_payment, pay_type_name, pay_type, customer_put_writeoff_date, m_delivery_type_name, m_delivery_type, settle_type_name, settle_type, period_delay_type_name, period_delay_type, deposit_type_name, deposit_type, payment_type_name, payment_type, receive_time_limit, service_items, supplier, audit, enable, policy_id, policy_match, policy_match_name, real_discount_status_name, real_discount_status, expect_discount_status_name, expect_discount_status, expect_policy_status_name, policy_status_name, subsidy_category_name, expect_subsidy_category_name, real_subsidy_category_name, revoke_status_name, revoke_status, revoke_type, revoke_type_name, asset_status_name, asset_status
| 键 | 手建 | 生成 |
|---|---|---|
| order_id | 手建 state=form required=False zh='订单id' enum=None vs=None | 生成 state=form required=True zh='业务订单ID' enum=None vs=None |

## fin.order.order_notice

- extra(2): policy_id, customer_id
| 键 | 手建 | 生成 |
|---|---|---|
| order_id | 手建 state=form required=True zh='' enum=None vs=None | 生成 state=form required=True zh='业务订单ID' enum=None vs=None |
| action | 手建 state=form required=True zh='' enum=['check', 'submit'] vs=None | 生成 state=form required=False zh='操作目的' enum=None vs=None |
| finance_ids | 手建 state=form required=True zh='' enum=None vs=None | 生成 state=form required=False zh='' enum=None vs=None |
| bank_ids | 手建 state=form required=True zh='' enum=None vs=None | 生成 state=form required=False zh='' enum=None vs=None |

## fin.order.order_page

- missing(3): sort_field, sort_order, params
- extra(95): order_ids, order_nos, customer_category, business_no, customer_order_sn, track_bl_no, track_bl_nos, bl_nos, revoke_reason, is_traverse, order_sub_no, customer_id, settle_type, period_delay_type, customer_main_id, business_main_id, supplier_id, policy_type, policy_id, status, pay_status, real_fee_status, fee_lock_status, is_loan_before_invoice, service_items, business_type, trade_term, carrier, client_expand_id, etd_start, etd_end, atd_start, atd_end, track_atd_start, track_atd_end, finance_date_start, finance_date_end, volume, ship_name, voy, pol, del, pod, airline_type, customer_period, customer_put_date_start, customer_put_date_end, book_supplier_id, book_supplier_period, book_supplier_pay_date_start, book_supplier_pay_date_end, customs_supplier_period, customs_supplier_pay_date_start, customs_supplier_pay_date_end, manifest_supplier_period, manifest_supplier_pay_date_start, manifest_supplier_pay_date_end, insurance_supplier_period, insurance_supplier_pay_date_start, insurance_supplier_pay_date_end, trucking_supplier_period, trucking_supplier_pay_date_start, trucking_supplier_pay_date_end, reverse_status, is_delayed_recovery, sale_id, service_id, operator_id, fund_code, customer_account_status, customer_invoice_status, customer_writeoff_status, supplier_account_status, supplier_invoice_status, supplier_writeoff_status, discount_rule, discount_currency, discount_status, create_time_start, create_time_end, period_rule, period_cutover_rule, is_special_pay, is_fee_miss, cancel_remark, create_id, entrust_status, term_rule_name, audit_type, is_financing, product_name, revoke_type, revoke_status, customer_payment_type, confirm_status
| 键 | 手建 | 生成 |
|---|---|---|
| bl_no | 手建 state=form required=True zh='' enum=None vs=None | 生成 state=form required=False zh='提单号' enum=None vs=None |
| order_no | 手建 state=form required=True zh='' enum=None vs=None | 生成 state=form required=False zh='业务订单编号' enum=None vs=None |
| page_no | 手建 state=form required=True zh='' enum=None vs=None | 生成 state=form required=False zh='' enum=None vs=None |
| page_size | 手建 state=form required=True zh='' enum=None vs=None | 生成 state=form required=False zh='' enum=None vs=None |

## fin.order_entrust.order_add

- missing(44): client_expand_name, m_delivery_type, customer_name, receive_time_limit, deposit_refund_day, deposit_settlement_date, service_name, sale_name, operator_name, customer_contact_name, settle_type_name, product_id, product_name, deposit_type, deposit_type_name, period_delay_type, period_delay_type_name, carrier_id, ocean_type, sea_trans_cost, teu, order_sn, sea_trans_currency, message_board, customer_file_list, payment_type_name, payment_type, policy_type_name, main_ids, pot_cn, pot_port_name, pol_cn, pol_port_name, pol_country_id, pol_country, pol_country_cn, del_cn, del_port_name, pod_cn, pod_port_name, country_id, country_name_cn, create_time, update_time
- extra(5): is_usd_project, customerData, order_id, oldSupplierMap, order_self_id
| 键 | 手建 | 生成 |
|---|---|---|
| bl_no | 手建 state=form required=False zh='' enum=None vs=('pending_orders', 'bl_no') | 生成 state=carry required=True zh='提单号' enum=None vs=('pending_orders', 'bl_no') |
| track_bl_no | 手建 state=form required=False zh='' enum=None vs=None | 生成 state=carry required=True zh='提单号' enum=None vs=None |
| action | 手建 state=form required=False zh='check[校验]/submit[提交]' enum=['check', 'submit'] vs=None | 生成 state=form required=False zh='操作目的' enum=None vs=None |
| client_expand_id | 手建 state=carry required=False zh='' enum=None vs=('customer_part', 'handover_form.client_expand_id') | 生成 state=form required=False zh='直客拓展ID' enum=None vs=None |
| customer_id | 手建 state=carry required=False zh='' enum=None vs=('customer_list', 'customer_id') | 生成 state=form required=True zh='客户ID' enum=None vs=None |
| service_id | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='客服ID' enum=None vs=None |
| sale_id | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='销售ID' enum=None vs=None |
| operator_id | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=True zh='操作ID' enum=None vs=None |
| customer_contact_id | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='客户联系人id' enum=None vs=None |
| main_sort | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=True zh='主体顺序' enum=None vs=None |
| policy_id | 手建 state=carry required=False zh='' enum=None vs=('customer_policy', 'policy_id') | 生成 state=form required=True zh='服务策略ID' enum=None vs=None |
| policy_name | 手建 state=carry required=False zh='' enum=None vs=('customer_policy', 'policy_name') | 生成 state=carry required=True zh='服务策略名字' enum=None vs=('customer_policy', 'policy_name') |
| policy_type | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=True zh='政策类型' enum=None vs=None |
| settle_type | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='1月结 2票结' enum=None vs=None |
| service_items | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=True zh='服务项目' enum=None vs=None |
| business_type | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='业务类型' enum=None vs=None |
| trade_term | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='成交方式' enum=None vs=None |
| carrier | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='船公司/承运人' enum=None vs=None |
| etd | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='预计开航日' enum=None vs=None |
| atd | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='实际开航日' enum=None vs=None |
| ship_name | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='船名' enum=None vs=None |
| voy | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='航次' enum=None vs=None |
| pol | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='起运港' enum=None vs=None |
| pot | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='中转港' enum=None vs=None |
| pod | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='卸货港' enum=None vs=None |
| del | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='目的地' enum=None vs=None |
| country_name | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='卸货港国家' enum=None vs=None |
| airline_type | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='航线分类' enum=None vs=None |
| terms_payment | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='结汇方式' enum=None vs=None |
| terms_transport | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='运输条款' enum=None vs=None |
| pay_type | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='付款方式' enum=None vs=None |
| customer_order_sn | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='客户单号' enum=None vs=None |
| terms_shipment | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='装运条款' enum=None vs=None |
| shipper | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='发货人' enum=None vs=None |
| consignee | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='收货人' enum=None vs=None |
| notifier | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='通知人' enum=None vs=None |
| ship_mark | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='唛头' enum=None vs=None |
| commodity | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='品名' enum=None vs=None |
| notes | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='托书备注' enum=None vs=None |
| cargo_type | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='货物类型' enum=None vs=None |
| packer | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='包装' enum=None vs=None |
| num | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='件数' enum=None vs=None |
| gross_weight | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='毛重' enum=None vs=None |
| bulk | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='体积' enum=None vs=None |
| volume | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='箱型箱量' enum=None vs=None |
| volume_desc | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='箱型箱量描述' enum=None vs=None |
| status | 手建 state=form required=False zh='' enum=None vs=None | 生成 state=form required=False zh='订单状态' enum=None vs=None |
| container | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='箱型' enum=None vs=None |
| supplier | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='' enum=None vs=None |
| remark | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=carry required=False zh='备注' enum=None vs=None |
| entrust_status | 手建 state=form required=False zh='1是检查，2是分发' enum=None vs=None | 生成 state=form required=False zh='1未分发 2已分发' enum=None vs=None |
| order_file | 手建 state=carry required=False zh='' enum=None vs=None | 生成 state=form required=False zh='' enum=None vs=None |

## fin.order_entrust.order_customer_container

- missing(4): customer_id, order_id, container, policy_type

## fin.order_entrust.order_dispatch

- missing(239): bl_no, track_bl_no, order_id, order_no, entrust_status, action, client_expand_name, client_expand_id, m_delivery_type, customer_id, customer_name, receive_time_limit, deposit_refund_day, deposit_settlement_date, service_id, service_name, sale_id, sale_name, operator_id, operator_name, customer_contact_id, customer_contact_name, main_sort, policy_id, policy_name, policy_type, settle_type, settle_type_name, product_id, product_name, deposit_type, deposit_type_name, period_delay_type, period_delay_type_name, service_items, business_type, trade_term, carrier, carrier_id, etd, atd, ship_name, voy, pol, pot, pod, del, country_name, airline_type, ocean_type, terms_payment, terms_transport, pay_type, customer_order_sn, terms_shipment, shipper, consignee, notifier, ship_mark, commodity, notes, cargo_type, packer, num, gross_weight, bulk, sea_trans_cost, teu, volume, volume_desc, order_sn, status, sea_trans_currency, container, message_board, customer_file_list, supplier, remark, customer_category, customer_tax_number, customer_address_cn, customer_contact_phone, customer_main_id, customer_main_name, business_main_id, business_main_name, fund_code, fund_name, track_atd, track_eta, track_ata, track_stcs, track_ship_name, track_voy, finance_date, pol_cn, pol_country_id, pol_country, pol_country_cn, pod_cn, pot_cn, del_cn, country_id, country_name_cn, customer_period, customer_settlement_date, period_rule, term_rule_name, customer_due_date, customer_put_date, customer_payment_collection_date, customer_put_date_manual, customer_put_writeoff_date, supplier_due_date, discount_start, discount_rule, discount_end, discount_ratio, discount_status, discount_currency, book_upload_date, trans_cost_put_preserve_date, bl_no_upload_date, supplier_invoice_date, supplier_invoice_taketime, real_cost_date, customer_invoice_request_date, first_financing_doc_ok_date, second_financing_doc_ok_date, insurance_doc_ok_date, customer_confirm_date, is_delayed_recovery, delayed_recovery_usd, delayed_recovery_cny, delayed_time, expect_fee_status, real_fee_status, fee_lock_status, pay_account_status, account_status, real_pay_usd, real_pay_cny, real_put_usd, real_put_cny, real_put_discount_rate, exchange_rate, folde_pay_usd, folde_put_usd, folde_pay_total, folde_put_total, gross_margin, gross_margin_rate, is_special_pay, is_loan_before_invoice, is_fee_miss, fee_miss_name, cancel_remark, cancel_time, effective_id, effective_by, effective_time, create_id, create_by, create_time, update_id, update_by, update_time, delete_time, business_time, main_ids, reverse_status, proprietary_business_status, loan_status, first_status, second_status, loan_pay_status, change_type, copy_order_id, real_fee_locked, is_usd_project, pay_status, is_sync_es, expect_discount_status, real_discount_status, audit_type, is_system_generate, is_financing, confirm_status, is_traverse, financing_apply_amount, financing_apply_amount_cny, financing_apply_amount_usd, sys_upttime, customer_put_date_desc, deposit_refund_month, payment_type, revoke_status, revoke_type, asset_status, revoke_failure_reason, repayment_date, repay_warn_time, reverse_status_name, is_delayed_recovery_name, order_finance_arr, order_main_bank_arr, order_sub, order_sub_no, service_project, service_project_amount, finance_status, main_ids_name, policy_main_arr, policy_type_name, business_type_name, cargo_type_name, period_rule_name, trade_term_name, carrier_name, terms_transport_name, terms_payment_name, pay_type_name, m_delivery_type_name, payment_type_name, audit, enable, policy_match, policy_match_name, real_discount_status_name, expect_discount_status_name, expect_policy_status_name, policy_status_name, subsidy_category_name, expect_subsidy_category_name, real_subsidy_category_name, revoke_status_name, revoke_type_name, asset_status_name, order_file

## fin.order_entrust.order_page

- missing(3): sort_field, sort_order, params
- extra(99): order_ids, order_nos, customer_category, revoke_type, revoke_status, customer_order_sn, track_bl_no, track_bl_nos, bl_nos, is_traverse, order_sub_no, customer_id, settle_type, period_delay_type, customer_main_id, business_main_id, supplier_id, policy_type, policy_id, status, pay_status, expect_fee_status, real_fee_status, fee_lock_status, is_loan_before_invoice, service_items, business_type, trade_term, carrier, client_expand_id, etd_start, etd_end, atd_start, atd_end, track_atd_start, track_atd_end, finance_date_start, finance_date_end, volume, ship_name, voy, pol, del, pod, airline_type, customer_period, customer_put_date_start, customer_put_date_end, book_supplier_id, book_supplier_period, book_supplier_pay_date_start, book_supplier_pay_date_end, customs_supplier_id, customs_supplier_period, customs_supplier_pay_date_start, customs_supplier_pay_date_end, manifest_supplier_id, manifest_supplier_period, manifest_supplier_pay_date_start, manifest_supplier_pay_date_end, insurance_supplier_id, insurance_supplier_period, insurance_supplier_pay_date_start, insurance_supplier_pay_date_end, trucking_supplier_id, trucking_supplier_period, trucking_supplier_pay_date_start, trucking_supplier_pay_date_end, reverse_status, is_delayed_recovery, sale_id, service_id, operator_id, fund_code, customer_account_status, customer_invoice_status, customer_writeoff_status, supplier_account_status, supplier_invoice_status, supplier_writeoff_status, real_put_discount_rate, discount_rule, discount_currency, discount_status, create_time_start, create_time_end, period_rule, period_cutover_rule, is_special_pay, is_fee_miss, cancel_remark, create_id, entrust_status, term_rule_name, audit_type, is_financing, customer_payment_type, product_name, confirm_status
| 键 | 手建 | 生成 |
|---|---|---|
| bl_no | 手建 state=form required=True zh='' enum=None vs=None | 生成 state=form required=False zh='提单号' enum=None vs=None |
| order_no | 手建 state=form required=True zh='' enum=None vs=None | 生成 state=form required=False zh='业务订单编号' enum=None vs=None |
| page_no | 手建 state=form required=True zh='' enum=None vs=None | 生成 state=form required=False zh='' enum=None vs=None |
| page_size | 手建 state=form required=True zh='' enum=None vs=None | 生成 state=form required=False zh='' enum=None vs=None |

## fin.order_fee.asset_push

- extra(7): main_ids, order_no, audit_note, flow_type, relation_id, order_ids, audit_type
| 键 | 手建 | 生成 |
|---|---|---|
| action | 手建 state=form required=True zh='' enum=['check', 'submit'] vs=None | 生成 state=form required=False zh='操作目的' enum=None vs=None |
| order_id | 手建 state=form required=True zh='' enum=None vs=None | 生成 state=form required=False zh='业务订单ID' enum=None vs=None |
| audit_msg | 手建 state=form required=True zh='' enum=None vs=None | 生成 state=form required=False zh='审批回显信息' enum=None vs=None |
| select_node_user | 手建 state=form required=True zh='' enum=None vs=None | 生成 state=form required=False zh='' enum=None vs=None |

## fin.order_fee.book_real_amount_edit

- missing(1): discount_ratio
- extra(5): service_item, to_customer_supplier, to_cooperate, policy_id, customer_id
| 键 | 手建 | 生成 |
|---|---|---|
| action | 手建 state=form required=False zh='' enum=['check', 'submit'] vs=None | 生成 state=form required=False zh='操作目的' enum=None vs=None |
| order_id | 手建 state=form required=False zh='' enum=None vs=None | 生成 state=form required=False zh='业务订单ID' enum=None vs=None |
| service_project | 手建 state=form required=False zh='' enum=None vs=None | 生成 state=form required=False zh='服务项目' enum=None vs=None |

## fin.order_fee.real_amount_lock_submit

- extra(19): box_no_continue, main_ids, order_no, customer_id, customer_name, bl_no, pol, pod, del, volume, audit_note, flow_type, relation_id, atd, discount_status, policy_id, container, policy_type, business_type
| 键 | 手建 | 生成 |
|---|---|---|
| action | 手建 state=form required=True zh='' enum=['check', 'submit'] vs=None | 生成 state=form required=False zh='操作目的' enum=None vs=None |
| order_id | 手建 state=form required=True zh='' enum=None vs=None | 生成 state=form required=False zh='业务订单ID' enum=None vs=None |
| order_fee_real_ids | 手建 state=form required=True zh='' enum=None vs=None | 生成 state=form required=False zh='' enum=None vs=None |
| audit_msg | 手建 state=form required=True zh='' enum=None vs=None | 生成 state=form required=False zh='审批回显信息' enum=None vs=None |
| select_node_user | 手建 state=form required=True zh='' enum=None vs=None | 生成 state=form required=False zh='' enum=None vs=None |

## fin.order_fee.toggle_real_amount

| 键 | 手建 | 生成 |
|---|---|---|
| order_id | 手建 state=form required=True zh='' enum=None vs=None | 生成 state=form required=False zh='业务订单ID' enum=None vs=None |

## fin.settlement.create_order

- missing(4): order_id, amount, currency, remark
