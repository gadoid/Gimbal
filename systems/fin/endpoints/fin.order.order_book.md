---
id: fin.order.order_book
type: endpoints
system: fin
service: fin-service
---

# 提交订舱文件

```gimbal:endpoint
review: reviewed
id: fin.order.order_book
system: fin
service: fin-service
name: 提交订舱文件
description: '由 Scenario_Test_14 提取: 提交订舱文件'
binding:
  protocol: http
  method: POST
  path: /api/order/order/orderBook
  auth: bearer
request:
  declarations:
  - name: bl_no
    path: $.bl_no
    type: string
    example: Codfish-IPKZ-Test
    ui_kind: text
  - name: order_id
    path: $.order_id
    type: string
    example: '354066893969032192'
    ui_kind: text
  - name: order_no
    path: $.order_no
    type: string
    example: YWDD20260904110854
    ui_kind: text
  - name: track_bl_no
    path: $.track_bl_no
    type: string
    example: Codfish-IPKZ-Test
    ui_kind: text
  - name: entrust_status
    path: $.entrust_status
    type: string
    example: '2'
    description: '1: 委托订单 2: 订单已分发'
    ui_kind: text
  - name: action
    path: $.action
    type: string
    example: check
    description: check 检查 | submit 提交
    enum:
    - check
    - submit
    ui_kind: text
  - name: customer_file_list
    path: $.customer_file_list
    type: array
    children:
    - name: client_company_id
      path: $.customer_file_list.client_company_id
      type: string
      ui_kind: text
    - name: client_company_name
      path: $.customer_file_list.client_company_name
      type: string
      ui_kind: text
    - name: trustee_company_id
      path: $.customer_file_list.trustee_company_id
      type: string
      ui_kind: text
    - name: trustee_company_name
      path: $.customer_file_list.trustee_company_name
      type: string
      ui_kind: text
    - name: document_type
      path: $.customer_file_list.document_type
      type: string
      ui_kind: text
    - name: file_url
      path: $.customer_file_list.file_url
      type: string
      ui_kind: text
    - name: file_name
      path: $.customer_file_list.file_name
      type: string
      ui_kind: text
    - name: file_id
      path: $.customer_file_list.file_id
      type: string
      ui_kind: text
    - name: file_type
      path: $.customer_file_list.file_type
      type: string
      ui_kind: text
  - name: client_expand_name
    path: $.client_expand_name
    type: string
    state: carry
    value_source:
      view: customer_part
      column: handover_form.client_expand_name
  - name: m_delivery_type
    path: $.m_delivery_type
    type: string
    state: carry
  - name: customer_id
    path: $.customer_id
    type: string
    state: carry
    value_source:
      view: customer_list
      column: customer_id
  - name: customer_name
    path: $.customer_name
    type: string
    state: carry
    value_source:
      view: customer_list
      column: customer_name
  - name: service_id
    path: $.service_id
    type: string
    state: carry
  - name: service_name
    path: $.service_name
    type: string
    state: carry
  - name: sale_id
    path: $.sale_id
    type: string
    state: carry
  - name: sale_name
    path: $.sale_name
    type: string
    state: carry
  - name: operator_id
    path: $.operator_id
    type: string
    state: carry
  - name: operator_name
    path: $.operator_name
    type: string
    state: carry
  - name: customer_contact_id
    path: $.customer_contact_id
    type: string
    state: carry
  - name: customer_contact_name
    path: $.customer_contact_name
    type: string
    state: carry
  - name: main_sort
    path: $.main_sort
    type: string
    state: carry
  - name: policy_id
    path: $.policy_id
    type: string
    state: carry
    value_source:
      view: customer_policy
      column: policy_id
  - name: policy_name
    path: $.policy_name
    type: string
    state: carry
    value_source:
      view: customer_policy
      column: policy_name
  - name: policy_type
    path: $.policy_type
    type: string
    state: carry
  - name: settle_type
    path: $.settle_type
    type: string
    state: carry
  - name: settle_type_name
    path: $.settle_type_name
    type: string
    state: carry
  - name: customer_product_id
    path: $.customer_product_id
    type: string
    state: carry
  - name: product_name
    path: $.product_name
    type: string
    state: carry
  - name: deposit_type
    path: $.deposit_type
    type: string
    state: carry
  - name: deposit_type_name
    path: $.deposit_type_name
    type: string
    state: carry
  - name: period_delay_type
    path: $.period_delay_type
    type: string
    state: carry
  - name: period_delay_type_name
    path: $.period_delay_type_name
    type: string
    state: carry
  - name: service_items
    path: $.service_items
    type: array
    state: carry
  - name: business_type
    path: $.business_type
    type: string
    state: carry
  - name: trade_term
    path: $.trade_term
    type: string
    state: carry
  - name: carrier
    path: $.carrier
    type: string
    state: carry
  - name: carrier_id
    path: $.carrier_id
    type: string
    state: carry
  - name: etd
    path: $.etd
    type: integer
    state: carry
  - name: atd
    path: $.atd
    type: integer
    state: carry
  - name: ship_name
    path: $.ship_name
    type: string
    state: carry
  - name: voy
    path: $.voy
    type: string
    state: carry
  - name: pol
    path: $.pol
    type: string
    state: carry
  - name: pot
    path: $.pot
    type: string
    state: carry
  - name: pod
    path: $.pod
    type: string
    state: carry
  - name: del
    path: $.del
    type: string
    state: carry
  - name: country_name
    path: $.country_name
    type: string
    state: carry
  - name: airline_type
    path: $.airline_type
    type: string
    state: carry
  - name: ocean_type
    path: $.ocean_type
    type: string
    state: carry
  - name: terms_payment
    path: $.terms_payment
    type: string
    state: carry
  - name: terms_transport
    path: $.terms_transport
    type: string
    state: carry
  - name: pay_type
    path: $.pay_type
    type: string
    state: carry
  - name: customer_order_sn
    path: $.customer_order_sn
    type: string
    state: carry
  - name: terms_shipment
    path: $.terms_shipment
    type: string
    state: carry
  - name: shipper
    path: $.shipper
    type: string
    state: carry
  - name: consignee
    path: $.consignee
    type: string
    state: carry
  - name: notifier
    path: $.notifier
    type: string
    state: carry
  - name: ship_mark
    path: $.ship_mark
    type: string
    state: carry
  - name: commodity
    path: $.commodity
    type: string
    state: carry
  - name: notes
    path: $.notes
    type: string
    state: carry
  - name: cargo_type
    path: $.cargo_type
    type: string
    state: carry
  - name: packer
    path: $.packer
    type: string
    state: carry
  - name: num
    path: $.num
    type: string
    state: carry
  - name: gross_weight
    path: $.gross_weight
    type: string
    state: carry
  - name: bulk
    path: $.bulk
    type: string
    state: carry
  - name: sea_trans_cost
    path: $.sea_trans_cost
    type: string
    state: carry
  - name: teu
    path: $.teu
    type: string
    state: carry
  - name: volume
    path: $.volume
    type: string
    state: carry
  - name: volume_desc
    path: $.volume_desc
    type: string
    state: carry
  - name: order_sn
    path: $.order_sn
    type: string
    state: carry
  - name: status
    path: $.status
    type: integer
  - name: sea_trans_currency
    path: $.sea_trans_currency
    type: string
    state: carry
  - name: message_board
    path: $.message_board
    type: array
    state: carry
  - name: supplier
    path: $.supplier
    type: array
    children:
    - name: order_supplier_id
      path: $.supplier.order_supplier_id
      type: string
      ui_kind: text
    - name: order_id
      path: $.supplier.order_id
      type: string
      ui_kind: text
    - name: isset_supplier
      path: $.supplier.isset_supplier
      type: string
      ui_kind: text
    - name: is_primary
      path: $.supplier.is_primary
      type: string
      ui_kind: text
    - name: supplier_id
      path: $.supplier.supplier_id
      type: string
      ui_kind: text
    - name: supplier_name
      path: $.supplier.supplier_name
      type: string
      ui_kind: text
    - name: settle_object_id
      path: $.supplier.settle_object_id
      type: string
      ui_kind: text
    - name: user_id
      path: $.supplier.user_id
      type: string
      ui_kind: text
    - name: user_name
      path: $.supplier.user_name
      type: string
      ui_kind: text
    - name: service_item
      path: $.supplier.service_item
      type: string
      ui_kind: text
    - name: supplier_period
      path: $.supplier.supplier_period
      type: string
      ui_kind: text
    - name: settlement_date
      path: $.supplier.settlement_date
      type: string
      ui_kind: text
    - name: supplier_pay_date
      path: $.supplier.supplier_pay_date
      type: string
      ui_kind: text
    - name: is_manual
      path: $.supplier.is_manual
      type: string
      ui_kind: text
    - name: sys_upttime
      path: $.supplier.sys_upttime
      type: string
      ui_kind: text
    - name: pay_time_limit
      path: $.supplier.pay_time_limit
      type: string
      ui_kind: text
    - name: supplier_pay_date_desc
      path: $.supplier.supplier_pay_date_desc
      type: string
      ui_kind: text
    - name: settle_type
      path: $.supplier.settle_type
      type: string
      ui_kind: text
    - name: supplier_label
      path: $.supplier.supplier_label
      type: string
      ui_kind: text
    - name: settle_type_name
      path: $.supplier.settle_type_name
      type: string
      ui_kind: text
    - name: service_item_name
      path: $.supplier.service_item_name
      type: string
      ui_kind: text
    - name: isset_fee
      path: $.supplier.isset_fee
      type: boolean
      ui_kind: boolean
  - name: container
    path: $.container
    type: array
    children:
    - name: order_container_id
      path: $.container.order_container_id
      type: string
      ui_kind: text
    - name: box_type
      path: $.container.box_type
      type: string
      ui_kind: text
    - name: box_num
      path: $.container.box_num
      type: string
      ui_kind: text
    - name: box_no
      path: $.container.box_no
      type: array
      state: collapse
    - name: seal_number
      path: $.container.seal_number
      type: array
      state: collapse
    - name: sea_trans_unit_price
      path: $.container.sea_trans_unit_price
      type: number
      ui_kind: number
  - name: customer_category
    path: $.customer_category
    type: string
    state: carry
  - name: customer_tax_number
    path: $.customer_tax_number
    type: string
    state: carry
  - name: customer_address_cn
    path: $.customer_address_cn
    type: string
    state: carry
  - name: client_expand_id
    path: $.client_expand_id
    type: string
    state: carry
    value_source:
      view: customer_part
      column: handover_form.client_expand_id
  - name: customer_contact_phone
    path: $.customer_contact_phone
    type: string
    state: carry
  - name: customer_main_id
    path: $.customer_main_id
    type: string
    state: carry
  - name: customer_main_name
    path: $.customer_main_name
    type: string
    state: carry
  - name: business_main_id
    path: $.business_main_id
    type: string
    state: carry
  - name: business_main_name
    path: $.business_main_name
    type: string
    state: carry
  - name: fund_code
    path: $.fund_code
    type: string
    state: carry
  - name: fund_name
    path: $.fund_name
    type: string
    state: carry
  - name: track_atd
    path: $.track_atd
    type: string
    state: carry
  - name: track_eta
    path: $.track_eta
    type: string
    state: carry
  - name: track_ata
    path: $.track_ata
    type: string
    state: carry
  - name: track_stcs
    path: $.track_stcs
    type: string
    state: carry
  - name: track_ship_name
    path: $.track_ship_name
    type: string
    state: carry
  - name: track_voy
    path: $.track_voy
    type: string
    state: carry
  - name: finance_date
    path: $.finance_date
    type: string
    state: carry
  - name: pol_cn
    path: $.pol_cn
    type: string
    state: carry
  - name: pol_country_id
    path: $.pol_country_id
    type: string
    state: carry
  - name: pol_country
    path: $.pol_country
    type: string
    state: carry
  - name: pol_country_cn
    path: $.pol_country_cn
    type: string
    state: carry
  - name: pod_cn
    path: $.pod_cn
    type: string
    state: carry
  - name: pot_cn
    path: $.pot_cn
    type: string
    state: carry
  - name: del_cn
    path: $.del_cn
    type: string
    state: carry
  - name: country_id
    path: $.country_id
    type: string
    state: carry
  - name: country_name_cn
    path: $.country_name_cn
    type: string
    state: carry
  - name: customer_period
    path: $.customer_period
    type: string
    state: carry
  - name: customer_settlement_date
    path: $.customer_settlement_date
    type: string
    state: carry
  - name: period_rule
    path: $.period_rule
    type: string
    state: carry
  - name: term_rule_name
    path: $.term_rule_name
    type: string
    state: carry
  - name: customer_due_date
    path: $.customer_due_date
    type: string
    state: carry
  - name: customer_put_date
    path: $.customer_put_date
    type: string
    state: carry
  - name: customer_payment_collection_date
    path: $.customer_payment_collection_date
    type: string
    state: carry
  - name: customer_put_date_manual
    path: $.customer_put_date_manual
    type: string
    state: carry
  - name: customer_put_writeoff_date
    path: $.customer_put_writeoff_date
    type: string
    state: carry
  - name: supplier_due_date
    path: $.supplier_due_date
    type: string
    state: carry
  - name: discount_start
    path: $.discount_start
    type: string
    state: carry
  - name: discount_rule
    path: $.discount_rule
    type: string
    state: carry
  - name: discount_end
    path: $.discount_end
    type: string
    state: carry
  - name: discount_ratio
    path: $.discount_ratio
    type: string
    state: carry
  - name: discount_status
    path: $.discount_status
    type: string
    state: carry
  - name: discount_currency
    path: $.discount_currency
    type: string
    state: carry
  - name: book_upload_date
    path: $.book_upload_date
    type: string
    state: carry
  - name: trans_cost_put_preserve_date
    path: $.trans_cost_put_preserve_date
    type: string
    state: carry
  - name: bl_no_upload_date
    path: $.bl_no_upload_date
    type: string
    state: carry
  - name: supplier_invoice_date
    path: $.supplier_invoice_date
    type: string
    state: carry
  - name: supplier_invoice_taketime
    path: $.supplier_invoice_taketime
    type: string
    state: carry
  - name: real_cost_date
    path: $.real_cost_date
    type: string
    state: carry
  - name: customer_invoice_request_date
    path: $.customer_invoice_request_date
    type: string
    state: carry
  - name: first_financing_doc_ok_date
    path: $.first_financing_doc_ok_date
    type: string
    state: carry
  - name: second_financing_doc_ok_date
    path: $.second_financing_doc_ok_date
    type: string
    state: carry
  - name: insurance_doc_ok_date
    path: $.insurance_doc_ok_date
    type: string
    state: carry
  - name: customer_confirm_date
    path: $.customer_confirm_date
    type: string
    state: carry
  - name: is_delayed_recovery
    path: $.is_delayed_recovery
    type: string
    state: carry
  - name: delayed_recovery_usd
    path: $.delayed_recovery_usd
    type: string
    state: carry
  - name: delayed_recovery_cny
    path: $.delayed_recovery_cny
    type: string
    state: carry
  - name: delayed_time
    path: $.delayed_time
    type: string
    state: carry
  - name: expect_fee_status
    path: $.expect_fee_status
    type: string
    state: carry
  - name: real_fee_status
    path: $.real_fee_status
    type: string
    state: carry
  - name: fee_lock_status
    path: $.fee_lock_status
    type: string
    state: carry
  - name: pay_account_status
    path: $.pay_account_status
    type: string
    state: carry
  - name: account_status
    path: $.account_status
    type: string
    state: carry
  - name: real_pay_usd
    path: $.real_pay_usd
    type: string
    state: carry
  - name: real_pay_cny
    path: $.real_pay_cny
    type: string
    state: carry
  - name: real_put_usd
    path: $.real_put_usd
    type: string
    state: carry
  - name: real_put_cny
    path: $.real_put_cny
    type: string
    state: carry
  - name: real_put_discount_rate
    path: $.real_put_discount_rate
    type: string
    state: carry
  - name: exchange_rate
    path: $.exchange_rate
    type: string
    state: carry
  - name: folde_pay_usd
    path: $.folde_pay_usd
    type: string
    state: carry
  - name: folde_put_usd
    path: $.folde_put_usd
    type: string
    state: carry
  - name: folde_pay_total
    path: $.folde_pay_total
    type: string
    state: carry
  - name: folde_put_total
    path: $.folde_put_total
    type: string
    state: carry
  - name: gross_margin
    path: $.gross_margin
    type: string
    state: carry
  - name: gross_margin_rate
    path: $.gross_margin_rate
    type: string
    state: carry
  - name: is_special_pay
    path: $.is_special_pay
    type: string
    state: carry
  - name: is_loan_before_invoice
    path: $.is_loan_before_invoice
    type: string
    state: carry
  - name: is_fee_miss
    path: $.is_fee_miss
    type: string
    state: carry
  - name: fee_miss_name
    path: $.fee_miss_name
    type: string
    state: carry
  - name: cancel_remark
    path: $.cancel_remark
    type: string
    state: carry
  - name: cancel_time
    path: $.cancel_time
    type: string
    state: carry
  - name: effective_id
    path: $.effective_id
    type: string
    state: carry
  - name: effective_by
    path: $.effective_by
    type: string
    state: carry
  - name: effective_time
    path: $.effective_time
    type: string
    state: carry
  - name: create_id
    path: $.create_id
    type: string
    state: carry
  - name: create_by
    path: $.create_by
    type: string
    state: carry
  - name: create_time
    path: $.create_time
    type: string
  - name: update_id
    path: $.update_id
    type: string
    state: carry
  - name: update_by
    path: $.update_by
    type: string
    state: carry
  - name: update_time
    path: $.update_time
    type: string
  - name: delete_time
    path: $.delete_time
    type: string
    state: carry
  - name: business_time
    path: $.business_time
    type: string
    state: carry
  - name: main_ids
    path: $.main_ids
    type: string
    state: carry
  - name: reverse_status
    path: $.reverse_status
    type: string
    state: carry
  - name: proprietary_business_status
    path: $.proprietary_business_status
    type: string
    state: carry
  - name: loan_status
    path: $.loan_status
    type: string
    state: carry
  - name: first_status
    path: $.first_status
    type: string
    state: carry
  - name: second_status
    path: $.second_status
    type: string
    state: carry
  - name: loan_pay_status
    path: $.loan_pay_status
    type: string
    state: carry
  - name: change_type
    path: $.change_type
    type: string
    state: carry
  - name: copy_order_id
    path: $.copy_order_id
    type: string
    state: carry
  - name: real_fee_locked
    path: $.real_fee_locked
    type: boolean
    state: carry
  - name: is_usd_project
    path: $.is_usd_project
    type: string
    state: carry
  - name: pay_status
    path: $.pay_status
    type: string
    state: carry
  - name: is_sync_es
    path: $.is_sync_es
    type: string
    state: carry
  - name: expect_discount_status
    path: $.expect_discount_status
    type: string
    state: carry
  - name: real_discount_status
    path: $.real_discount_status
    type: string
    state: carry
  - name: remark
    path: $.remark
    type: string
    state: carry
  - name: audit_type
    path: $.audit_type
    type: string
    state: carry
  - name: is_system_generate
    path: $.is_system_generate
    type: string
    state: carry
  - name: is_financing
    path: $.is_financing
    type: string
    state: carry
  - name: confirm_status
    path: $.confirm_status
    type: string
    state: carry
  - name: is_traverse
    path: $.is_traverse
    type: string
    state: carry
  - name: financing_apply_amount
    path: $.financing_apply_amount
    type: string
    state: carry
  - name: financing_apply_amount_cny
    path: $.financing_apply_amount_cny
    type: string
    state: carry
  - name: financing_apply_amount_usd
    path: $.financing_apply_amount_usd
    type: string
    state: carry
  - name: sys_upttime
    path: $.sys_upttime
    type: string
    ui_kind: text
  - name: receive_time_limit
    path: $.receive_time_limit
    type: string
    state: carry
  - name: customer_put_date_desc
    path: $.customer_put_date_desc
    type: string
    state: carry
  - name: deposit_refund_day
    path: $.deposit_refund_day
    type: string
    state: carry
  - name: deposit_settlement_date
    path: $.deposit_settlement_date
    type: string
    state: carry
  - name: deposit_refund_month
    path: $.deposit_refund_month
    type: string
    state: carry
  - name: payment_type
    path: $.payment_type
    type: string
    state: carry
  - name: product_id
    path: $.product_id
    type: string
    state: carry
  - name: revoke_status
    path: $.revoke_status
    type: string
    state: carry
  - name: revoke_type
    path: $.revoke_type
    type: string
    state: carry
  - name: asset_status
    path: $.asset_status
    type: string
    state: carry
  - name: revoke_failure_reason
    path: $.revoke_failure_reason
    type: string
    state: carry
  - name: repayment_date
    path: $.repayment_date
    type: string
    state: carry
  - name: repay_warn_time
    path: $.repay_warn_time
    type: string
    state: carry
  - name: reverse_status_name
    path: $.reverse_status_name
    type: string
    state: carry
  - name: is_delayed_recovery_name
    path: $.is_delayed_recovery_name
    type: string
    state: carry
  - name: order_finance_arr
    path: $.order_finance_arr
    type: array
    state: carry
  - name: order_main_bank_arr
    path: $.order_main_bank_arr
    type: array
    state: carry
  - name: order_sub
    path: $.order_sub
    type: array
    state: carry
  - name: order_sub_no
    path: $.order_sub_no
    type: string
    state: carry
  - name: service_project
    path: $.service_project
    type: object
    state: carry
    children:
    - name: booking_space
      path: $.service_project.booking_space
      type: boolean
      state: carry
    - name: customs_clearance
      path: $.service_project.customs_clearance
      type: boolean
      state: carry
    - name: manifest
      path: $.service_project.manifest
      type: boolean
      state: carry
    - name: insurance
      path: $.service_project.insurance
      type: boolean
      state: carry
    - name: trucking
      path: $.service_project.trucking
      type: boolean
      state: carry
  - name: service_project_amount
    path: $.service_project_amount
    type: object
    state: carry
    children:
    - name: booking_space
      path: $.service_project_amount.booking_space
      type: boolean
      state: carry
    - name: customs_clearance
      path: $.service_project_amount.customs_clearance
      type: boolean
      state: carry
    - name: manifest
      path: $.service_project_amount.manifest
      type: boolean
      state: carry
    - name: insurance
      path: $.service_project_amount.insurance
      type: boolean
      state: carry
    - name: trucking
      path: $.service_project_amount.trucking
      type: boolean
      state: carry
  - name: finance_status
    path: $.finance_status
    type: boolean
    state: carry
  - name: main_ids_name
    path: $.main_ids_name
    type: string
    state: carry
  - name: policy_main_arr
    path: $.policy_main_arr
    type: array
    state: carry
    children:
    - name: fee_main_id
      path: $.policy_main_arr.fee_main_id
      type: string
      state: carry
    - name: main_name
      path: $.policy_main_arr.main_name
      type: string
      state: carry
  - name: policy_type_name
    path: $.policy_type_name
    type: string
    state: carry
  - name: business_type_name
    path: $.business_type_name
    type: string
    state: carry
  - name: cargo_type_name
    path: $.cargo_type_name
    type: string
    state: carry
  - name: period_rule_name
    path: $.period_rule_name
    type: string
    state: carry
  - name: trade_term_name
    path: $.trade_term_name
    type: string
    state: carry
  - name: carrier_name
    path: $.carrier_name
    type: string
    state: carry
  - name: terms_transport_name
    path: $.terms_transport_name
    type: string
    state: carry
  - name: terms_payment_name
    path: $.terms_payment_name
    type: string
    state: carry
  - name: pay_type_name
    path: $.pay_type_name
    type: string
    state: carry
  - name: m_delivery_type_name
    path: $.m_delivery_type_name
    type: string
    state: carry
  - name: payment_type_name
    path: $.payment_type_name
    type: string
    state: carry
  - name: audit
    path: $.audit
    type: array
    state: carry
  - name: enable
    path: $.enable
    type: string
    state: carry
  - name: policy_match
    path: $.policy_match
    type: string
    state: carry
  - name: policy_match_name
    path: $.policy_match_name
    type: string
    state: carry
  - name: real_discount_status_name
    path: $.real_discount_status_name
    type: string
    state: carry
  - name: expect_discount_status_name
    path: $.expect_discount_status_name
    type: string
    state: carry
  - name: expect_policy_status_name
    path: $.expect_policy_status_name
    type: string
    state: carry
  - name: policy_status_name
    path: $.policy_status_name
    type: string
    state: carry
  - name: subsidy_category_name
    path: $.subsidy_category_name
    type: string
    state: carry
  - name: expect_subsidy_category_name
    path: $.expect_subsidy_category_name
    type: string
    state: carry
  - name: real_subsidy_category_name
    path: $.real_subsidy_category_name
    type: string
    state: carry
  - name: revoke_status_name
    path: $.revoke_status_name
    type: string
    state: carry
  - name: revoke_type_name
    path: $.revoke_type_name
    type: string
    state: carry
  - name: asset_status_name
    path: $.asset_status_name
    type: string
    state: carry
  - name: order_file
    path: $.order_file
    type: array
    state: carry
responses:
  '200':
    description: 成功
    declarations:
    - name: code
      path: $.code
      type: integer
      example: 200
      ui_kind: text
      assertable: true
    - name: msg
      path: $.msg
      type: string
      example: 成功
      ui_kind: text
      assertable: true
    - name: data
      path: $.data
      type: array
      assertable: true
      children:
      - name: client_company_id
        path: $.data.client_company_id
        type: string
        example: '335247043402399744'
        ui_kind: text
        assertable: true
      - name: client_company_name
        path: $.data.client_company_name
        type: string
        example: 绍兴柯桥鹏达进出口有限公司
        ui_kind: text
        assertable: true
      - name: trustee_company_id
        path: $.data.trustee_company_id
        type: string
        example: '1'
        ui_kind: text
        assertable: true
      - name: trustee_company_name
        path: $.data.trustee_company_name
        type: string
        example: 青岛易航道物流科技有限公司
        ui_kind: text
        assertable: true
      - name: document_type
        path: $.data.document_type
        type: string
        example: BOOK_CUSTOMER
        ui_kind: text
        assertable: true
      - name: file_url
        path: $.data.file_url
        type: string
        example: 6a9c2d1e2292e.pdf
        ui_kind: text
        assertable: true
      - name: file_name
        path: $.data.file_name
        type: string
        example: 6a9c2d1e2292e.pdf
        ui_kind: text
        assertable: true
      - name: file_id
        path: $.data.file_id
        type: string
        example: '354640409386812416'
        ui_kind: text
        assertable: true
      - name: file_type
        path: $.data.file_type
        type: string
        example: PDF
        ui_kind: text
        assertable: true
    - name: request_id
      path: $.request_id
      type: string
      example: 44a89db20b3ebd34718f4b3f4b7c24d8
      ui_kind: text
      assertable: true
metadata:
  module: fin
  tags:
  - fin
  owner: fin-team
```
