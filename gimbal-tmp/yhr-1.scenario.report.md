# Scenario Assembly Report

- script: `yhr-1.script.json`
- scaffold: `yhr-1-scaffold.json`
- output scenario: `yhr-1.scenario.json`
- auth user: `codfish`
- service: `None`

## Counts

- kept steps: **24**
- external values templated: **1**
- whitelist headers kept: `authorization, content-type`

## External values templated

| Template | # source values |
|---|---:|
| `${var.bl_no}` | 1 |

## Wiring (kept steps)

| # | idx | method | path | extracts | assigns | synthetic |
|---:|---:|---|---|---|---|---|
| 0 | 0 | POST | `/api/order/orderEntrust/orderAdd` | — | — |  |
| 1 | 1 | POST | `/api/order/orderEntrust/orderAdd` | — | — |  |
| 2 | 2 | POST | `/api/order/orderEntrust/orderPage` | `order_id`, `order_no` | — |  |
| 3 | 4 | POST | `/api/order/order/orderDetail` | `order_supplier_id` | `order_id`→`$.request_body.order_id` |  |
| 4 | 5 | POST | `/api/order/orderEntrust/orderAdd` | — | `order_supplier_id`→`$.request_body.supplier[0].order_supplier_id`, `order_id`→`$.request_body.supplier[0].order_id`, `order_id`→`$.request_body.order_id`, `order_no`→`$.request_body.order_no` |  |
| 5 | 6 | POST | `/api/order/orderEntrust/orderAdd` | — | `order_supplier_id`→`$.request_body.supplier[0].order_supplier_id`, `order_id`→`$.request_body.supplier[0].order_id`, `order_id`→`$.request_body.order_id`, `order_no`→`$.request_body.order_no` |  |
| 6 | 10 | POST | `/api/order/order/orderDetail` | `order_container_id` | `order_id`→`$.request_body.order_id` |  |
| 7 | 11 | POST | `/api/order/order/orderAdd` | — | `order_container_id`→`$.request_body.container[0].order_container_id`, `order_supplier_id`→`$.request_body.supplier[0].order_supplier_id`, `order_id`→`$.request_body.supplier[0].order_id`, `order_id`→`$.request_body.order_id`, `order_no`→`$.request_body.order_no` |  |
| 8 | 12 | POST | `/api/order/order/orderBook` | `file_id` | `order_container_id`→`$.request_body.container[0].order_container_id`, `order_supplier_id`→`$.request_body.supplier[0].order_supplier_id`, `order_id`→`$.request_body.supplier[0].order_id`, `order_id`→`$.request_body.order_id`, `order_no`→`$.request_body.order_no` |  |
| 9 | 13 | POST | `/api/order/order/orderAdd` | — | `order_container_id`→`$.request_body.container[0].order_container_id`, `file_id`→`$.request_body.customer_file_list[0].file_id`, `order_supplier_id`→`$.request_body.supplier[0].order_supplier_id`, `order_id`→`$.request_body.supplier[0].order_id`, `order_id`→`$.request_body.order_id`, `order_no`→`$.request_body.order_no` |  |
| 10 | 14 | POST | `/api/order/order/orderPage` | `code` | — |  |
| 11 | 16 | POST | `/api/order/orderFee/toggleRealAmount` | — | `order_id`→`$.request_body.order_id` |  |
| 12 | 17 | POST | `/api/order/orderFee/bookRealAmountEdit` | — | `order_id`→`$.request_body.order_id` |  |
| 13 | 18 | POST | `/api/order/orderFee/bookRealAmountEdit` | — | `order_id`→`$.request_body.order_id` |  |
| 14 | 21 | POST | `/api/order/order/checkGenerateOrderSub` | — | `order_id`→`$.request_body.order_id` |  |
| 15 | 22 | POST | `/api/order/order/generateOrderSub` | — | `order_id`→`$.request_body.order_id` |  |
| 16 | 24 | POST | `/api/order/orderFee/toggleRealAmount` | `order_fee_real_ids` | `order_id`→`$.request_body.order_id` |  |
| 17 | 25 | POST | `/api/order/orderFee/realAmountLockSubmit` | — | `order_id`→`$.request_body.order_id`, `order_fee_real_ids`→`$.request_body.order_fee_real_ids[0]` |  |
| 18 | 26 | POST | `/api/order/orderFee/realAmountLockSubmit` | — | `order_id`→`$.request_body.order_id`, `order_fee_real_ids`→`$.request_body.order_fee_real_ids[0]` |  |
| 19 | 27 | POST | `/api/order/orderFee/realAmountLockSubmit` | — | `order_id`→`$.request_body.order_id`, `order_fee_real_ids`→`$.request_body.order_fee_real_ids[0]`, `code`→`$.request_body.audit_msg.code` |  |
| 20 | 29 | POST | `/api/order/order/orderDetail` | `audit_id` | `order_id`→`$.request_body.order_id` |  |
| 21 | 33 | POST | `/api/home/audit/auditExecute` | — | `audit_id`→`$.request_body.audit_ids[0]` |  |
| 22 | 38 | POST | `/api/order/order/orderDetail` | `audit_id_2` | `order_id`→`$.request_body.order_id` |  |
| 23 | 42 | POST | `/api/home/audit/auditExecute` | — | `audit_id_2`→`$.request_body.audit_ids[0]` |  |

## Untemplated literals (review candidates)

String values that survived assembly because no scaffold var / resource matched. These may be either legitimate constant payloads or missed wiring — review before shipping.

**Step 0 (idx=0, POST `/api/order/orderEntrust/orderAdd`)**

| jsonpath | literal |
|---|---|
| `$.client_expand_name` | `唐欣雨` |
| `$.client_expand_id` | `261` |
| `$.m_delivery_type` | `` |
| `$.customer_id` | `320` |
| `$.customer_name` | `` |
| `$.service_id` | `55` |
| `$.service_name` | `曲静霞` |
| `$.operator_id` | `336` |
| `$.operator_name` | `` |
| `$.customer_contact_id` | `` |
| `$.customer_contact_name` | `` |
| `$.main_sort` | `易汇瀚-易海-易航道` |
| `$.policy_id` | `134` |
| `$.policy_name` | `【SPV对客】易汇瀚（仅人民币）` |
| `$.policy_type` | `JSZX` |
| `$.service_items[0]` | `booking_space` |
| `$.business_type` | `1` |
| `$.trade_term` | `CIF` |
| `$.carrier` | `COSCO` |
| `$.carrier_id` | `16` |
| `$.ship_name` | `OOCL FRANCE` |
| `$.voy` | `068E` |
| `$.pol` | `QINGDAO,CHINA` |
| `$.pot` | `` |
| `$.pod` | `ANTING,CHINA` |
| `$.del` | `ANTING,CHINA` |
| `$.country_name` | `CHINA` |
| `$.airline_type` | `中国` |
| `$.ocean_type` | `近洋` |
| `$.terms_payment` | `T/T` |
| `$.terms_transport` | `CY/CY` |
| `$.pay_type` | `FREIGHT PREPAID` |
| `$.customer_order_sn` | `` |
| `$.terms_shipment` | `` |
| `$.shipper` | `` |
| `$.consignee` | `` |
| `$.notifier` | `` |
| `$.ship_mark` | `` |
| `$.commodity` | `` |
| `$.notes` | `` |
| `$.cargo_type` | `` |
| `$.packer` | `` |
| `$.num` | `1872` |
| `$.gross_weight` | `26800.000` |
| `$.bulk` | `60.000` |
| `$.sea_trans_cost` | `` |
| `$.teu` | `` |
| `$.volume` | `` |
| `$.volume_desc` | `` |
| `$.order_sn` | `` |
| `$.status` | `1` |
| `$.sea_trans_currency` | `USD` |
| `$.supplier[0].is_manual` | `` |
| `$.supplier[0].is_primary` | `1` |
| `$.supplier[0].isset_fee` | `0` |
| `$.supplier[0].isset_supplier` | `1` |
| `$.supplier[0].order_id` | `` |
| `$.supplier[0].order_supplier_id` | `` |
| `$.supplier[0].service_item` | `booking_space` |
| `$.supplier[0].service_item_name` | `订舱` |
| `$.supplier[0].settle_object_id` | `` |
| `$.supplier[0].supplier_id` | `805` |
| `$.supplier[0].supplier_name` | `青岛雅然国际物流有限公司` |
| `$.supplier[0].user_id` | `336` |
| `$.supplier[0].user_name` | `闫航` |
| `$.remark` | `` |
| `$.policy_type_name` | `` |
| `$.main_ids` | `15,16,1` |
| `$.pol_cn` | `青岛流亭机场` |
| `$.pol_port_name` | `QINGDAO,CHINA` |
| `$.pol_country_id` | `1` |
| `$.pol_country` | `CHINA` |
| `$.pol_country_cn` | `中国` |
| `$.pod_port_name` | `ANTING,CHINA` |
| `$.del_port_name` | `ANTING,CHINA` |
| `$.country_id` | `1` |
| `$.country_name_cn` | `中国` |
| `$.action` | `check` |

**Step 1 (idx=1, POST `/api/order/orderEntrust/orderAdd`)**

| jsonpath | literal |
|---|---|
| `$.client_expand_name` | `唐欣雨` |
| `$.client_expand_id` | `261` |
| `$.m_delivery_type` | `` |
| `$.customer_id` | `320` |
| `$.customer_name` | `` |
| `$.service_id` | `55` |
| `$.service_name` | `曲静霞` |
| `$.operator_id` | `336` |
| `$.operator_name` | `` |
| `$.customer_contact_id` | `` |
| `$.customer_contact_name` | `` |
| `$.main_sort` | `易汇瀚-易海-易航道` |
| `$.policy_id` | `134` |
| `$.policy_name` | `【SPV对客】易汇瀚（仅人民币）` |
| `$.policy_type` | `JSZX` |
| `$.service_items[0]` | `booking_space` |
| `$.business_type` | `1` |
| `$.trade_term` | `CIF` |
| `$.carrier` | `COSCO` |
| `$.carrier_id` | `16` |
| `$.ship_name` | `OOCL FRANCE` |
| `$.voy` | `068E` |
| `$.pol` | `QINGDAO,CHINA` |
| `$.pot` | `` |
| `$.pod` | `ANTING,CHINA` |
| `$.del` | `ANTING,CHINA` |
| `$.country_name` | `CHINA` |
| `$.airline_type` | `中国` |
| `$.ocean_type` | `近洋` |
| `$.terms_payment` | `T/T` |
| `$.terms_transport` | `CY/CY` |
| `$.pay_type` | `FREIGHT PREPAID` |
| `$.customer_order_sn` | `` |
| `$.terms_shipment` | `` |
| `$.shipper` | `` |
| `$.consignee` | `` |
| `$.notifier` | `` |
| `$.ship_mark` | `` |
| `$.commodity` | `` |
| `$.notes` | `` |
| `$.cargo_type` | `` |
| `$.packer` | `` |
| `$.num` | `1872` |
| `$.gross_weight` | `26800.000` |
| `$.bulk` | `60.000` |
| `$.sea_trans_cost` | `` |
| `$.teu` | `` |
| `$.volume` | `` |
| `$.volume_desc` | `` |
| `$.order_sn` | `` |
| `$.status` | `1` |
| `$.sea_trans_currency` | `USD` |
| `$.supplier[0].is_manual` | `` |
| `$.supplier[0].is_primary` | `1` |
| `$.supplier[0].isset_fee` | `0` |
| `$.supplier[0].isset_supplier` | `1` |
| `$.supplier[0].order_id` | `` |
| `$.supplier[0].order_supplier_id` | `` |
| `$.supplier[0].service_item` | `booking_space` |
| `$.supplier[0].service_item_name` | `订舱` |
| `$.supplier[0].settle_object_id` | `` |
| `$.supplier[0].supplier_id` | `805` |
| `$.supplier[0].supplier_name` | `青岛雅然国际物流有限公司` |
| `$.supplier[0].user_id` | `336` |
| `$.supplier[0].user_name` | `闫航` |
| `$.remark` | `` |
| `$.policy_type_name` | `` |
| `$.main_ids` | `15,16,1` |
| `$.pol_cn` | `青岛流亭机场` |
| `$.pol_port_name` | `QINGDAO,CHINA` |
| `$.pol_country_id` | `1` |
| `$.pol_country` | `CHINA` |
| `$.pol_country_cn` | `中国` |
| `$.pod_port_name` | `ANTING,CHINA` |
| `$.del_port_name` | `ANTING,CHINA` |
| `$.country_id` | `1` |
| `$.country_name_cn` | `中国` |
| `$.action` | `submit` |

**Step 2 (idx=2, POST `/api/order/orderEntrust/orderPage`)**

| jsonpath | literal |
|---|---|
| `$.sort_field` | `update_time` |
| `$.sort_order` | `desc` |

**Step 3 (idx=4, POST `/api/order/order/orderDetail`)**

| jsonpath | literal |
|---|---|
| `$.order_id` | `330576955302739968` |

**Step 4 (idx=5, POST `/api/order/orderEntrust/orderAdd`)**

| jsonpath | literal |
|---|---|
| `$.client_expand_name` | `唐欣雨` |
| `$.client_expand_id` | `261` |
| `$.m_delivery_type` | `` |
| `$.customer_id` | `320` |
| `$.customer_name` | `山东悦慕食品有限公司` |
| `$.service_id` | `55` |
| `$.service_name` | `曲静霞` |
| `$.operator_id` | `336` |
| `$.operator_name` | `闫航` |
| `$.customer_contact_id` | `` |
| `$.customer_contact_name` | `` |
| `$.main_sort` | `易汇瀚,易海,易航道` |
| `$.policy_id` | `134` |
| `$.policy_name` | `【SPV对客】易汇瀚（仅人民币）` |
| `$.policy_type` | `JSZX` |
| `$.service_items[0]` | `booking_space` |
| `$.business_type` | `1` |
| `$.trade_term` | `CIF` |
| `$.carrier` | `COSCO` |
| `$.carrier_id` | `16` |
| `$.ship_name` | `OOCL FRANCE` |
| `$.voy` | `068E` |
| `$.pol` | `QINGDAO,CHINA` |
| `$.pot` | `` |
| `$.pod` | `ANTING,CHINA` |
| `$.del` | `ANTING,CHINA` |
| `$.country_name` | `CHINA` |
| `$.airline_type` | `中国` |
| `$.ocean_type` | `近洋` |
| `$.terms_payment` | `T/T` |
| `$.terms_transport` | `CY/CY` |
| `$.pay_type` | `FREIGHT PREPAID` |
| `$.customer_order_sn` | `` |
| `$.terms_shipment` | `Codfish` |
| `$.shipper` | `Codfish` |
| `$.consignee` | `Codfish` |
| `$.notifier` | `Codfish` |
| `$.ship_mark` | `Codfish` |
| `$.commodity` | `Codfish` |
| `$.notes` | `Codfish` |
| `$.cargo_type` | `` |
| `$.packer` | `` |
| `$.num` | `1872` |
| `$.gross_weight` | `26800.000` |
| `$.bulk` | `60.000` |
| `$.sea_trans_cost` | `1.00` |
| `$.teu` | `` |
| `$.volume` | `1*40HQ` |
| `$.volume_desc` | `普柜` |
| `$.order_sn` | `` |
| `$.status` | `1` |
| `$.sea_trans_currency` | `USD` |
| `$.container[0].box_type` | `40HQ` |
| `$.container[0].box_num` | `1` |
| `$.container[0].box_no[0]` | `` |
| `$.container[0].seal_number[0]` | `` |
| `$.container[0].sea_trans_unit_price` | `1` |
| `$.supplier[0].order_supplier_id` | `330576956728803328` |
| `$.supplier[0].order_id` | `330576955302739968` |
| `$.supplier[0].isset_supplier` | `1` |
| `$.supplier[0].is_primary` | `1` |
| `$.supplier[0].supplier_id` | `805` |
| `$.supplier[0].supplier_name` | `青岛雅然国际物流有限公司` |
| `$.supplier[0].settle_object_id` | `1384` |
| `$.supplier[0].user_id` | `336` |
| `$.supplier[0].user_name` | `闫航` |
| `$.supplier[0].service_item` | `booking_space` |
| `$.supplier[0].supplier_period` | `60` |
| `$.supplier[0].settlement_date` | `20` |
| `$.supplier[0].supplier_pay_date` | `0` |
| `$.supplier[0].is_manual` | `0` |
| `$.supplier[0].sys_upttime` | `2026-07-01 13:14:48` |
| `$.supplier[0].supplier_label` | `青岛雅然国际物流有限公司-订舱` |
| `$.supplier[0].service_item_name` | `订舱` |
| `$.remark` | `` |
| `$.order_id` | `330576955302739968` |
| `$.order_no` | `YWDD20260701107571` |
| `$.customer_category` | `,1,2,` |
| `$.customer_tax_number` | `91370786MA3D6MW35A` |
| `$.customer_address_cn` | `山东省潍坊市昌邑市围子街道206国道北(官道郜北)` |
| `$.customer_contact_phone` | `` |
| `$.customer_main_id` | `15` |
| `$.customer_main_name` | `成都易汇瀚供应链管理有限公司` |
| `$.business_main_id` | `1` |
| `$.business_main_name` | `青岛易航道物流科技有限公司` |
| `$.fund_code` | `` |
| `$.track_atd` | `0` |
| `$.finance_date` | `1782316800` |
| `$.pol_cn` | `青岛流亭机场` |
| `$.pol_country_id` | `1` |
| `$.pol_country` | `CHINA` |
| `$.pol_country_cn` | `中国` |
| `$.pod_cn` | `` |
| `$.pot_cn` | `` |
| `$.del_cn` | `` |
| `$.country_id` | `1` |
| `$.country_name_cn` | `中国` |
| `$.customer_period` | `120` |
| `$.customer_settlement_date` | `10` |
| `$.period_rule` | `0` |
| `$.customer_due_date` | `0` |
| `$.customer_put_date` | `0` |
| `$.customer_put_date_manual` | `0` |
| `$.customer_put_writeoff_date` | `` |
| `$.supplier_due_date` | `0` |
| `$.discount_start` | `0` |
| `$.discount_rule` | `` |
| `$.discount_end` | `0` |
| `$.discount_ratio` | `` |
| `$.discount_status` | `2` |
| `$.discount_currency` | `` |
| `$.book_upload_date` | `0` |
| `$.trans_cost_put_preserve_date` | `0` |
| `$.bl_no_upload_date` | `0` |
| `$.supplier_invoice_date` | `0` |
| `$.supplier_invoice_taketime` | `` |
| `$.real_cost_date` | `0` |
| `$.customer_invoice_request_date` | `0` |
| `$.first_financing_doc_ok_date` | `0` |
| `$.second_financing_doc_ok_date` | `0` |
| `$.insurance_doc_ok_date` | `0` |
| `$.customer_confirm_date` | `0` |
| `$.is_delayed_recovery` | `否` |
| `$.delayed_recovery_usd` | `` |
| `$.delayed_recovery_cny` | `` |
| `$.delayed_time` | `` |
| `$.expect_fee_status` | `0` |
| `$.real_fee_status` | `0` |
| `$.fee_lock_status` | `0` |
| `$.pay_account_status` | `0` |
| `$.account_status` | `0` |
| `$.real_pay_usd` | `0.00` |
| `$.real_pay_cny` | `0.00` |
| `$.real_put_usd` | `0.00` |
| `$.real_put_cny` | `0.00` |
| `$.real_put_discount_rate` | `0.00` |
| `$.exchange_rate` | `0.0000` |
| `$.folde_pay_usd` | `0.00` |
| `$.folde_put_usd` | `0.00` |
| `$.folde_pay_total` | `0.00` |
| `$.folde_put_total` | `0.00` |
| `$.gross_margin` | `0.00` |
| `$.gross_margin_rate` | `0.00` |
| `$.is_special_pay` | `0` |
| `$.is_loan_before_invoice` | `0` |
| `$.is_fee_miss` | `0` |
| `$.fee_miss_name` | `` |
| `$.cancel_remark` | `` |
| `$.cancel_time` | `0` |
| `$.effective_id` | `0` |
| `$.effective_by` | `` |
| `$.effective_time` | `0` |
| `$.create_id` | `828` |
| `$.create_by` | `GIMBAL` |
| `$.create_time` | `1782882887` |
| `$.update_id` | `828` |
| `$.update_by` | `GIMBAL` |
| `$.update_time` | `1782882888` |
| `$.delete_time` | `0` |
| `$.business_time` | `0` |
| `$.main_ids` | `15,16,1` |
| `$.reverse_status` | `0` |
| `$.proprietary_business_status` | `0` |
| `$.loan_pay_status` | `` |
| `$.change_type` | `0` |
| `$.copy_order_id` | `0` |
| `$.is_usd_project` | `2` |
| `$.pay_status` | `1` |
| `$.is_sync_es` | `0` |
| `$.expect_discount_status` | `0` |
| `$.real_discount_status` | `0` |
| `$.audit_type` | `` |
| `$.is_system_generate` | `0` |
| `$.is_financing` | `0` |
| `$.confirm_status` | `0` |
| `$.is_traverse` | `0` |
| `$.financing_apply_amount` | `0.00` |
| `$.financing_apply_amount_cny` | `0.00` |
| `$.financing_apply_amount_usd` | `0.00` |
| `$.sys_upttime` | `2026-07-01 13:14:48` |
| `$.reverse_status_name` | `否` |
| `$.is_delayed_recovery_name` | `否` |
| `$.order_sub_no` | `` |
| `$.main_ids_name` | `易汇瀚,易海,易航道` |
| `$.policy_main_arr[0].fee_main_id` | `15` |
| `$.policy_main_arr[0].main_name` | `成都易汇瀚供应链管理有限公司` |
| `$.policy_main_arr[1].fee_main_id` | `16` |
| `$.policy_main_arr[1].main_name` | `青岛易海供应链管理有限公司` |
| `$.policy_main_arr[2].fee_main_id` | `1` |
| `$.policy_main_arr[2].main_name` | `青岛易航道物流科技有限公司` |
| `$.policy_type_name` | `结算业务` |
| `$.business_type_name` | `海运整箱` |
| `$.cargo_type_name` | `` |
| `$.period_rule_name` | `` |
| `$.trade_term_name` | `CIF` |
| `$.carrier_name` | `中国远洋运输（集团）总公司` |
| `$.terms_transport_name` | `CY/CY` |
| `$.terms_payment_name` | `T/T` |
| `$.pay_type_name` | `FREIGHT PREPAID` |
| `$.m_delivery_type_name` | `` |
| `$.enable` | `1` |
| `$.policy_match` | `semi` |
| `$.policy_match_name` | `手动选择` |
| `$.real_discount_status_name` | `—` |
| `$.expect_discount_status_name` | `—` |
| `$.expect_policy_status_name` | `` |
| `$.policy_status_name` | `` |
| `$.subsidy_category_name` | `—` |
| `$.expect_subsidy_category_name` | `—` |
| `$.real_subsidy_category_name` | `—` |
| `$.action` | `check` |

**Step 5 (idx=6, POST `/api/order/orderEntrust/orderAdd`)**

| jsonpath | literal |
|---|---|
| `$.client_expand_name` | `唐欣雨` |
| `$.client_expand_id` | `261` |
| `$.m_delivery_type` | `` |
| `$.customer_id` | `320` |
| `$.customer_name` | `山东悦慕食品有限公司` |
| `$.service_id` | `55` |
| `$.service_name` | `曲静霞` |
| `$.operator_id` | `336` |
| `$.operator_name` | `闫航` |
| `$.customer_contact_id` | `` |
| `$.customer_contact_name` | `` |
| `$.main_sort` | `易汇瀚,易海,易航道` |
| `$.policy_id` | `134` |
| `$.policy_name` | `【SPV对客】易汇瀚（仅人民币）` |
| `$.policy_type` | `JSZX` |
| `$.service_items[0]` | `booking_space` |
| `$.business_type` | `1` |
| `$.trade_term` | `CIF` |
| `$.carrier` | `COSCO` |
| `$.carrier_id` | `16` |
| `$.ship_name` | `OOCL FRANCE` |
| `$.voy` | `068E` |
| `$.pol` | `QINGDAO,CHINA` |
| `$.pot` | `` |
| `$.pod` | `ANTING,CHINA` |
| `$.del` | `ANTING,CHINA` |
| `$.country_name` | `CHINA` |
| `$.airline_type` | `中国` |
| `$.ocean_type` | `近洋` |
| `$.terms_payment` | `T/T` |
| `$.terms_transport` | `CY/CY` |
| `$.pay_type` | `FREIGHT PREPAID` |
| `$.customer_order_sn` | `` |
| `$.terms_shipment` | `Codfish` |
| `$.shipper` | `Codfish` |
| `$.consignee` | `Codfish` |
| `$.notifier` | `Codfish` |
| `$.ship_mark` | `Codfish` |
| `$.commodity` | `Codfish` |
| `$.notes` | `Codfish` |
| `$.cargo_type` | `` |
| `$.packer` | `` |
| `$.num` | `1872` |
| `$.gross_weight` | `26800.000` |
| `$.bulk` | `60.000` |
| `$.sea_trans_cost` | `1.00` |
| `$.teu` | `` |
| `$.volume` | `1*40HQ` |
| `$.volume_desc` | `普柜` |
| `$.order_sn` | `` |
| `$.status` | `1` |
| `$.sea_trans_currency` | `USD` |
| `$.container[0].box_type` | `40HQ` |
| `$.container[0].box_num` | `1` |
| `$.container[0].box_no[0]` | `` |
| `$.container[0].seal_number[0]` | `` |
| `$.container[0].sea_trans_unit_price` | `1` |
| `$.supplier[0].order_supplier_id` | `330576956728803328` |
| `$.supplier[0].order_id` | `330576955302739968` |
| `$.supplier[0].isset_supplier` | `1` |
| `$.supplier[0].is_primary` | `1` |
| `$.supplier[0].supplier_id` | `805` |
| `$.supplier[0].supplier_name` | `青岛雅然国际物流有限公司` |
| `$.supplier[0].settle_object_id` | `1384` |
| `$.supplier[0].user_id` | `336` |
| `$.supplier[0].user_name` | `闫航` |
| `$.supplier[0].service_item` | `booking_space` |
| `$.supplier[0].supplier_period` | `60` |
| `$.supplier[0].settlement_date` | `20` |
| `$.supplier[0].supplier_pay_date` | `0` |
| `$.supplier[0].is_manual` | `0` |
| `$.supplier[0].sys_upttime` | `2026-07-01 13:14:48` |
| `$.supplier[0].supplier_label` | `青岛雅然国际物流有限公司-订舱` |
| `$.supplier[0].service_item_name` | `订舱` |
| `$.remark` | `` |
| `$.order_id` | `330576955302739968` |
| `$.order_no` | `YWDD20260701107571` |
| `$.customer_category` | `,1,2,` |
| `$.customer_tax_number` | `91370786MA3D6MW35A` |
| `$.customer_address_cn` | `山东省潍坊市昌邑市围子街道206国道北(官道郜北)` |
| `$.customer_contact_phone` | `` |
| `$.customer_main_id` | `15` |
| `$.customer_main_name` | `成都易汇瀚供应链管理有限公司` |
| `$.business_main_id` | `1` |
| `$.business_main_name` | `青岛易航道物流科技有限公司` |
| `$.fund_code` | `` |
| `$.track_atd` | `0` |
| `$.finance_date` | `1782316800` |
| `$.pol_cn` | `青岛流亭机场` |
| `$.pol_country_id` | `1` |
| `$.pol_country` | `CHINA` |
| `$.pol_country_cn` | `中国` |
| `$.pod_cn` | `` |
| `$.pot_cn` | `` |
| `$.del_cn` | `` |
| `$.country_id` | `1` |
| `$.country_name_cn` | `中国` |
| `$.customer_period` | `120` |
| `$.customer_settlement_date` | `10` |
| `$.period_rule` | `0` |
| `$.customer_due_date` | `0` |
| `$.customer_put_date` | `0` |
| `$.customer_put_date_manual` | `0` |
| `$.customer_put_writeoff_date` | `` |
| `$.supplier_due_date` | `0` |
| `$.discount_start` | `0` |
| `$.discount_rule` | `` |
| `$.discount_end` | `0` |
| `$.discount_ratio` | `` |
| `$.discount_status` | `2` |
| `$.discount_currency` | `` |
| `$.book_upload_date` | `0` |
| `$.trans_cost_put_preserve_date` | `0` |
| `$.bl_no_upload_date` | `0` |
| `$.supplier_invoice_date` | `0` |
| `$.supplier_invoice_taketime` | `` |
| `$.real_cost_date` | `0` |
| `$.customer_invoice_request_date` | `0` |
| `$.first_financing_doc_ok_date` | `0` |
| `$.second_financing_doc_ok_date` | `0` |
| `$.insurance_doc_ok_date` | `0` |
| `$.customer_confirm_date` | `0` |
| `$.is_delayed_recovery` | `否` |
| `$.delayed_recovery_usd` | `` |
| `$.delayed_recovery_cny` | `` |
| `$.delayed_time` | `` |
| `$.expect_fee_status` | `0` |
| `$.real_fee_status` | `0` |
| `$.fee_lock_status` | `0` |
| `$.pay_account_status` | `0` |
| `$.account_status` | `0` |
| `$.real_pay_usd` | `0.00` |
| `$.real_pay_cny` | `0.00` |
| `$.real_put_usd` | `0.00` |
| `$.real_put_cny` | `0.00` |
| `$.real_put_discount_rate` | `0.00` |
| `$.exchange_rate` | `0.0000` |
| `$.folde_pay_usd` | `0.00` |
| `$.folde_put_usd` | `0.00` |
| `$.folde_pay_total` | `0.00` |
| `$.folde_put_total` | `0.00` |
| `$.gross_margin` | `0.00` |
| `$.gross_margin_rate` | `0.00` |
| `$.is_special_pay` | `0` |
| `$.is_loan_before_invoice` | `0` |
| `$.is_fee_miss` | `0` |
| `$.fee_miss_name` | `` |
| `$.cancel_remark` | `` |
| `$.cancel_time` | `0` |
| `$.effective_id` | `0` |
| `$.effective_by` | `` |
| `$.effective_time` | `0` |
| `$.create_id` | `828` |
| `$.create_by` | `GIMBAL` |
| `$.create_time` | `1782882887` |
| `$.update_id` | `828` |
| `$.update_by` | `GIMBAL` |
| `$.update_time` | `1782882888` |
| `$.delete_time` | `0` |
| `$.business_time` | `0` |
| `$.main_ids` | `15,16,1` |
| `$.reverse_status` | `0` |
| `$.proprietary_business_status` | `0` |
| `$.loan_pay_status` | `` |
| `$.change_type` | `0` |
| `$.copy_order_id` | `0` |
| `$.is_usd_project` | `2` |
| `$.pay_status` | `1` |
| `$.is_sync_es` | `0` |
| `$.expect_discount_status` | `0` |
| `$.real_discount_status` | `0` |
| `$.audit_type` | `` |
| `$.is_system_generate` | `0` |
| `$.is_financing` | `0` |
| `$.confirm_status` | `0` |
| `$.is_traverse` | `0` |
| `$.financing_apply_amount` | `0.00` |
| `$.financing_apply_amount_cny` | `0.00` |
| `$.financing_apply_amount_usd` | `0.00` |
| `$.sys_upttime` | `2026-07-01 13:14:48` |
| `$.reverse_status_name` | `否` |
| `$.is_delayed_recovery_name` | `否` |
| `$.order_sub_no` | `` |
| `$.main_ids_name` | `易汇瀚,易海,易航道` |
| `$.policy_main_arr[0].fee_main_id` | `15` |
| `$.policy_main_arr[0].main_name` | `成都易汇瀚供应链管理有限公司` |
| `$.policy_main_arr[1].fee_main_id` | `16` |
| `$.policy_main_arr[1].main_name` | `青岛易海供应链管理有限公司` |
| `$.policy_main_arr[2].fee_main_id` | `1` |
| `$.policy_main_arr[2].main_name` | `青岛易航道物流科技有限公司` |
| `$.policy_type_name` | `结算业务` |
| `$.business_type_name` | `海运整箱` |
| `$.cargo_type_name` | `` |
| `$.period_rule_name` | `` |
| `$.trade_term_name` | `CIF` |
| `$.carrier_name` | `中国远洋运输（集团）总公司` |
| `$.terms_transport_name` | `CY/CY` |
| `$.terms_payment_name` | `T/T` |
| `$.pay_type_name` | `FREIGHT PREPAID` |
| `$.m_delivery_type_name` | `` |
| `$.enable` | `1` |
| `$.policy_match` | `semi` |
| `$.policy_match_name` | `手动选择` |
| `$.real_discount_status_name` | `—` |
| `$.expect_discount_status_name` | `—` |
| `$.expect_policy_status_name` | `` |
| `$.policy_status_name` | `` |
| `$.subsidy_category_name` | `—` |
| `$.expect_subsidy_category_name` | `—` |
| `$.real_subsidy_category_name` | `—` |
| `$.action` | `submit` |

**Step 6 (idx=10, POST `/api/order/order/orderDetail`)**

| jsonpath | literal |
|---|---|
| `$.order_id` | `330576955302739968` |

**Step 7 (idx=11, POST `/api/order/order/orderAdd`)**

| jsonpath | literal |
|---|---|
| `$.client_expand_name` | `唐欣雨` |
| `$.m_delivery_type` | `` |
| `$.customer_id` | `320` |
| `$.customer_name` | `山东悦慕食品有限公司` |
| `$.service_id` | `55` |
| `$.service_name` | `曲静霞` |
| `$.operator_id` | `336` |
| `$.operator_name` | `闫航` |
| `$.customer_contact_id` | `` |
| `$.customer_contact_name` | `` |
| `$.main_sort` | `易汇瀚,易海,易航道` |
| `$.policy_id` | `134` |
| `$.policy_name` | `【SPV对客】易汇瀚（仅人民币）` |
| `$.policy_type` | `JSZX` |
| `$.service_items[0]` | `booking_space` |
| `$.business_type` | `1` |
| `$.trade_term` | `CIF` |
| `$.carrier` | `COSCO` |
| `$.carrier_id` | `16` |
| `$.ship_name` | `OOCL FRANCE` |
| `$.voy` | `068E` |
| `$.pol` | `QINGDAO,CHINA` |
| `$.pot` | `` |
| `$.pod` | `ANTING,CHINA` |
| `$.del` | `ANTING,CHINA` |
| `$.country_name` | `CHINA` |
| `$.airline_type` | `中国` |
| `$.ocean_type` | `近洋` |
| `$.terms_payment` | `T/T` |
| `$.terms_transport` | `CY/CY` |
| `$.pay_type` | `FREIGHT PREPAID` |
| `$.customer_order_sn` | `` |
| `$.terms_shipment` | `Codfish` |
| `$.shipper` | `Codfish` |
| `$.consignee` | `Codfish` |
| `$.notifier` | `Codfish` |
| `$.ship_mark` | `Codfish` |
| `$.commodity` | `Codfish` |
| `$.notes` | `Codfish` |
| `$.cargo_type` | `` |
| `$.packer` | `` |
| `$.num` | `1872` |
| `$.gross_weight` | `26800.000` |
| `$.bulk` | `60.000` |
| `$.sea_trans_cost` | `1.00` |
| `$.teu` | `2` |
| `$.volume` | `1*40HQ` |
| `$.volume_desc` | `普柜` |
| `$.order_sn` | `` |
| `$.sea_trans_currency` | `USD` |
| `$.container[0].order_container_id` | `330577156688052224` |
| `$.container[0].box_type` | `40HQ` |
| `$.container[0].box_num` | `1` |
| `$.container[0].box_no[0]` | `` |
| `$.container[0].seal_number[0]` | `` |
| `$.supplier[0].order_supplier_id` | `330576956728803328` |
| `$.supplier[0].order_id` | `330576955302739968` |
| `$.supplier[0].isset_supplier` | `1` |
| `$.supplier[0].is_primary` | `1` |
| `$.supplier[0].supplier_id` | `805` |
| `$.supplier[0].supplier_name` | `青岛雅然国际物流有限公司` |
| `$.supplier[0].settle_object_id` | `1384` |
| `$.supplier[0].user_id` | `336` |
| `$.supplier[0].user_name` | `闫航` |
| `$.supplier[0].service_item` | `booking_space` |
| `$.supplier[0].supplier_period` | `60` |
| `$.supplier[0].settlement_date` | `20` |
| `$.supplier[0].supplier_pay_date` | `0` |
| `$.supplier[0].is_manual` | `0` |
| `$.supplier[0].sys_upttime` | `2026-07-01 13:14:48` |
| `$.supplier[0].supplier_label` | `青岛雅然国际物流有限公司-订舱` |
| `$.supplier[0].service_item_name` | `订舱` |
| `$.order_id` | `330576955302739968` |
| `$.order_no` | `YWDD20260701107571` |
| `$.customer_category` | `,1,2,` |
| `$.customer_tax_number` | `91370786MA3D6MW35A` |
| `$.customer_address_cn` | `山东省潍坊市昌邑市围子街道206国道北(官道郜北)` |
| `$.client_expand_id` | `261` |
| `$.customer_contact_phone` | `` |
| `$.customer_main_id` | `15` |
| `$.customer_main_name` | `成都易汇瀚供应链管理有限公司` |
| `$.business_main_id` | `1` |
| `$.business_main_name` | `青岛易航道物流科技有限公司` |
| `$.fund_code` | `` |
| `$.track_atd` | `0` |
| `$.finance_date` | `1782316800` |
| `$.pol_cn` | `青岛流亭机场` |
| `$.pol_country_id` | `1` |
| `$.pol_country` | `CHINA` |
| `$.pol_country_cn` | `中国` |
| `$.pod_cn` | `` |
| `$.pot_cn` | `` |
| `$.del_cn` | `` |
| `$.country_id` | `1` |
| `$.country_name_cn` | `中国` |
| `$.customer_period` | `120` |
| `$.customer_settlement_date` | `10` |
| `$.period_rule` | `0` |
| `$.customer_due_date` | `0` |
| `$.customer_put_date` | `0` |
| `$.customer_put_date_manual` | `0` |
| `$.customer_put_writeoff_date` | `` |
| `$.supplier_due_date` | `0` |
| `$.discount_start` | `0` |
| `$.discount_rule` | `` |
| `$.discount_end` | `0` |
| `$.discount_ratio` | `` |
| `$.discount_status` | `2` |
| `$.discount_currency` | `` |
| `$.book_upload_date` | `0` |
| `$.trans_cost_put_preserve_date` | `0` |
| `$.bl_no_upload_date` | `0` |
| `$.supplier_invoice_date` | `0` |
| `$.supplier_invoice_taketime` | `` |
| `$.real_cost_date` | `0` |
| `$.customer_invoice_request_date` | `0` |
| `$.first_financing_doc_ok_date` | `0` |
| `$.second_financing_doc_ok_date` | `0` |
| `$.insurance_doc_ok_date` | `0` |
| `$.customer_confirm_date` | `0` |
| `$.is_delayed_recovery` | `否` |
| `$.delayed_recovery_usd` | `` |
| `$.delayed_recovery_cny` | `` |
| `$.delayed_time` | `` |
| `$.expect_fee_status` | `0` |
| `$.real_fee_status` | `0` |
| `$.fee_lock_status` | `0` |
| `$.pay_account_status` | `0` |
| `$.account_status` | `0` |
| `$.real_pay_usd` | `0.00` |
| `$.real_pay_cny` | `0.00` |
| `$.real_put_usd` | `0.00` |
| `$.real_put_cny` | `0.00` |
| `$.real_put_discount_rate` | `0.00` |
| `$.exchange_rate` | `6.8067` |
| `$.folde_pay_usd` | `0.00` |
| `$.folde_put_usd` | `0.00` |
| `$.folde_pay_total` | `0.00` |
| `$.folde_put_total` | `0.00` |
| `$.gross_margin` | `0.00` |
| `$.gross_margin_rate` | `0.00` |
| `$.is_special_pay` | `0` |
| `$.is_loan_before_invoice` | `0` |
| `$.is_fee_miss` | `0` |
| `$.fee_miss_name` | `` |
| `$.cancel_remark` | `` |
| `$.cancel_time` | `0` |
| `$.effective_id` | `0` |
| `$.effective_by` | `` |
| `$.effective_time` | `0` |
| `$.create_id` | `828` |
| `$.create_by` | `GIMBAL` |
| `$.create_time` | `1782882887` |
| `$.update_id` | `828` |
| `$.update_by` | `GIMBAL` |
| `$.update_time` | `1782882935` |
| `$.delete_time` | `0` |
| `$.business_time` | `0` |
| `$.main_ids` | `,15,16,1,` |
| `$.reverse_status` | `0` |
| `$.proprietary_business_status` | `0` |
| `$.loan_pay_status` | `` |
| `$.change_type` | `0` |
| `$.copy_order_id` | `0` |
| `$.is_usd_project` | `2` |
| `$.pay_status` | `1` |
| `$.is_sync_es` | `0` |
| `$.expect_discount_status` | `0` |
| `$.real_discount_status` | `0` |
| `$.entrust_status` | `2` |
| `$.remark` | `` |
| `$.audit_type` | `` |
| `$.is_system_generate` | `0` |
| `$.is_financing` | `0` |
| `$.confirm_status` | `0` |
| `$.is_traverse` | `0` |
| `$.financing_apply_amount` | `0.00` |
| `$.financing_apply_amount_cny` | `0.00` |
| `$.financing_apply_amount_usd` | `0.00` |
| `$.sys_upttime` | `2026-07-01 13:15:35` |
| `$.reverse_status_name` | `否` |
| `$.is_delayed_recovery_name` | `否` |
| `$.order_sub_no` | `` |
| `$.main_ids_name` | `易汇瀚,易海,易航道` |
| `$.policy_main_arr[0].fee_main_id` | `15` |
| `$.policy_main_arr[0].main_name` | `成都易汇瀚供应链管理有限公司` |
| `$.policy_main_arr[1].fee_main_id` | `16` |
| `$.policy_main_arr[1].main_name` | `青岛易海供应链管理有限公司` |
| `$.policy_main_arr[2].fee_main_id` | `1` |
| `$.policy_main_arr[2].main_name` | `青岛易航道物流科技有限公司` |
| `$.policy_type_name` | `结算业务` |
| `$.business_type_name` | `海运整箱` |
| `$.cargo_type_name` | `` |
| `$.period_rule_name` | `` |
| `$.trade_term_name` | `CIF` |
| `$.carrier_name` | `中国远洋运输（集团）总公司` |
| `$.terms_transport_name` | `CY/CY` |
| `$.terms_payment_name` | `T/T` |
| `$.pay_type_name` | `FREIGHT PREPAID` |
| `$.m_delivery_type_name` | `` |
| `$.enable` | `1` |
| `$.policy_match` | `semi` |
| `$.policy_match_name` | `手动选择` |
| `$.real_discount_status_name` | `—` |
| `$.expect_discount_status_name` | `—` |
| `$.expect_policy_status_name` | `` |
| `$.policy_status_name` | `` |
| `$.subsidy_category_name` | `—` |
| `$.expect_subsidy_category_name` | `—` |
| `$.real_subsidy_category_name` | `—` |
| `$.action` | `check` |

**Step 8 (idx=12, POST `/api/order/order/orderBook`)**

| jsonpath | literal |
|---|---|
| `$.client_expand_name` | `唐欣雨` |
| `$.m_delivery_type` | `` |
| `$.customer_id` | `320` |
| `$.customer_name` | `山东悦慕食品有限公司` |
| `$.service_id` | `55` |
| `$.service_name` | `曲静霞` |
| `$.operator_id` | `336` |
| `$.operator_name` | `闫航` |
| `$.customer_contact_id` | `` |
| `$.customer_contact_name` | `` |
| `$.main_sort` | `易汇瀚,易海,易航道` |
| `$.policy_id` | `134` |
| `$.policy_name` | `【SPV对客】易汇瀚（仅人民币）` |
| `$.policy_type` | `JSZX` |
| `$.service_items[0]` | `booking_space` |
| `$.business_type` | `1` |
| `$.trade_term` | `CIF` |
| `$.carrier` | `COSCO` |
| `$.carrier_id` | `16` |
| `$.ship_name` | `OOCL FRANCE` |
| `$.voy` | `068E` |
| `$.pol` | `QINGDAO,CHINA` |
| `$.pot` | `` |
| `$.pod` | `ANTING,CHINA` |
| `$.del` | `ANTING,CHINA` |
| `$.country_name` | `CHINA` |
| `$.airline_type` | `中国` |
| `$.ocean_type` | `近洋` |
| `$.terms_payment` | `T/T` |
| `$.terms_transport` | `CY/CY` |
| `$.pay_type` | `FREIGHT PREPAID` |
| `$.customer_order_sn` | `` |
| `$.terms_shipment` | `Codfish` |
| `$.shipper` | `Codfish` |
| `$.consignee` | `Codfish` |
| `$.notifier` | `Codfish` |
| `$.ship_mark` | `Codfish` |
| `$.commodity` | `Codfish` |
| `$.notes` | `Codfish` |
| `$.cargo_type` | `` |
| `$.packer` | `` |
| `$.num` | `1872` |
| `$.gross_weight` | `26800.000` |
| `$.bulk` | `60.000` |
| `$.sea_trans_cost` | `1.00` |
| `$.teu` | `2` |
| `$.volume` | `1*40HQ` |
| `$.volume_desc` | `普柜` |
| `$.order_sn` | `` |
| `$.sea_trans_currency` | `USD` |
| `$.container[0].order_container_id` | `330577156688052224` |
| `$.container[0].box_type` | `40HQ` |
| `$.container[0].box_num` | `1` |
| `$.container[0].box_no[0]` | `` |
| `$.container[0].seal_number[0]` | `` |
| `$.supplier[0].order_supplier_id` | `330576956728803328` |
| `$.supplier[0].order_id` | `330576955302739968` |
| `$.supplier[0].isset_supplier` | `1` |
| `$.supplier[0].is_primary` | `1` |
| `$.supplier[0].supplier_id` | `805` |
| `$.supplier[0].supplier_name` | `青岛雅然国际物流有限公司` |
| `$.supplier[0].settle_object_id` | `1384` |
| `$.supplier[0].user_id` | `336` |
| `$.supplier[0].user_name` | `闫航` |
| `$.supplier[0].service_item` | `booking_space` |
| `$.supplier[0].supplier_period` | `60` |
| `$.supplier[0].settlement_date` | `20` |
| `$.supplier[0].supplier_pay_date` | `0` |
| `$.supplier[0].is_manual` | `0` |
| `$.supplier[0].sys_upttime` | `2026-07-01 13:14:48` |
| `$.supplier[0].supplier_label` | `青岛雅然国际物流有限公司-订舱` |
| `$.supplier[0].service_item_name` | `订舱` |
| `$.order_id` | `330576955302739968` |
| `$.order_no` | `YWDD20260701107571` |
| `$.customer_category` | `,1,2,` |
| `$.customer_tax_number` | `91370786MA3D6MW35A` |
| `$.customer_address_cn` | `山东省潍坊市昌邑市围子街道206国道北(官道郜北)` |
| `$.client_expand_id` | `261` |
| `$.customer_contact_phone` | `` |
| `$.customer_main_id` | `15` |
| `$.customer_main_name` | `成都易汇瀚供应链管理有限公司` |
| `$.business_main_id` | `1` |
| `$.business_main_name` | `青岛易航道物流科技有限公司` |
| `$.fund_code` | `` |
| `$.track_atd` | `0` |
| `$.finance_date` | `1782316800` |
| `$.pol_cn` | `青岛流亭机场` |
| `$.pol_country_id` | `1` |
| `$.pol_country` | `CHINA` |
| `$.pol_country_cn` | `中国` |
| `$.pod_cn` | `` |
| `$.pot_cn` | `` |
| `$.del_cn` | `` |
| `$.country_id` | `1` |
| `$.country_name_cn` | `中国` |
| `$.customer_period` | `120` |
| `$.customer_settlement_date` | `10` |
| `$.period_rule` | `0` |
| `$.customer_due_date` | `0` |
| `$.customer_put_date` | `0` |
| `$.customer_put_date_manual` | `0` |
| `$.customer_put_writeoff_date` | `` |
| `$.supplier_due_date` | `0` |
| `$.discount_start` | `0` |
| `$.discount_rule` | `` |
| `$.discount_end` | `0` |
| `$.discount_ratio` | `` |
| `$.discount_status` | `2` |
| `$.discount_currency` | `` |
| `$.book_upload_date` | `0` |
| `$.trans_cost_put_preserve_date` | `0` |
| `$.bl_no_upload_date` | `0` |
| `$.supplier_invoice_date` | `0` |
| `$.supplier_invoice_taketime` | `` |
| `$.real_cost_date` | `0` |
| `$.customer_invoice_request_date` | `0` |
| `$.first_financing_doc_ok_date` | `0` |
| `$.second_financing_doc_ok_date` | `0` |
| `$.insurance_doc_ok_date` | `0` |
| `$.customer_confirm_date` | `0` |
| `$.is_delayed_recovery` | `否` |
| `$.delayed_recovery_usd` | `` |
| `$.delayed_recovery_cny` | `` |
| `$.delayed_time` | `` |
| `$.expect_fee_status` | `0` |
| `$.real_fee_status` | `0` |
| `$.fee_lock_status` | `0` |
| `$.pay_account_status` | `0` |
| `$.account_status` | `0` |
| `$.real_pay_usd` | `0.00` |
| `$.real_pay_cny` | `0.00` |
| `$.real_put_usd` | `0.00` |
| `$.real_put_cny` | `0.00` |
| `$.real_put_discount_rate` | `0.00` |
| `$.exchange_rate` | `6.8067` |
| `$.folde_pay_usd` | `0.00` |
| `$.folde_put_usd` | `0.00` |
| `$.folde_pay_total` | `0.00` |
| `$.folde_put_total` | `0.00` |
| `$.gross_margin` | `0.00` |
| `$.gross_margin_rate` | `0.00` |
| `$.is_special_pay` | `0` |
| `$.is_loan_before_invoice` | `0` |
| `$.is_fee_miss` | `0` |
| `$.fee_miss_name` | `` |
| `$.cancel_remark` | `` |
| `$.cancel_time` | `0` |
| `$.effective_id` | `0` |
| `$.effective_by` | `` |
| `$.effective_time` | `0` |
| `$.create_id` | `828` |
| `$.create_by` | `GIMBAL` |
| `$.create_time` | `1782882887` |
| `$.update_id` | `828` |
| `$.update_by` | `GIMBAL` |
| `$.update_time` | `1782882935` |
| `$.delete_time` | `0` |
| `$.business_time` | `0` |
| `$.main_ids` | `,15,16,1,` |
| `$.reverse_status` | `0` |
| `$.proprietary_business_status` | `0` |
| `$.loan_pay_status` | `` |
| `$.change_type` | `0` |
| `$.copy_order_id` | `0` |
| `$.is_usd_project` | `2` |
| `$.pay_status` | `1` |
| `$.is_sync_es` | `0` |
| `$.expect_discount_status` | `0` |
| `$.real_discount_status` | `0` |
| `$.entrust_status` | `2` |
| `$.remark` | `` |
| `$.audit_type` | `` |
| `$.is_system_generate` | `0` |
| `$.is_financing` | `0` |
| `$.confirm_status` | `0` |
| `$.is_traverse` | `0` |
| `$.financing_apply_amount` | `0.00` |
| `$.financing_apply_amount_cny` | `0.00` |
| `$.financing_apply_amount_usd` | `0.00` |
| `$.sys_upttime` | `2026-07-01 13:15:35` |
| `$.reverse_status_name` | `否` |
| `$.is_delayed_recovery_name` | `否` |
| `$.order_sub_no` | `` |
| `$.main_ids_name` | `易汇瀚,易海,易航道` |
| `$.policy_main_arr[0].fee_main_id` | `15` |
| `$.policy_main_arr[0].main_name` | `成都易汇瀚供应链管理有限公司` |
| `$.policy_main_arr[1].fee_main_id` | `16` |
| `$.policy_main_arr[1].main_name` | `青岛易海供应链管理有限公司` |
| `$.policy_main_arr[2].fee_main_id` | `1` |
| `$.policy_main_arr[2].main_name` | `青岛易航道物流科技有限公司` |
| `$.policy_type_name` | `结算业务` |
| `$.business_type_name` | `海运整箱` |
| `$.cargo_type_name` | `` |
| `$.period_rule_name` | `` |
| `$.trade_term_name` | `CIF` |
| `$.carrier_name` | `中国远洋运输（集团）总公司` |
| `$.terms_transport_name` | `CY/CY` |
| `$.terms_payment_name` | `T/T` |
| `$.pay_type_name` | `FREIGHT PREPAID` |
| `$.m_delivery_type_name` | `` |
| `$.enable` | `1` |
| `$.policy_match` | `semi` |
| `$.policy_match_name` | `手动选择` |
| `$.real_discount_status_name` | `—` |
| `$.expect_discount_status_name` | `—` |
| `$.expect_policy_status_name` | `` |
| `$.policy_status_name` | `` |
| `$.subsidy_category_name` | `—` |
| `$.expect_subsidy_category_name` | `—` |
| `$.real_subsidy_category_name` | `—` |
| `$.action` | `check` |

**Step 9 (idx=13, POST `/api/order/order/orderAdd`)**

| jsonpath | literal |
|---|---|
| `$.client_expand_name` | `唐欣雨` |
| `$.m_delivery_type` | `` |
| `$.customer_id` | `320` |
| `$.customer_name` | `山东悦慕食品有限公司` |
| `$.service_id` | `55` |
| `$.service_name` | `曲静霞` |
| `$.operator_id` | `336` |
| `$.operator_name` | `闫航` |
| `$.customer_contact_id` | `` |
| `$.customer_contact_name` | `` |
| `$.main_sort` | `易汇瀚,易海,易航道` |
| `$.policy_id` | `134` |
| `$.policy_name` | `【SPV对客】易汇瀚（仅人民币）` |
| `$.policy_type` | `JSZX` |
| `$.service_items[0]` | `booking_space` |
| `$.business_type` | `1` |
| `$.trade_term` | `CIF` |
| `$.carrier` | `COSCO` |
| `$.carrier_id` | `16` |
| `$.ship_name` | `OOCL FRANCE` |
| `$.voy` | `068E` |
| `$.pol` | `QINGDAO,CHINA` |
| `$.pot` | `` |
| `$.pod` | `ANTING,CHINA` |
| `$.del` | `ANTING,CHINA` |
| `$.country_name` | `CHINA` |
| `$.airline_type` | `中国` |
| `$.ocean_type` | `近洋` |
| `$.terms_payment` | `T/T` |
| `$.terms_transport` | `CY/CY` |
| `$.pay_type` | `FREIGHT PREPAID` |
| `$.customer_order_sn` | `` |
| `$.terms_shipment` | `Codfish` |
| `$.shipper` | `Codfish` |
| `$.consignee` | `Codfish` |
| `$.notifier` | `Codfish` |
| `$.ship_mark` | `Codfish` |
| `$.commodity` | `Codfish` |
| `$.notes` | `Codfish` |
| `$.cargo_type` | `` |
| `$.packer` | `` |
| `$.num` | `1872` |
| `$.gross_weight` | `26800.000` |
| `$.bulk` | `60.000` |
| `$.sea_trans_cost` | `1.00` |
| `$.teu` | `2` |
| `$.volume` | `1*40HQ` |
| `$.volume_desc` | `普柜` |
| `$.order_sn` | `` |
| `$.sea_trans_currency` | `USD` |
| `$.container[0].order_container_id` | `330577156688052224` |
| `$.container[0].box_type` | `40HQ` |
| `$.container[0].box_num` | `1` |
| `$.container[0].box_no[0]` | `` |
| `$.container[0].seal_number[0]` | `` |
| `$.customer_file_list[0].client_company_id` | `320` |
| `$.customer_file_list[0].client_company_name` | `山东悦慕食品有限公司` |
| `$.customer_file_list[0].trustee_company_id` | `15` |
| `$.customer_file_list[0].trustee_company_name` | `成都易汇瀚供应链管理有限公司` |
| `$.customer_file_list[0].document_type` | `BOOK_CUSTOMER` |
| `$.customer_file_list[0].file_url` | `6a44a28c0c41b.pdf` |
| `$.customer_file_list[0].file_name` | `6a44a28c0c41b.pdf` |
| `$.customer_file_list[0].file_id` | `330577242251853824` |
| `$.customer_file_list[0].file_type` | `PDF` |
| `$.customer_file_list[0]._XID` | `row_384` |
| `$.supplier[0].order_supplier_id` | `330576956728803328` |
| `$.supplier[0].order_id` | `330576955302739968` |
| `$.supplier[0].isset_supplier` | `1` |
| `$.supplier[0].is_primary` | `1` |
| `$.supplier[0].supplier_id` | `805` |
| `$.supplier[0].supplier_name` | `青岛雅然国际物流有限公司` |
| `$.supplier[0].settle_object_id` | `1384` |
| `$.supplier[0].user_id` | `336` |
| `$.supplier[0].user_name` | `闫航` |
| `$.supplier[0].service_item` | `booking_space` |
| `$.supplier[0].supplier_period` | `60` |
| `$.supplier[0].settlement_date` | `20` |
| `$.supplier[0].supplier_pay_date` | `0` |
| `$.supplier[0].is_manual` | `0` |
| `$.supplier[0].sys_upttime` | `2026-07-01 13:14:48` |
| `$.supplier[0].supplier_label` | `青岛雅然国际物流有限公司-订舱` |
| `$.supplier[0].service_item_name` | `订舱` |
| `$.order_id` | `330576955302739968` |
| `$.order_no` | `YWDD20260701107571` |
| `$.customer_category` | `,1,2,` |
| `$.customer_tax_number` | `91370786MA3D6MW35A` |
| `$.customer_address_cn` | `山东省潍坊市昌邑市围子街道206国道北(官道郜北)` |
| `$.client_expand_id` | `261` |
| `$.customer_contact_phone` | `` |
| `$.customer_main_id` | `15` |
| `$.customer_main_name` | `成都易汇瀚供应链管理有限公司` |
| `$.business_main_id` | `1` |
| `$.business_main_name` | `青岛易航道物流科技有限公司` |
| `$.fund_code` | `` |
| `$.track_atd` | `0` |
| `$.finance_date` | `1782316800` |
| `$.pol_cn` | `青岛流亭机场` |
| `$.pol_country_id` | `1` |
| `$.pol_country` | `CHINA` |
| `$.pol_country_cn` | `中国` |
| `$.pod_cn` | `` |
| `$.pot_cn` | `` |
| `$.del_cn` | `` |
| `$.country_id` | `1` |
| `$.country_name_cn` | `中国` |
| `$.customer_period` | `120` |
| `$.customer_settlement_date` | `10` |
| `$.period_rule` | `0` |
| `$.customer_due_date` | `0` |
| `$.customer_put_date` | `0` |
| `$.customer_put_date_manual` | `0` |
| `$.customer_put_writeoff_date` | `` |
| `$.supplier_due_date` | `0` |
| `$.discount_start` | `0` |
| `$.discount_rule` | `` |
| `$.discount_end` | `0` |
| `$.discount_ratio` | `` |
| `$.discount_status` | `2` |
| `$.discount_currency` | `` |
| `$.book_upload_date` | `0` |
| `$.trans_cost_put_preserve_date` | `0` |
| `$.bl_no_upload_date` | `0` |
| `$.supplier_invoice_date` | `0` |
| `$.supplier_invoice_taketime` | `` |
| `$.real_cost_date` | `0` |
| `$.customer_invoice_request_date` | `0` |
| `$.first_financing_doc_ok_date` | `0` |
| `$.second_financing_doc_ok_date` | `0` |
| `$.insurance_doc_ok_date` | `0` |
| `$.customer_confirm_date` | `0` |
| `$.is_delayed_recovery` | `否` |
| `$.delayed_recovery_usd` | `` |
| `$.delayed_recovery_cny` | `` |
| `$.delayed_time` | `` |
| `$.expect_fee_status` | `0` |
| `$.real_fee_status` | `0` |
| `$.fee_lock_status` | `0` |
| `$.pay_account_status` | `0` |
| `$.account_status` | `0` |
| `$.real_pay_usd` | `0.00` |
| `$.real_pay_cny` | `0.00` |
| `$.real_put_usd` | `0.00` |
| `$.real_put_cny` | `0.00` |
| `$.real_put_discount_rate` | `0.00` |
| `$.exchange_rate` | `6.8067` |
| `$.folde_pay_usd` | `0.00` |
| `$.folde_put_usd` | `0.00` |
| `$.folde_pay_total` | `0.00` |
| `$.folde_put_total` | `0.00` |
| `$.gross_margin` | `0.00` |
| `$.gross_margin_rate` | `0.00` |
| `$.is_special_pay` | `0` |
| `$.is_loan_before_invoice` | `0` |
| `$.is_fee_miss` | `0` |
| `$.fee_miss_name` | `` |
| `$.cancel_remark` | `` |
| `$.cancel_time` | `0` |
| `$.effective_id` | `0` |
| `$.effective_by` | `` |
| `$.effective_time` | `0` |
| `$.create_id` | `828` |
| `$.create_by` | `GIMBAL` |
| `$.create_time` | `1782882887` |
| `$.update_id` | `828` |
| `$.update_by` | `GIMBAL` |
| `$.update_time` | `1782882935` |
| `$.delete_time` | `0` |
| `$.business_time` | `0` |
| `$.main_ids` | `,15,16,1,` |
| `$.reverse_status` | `0` |
| `$.proprietary_business_status` | `0` |
| `$.loan_pay_status` | `` |
| `$.change_type` | `0` |
| `$.copy_order_id` | `0` |
| `$.is_usd_project` | `2` |
| `$.pay_status` | `1` |
| `$.is_sync_es` | `0` |
| `$.expect_discount_status` | `0` |
| `$.real_discount_status` | `0` |
| `$.entrust_status` | `2` |
| `$.remark` | `` |
| `$.audit_type` | `` |
| `$.is_system_generate` | `0` |
| `$.is_financing` | `0` |
| `$.confirm_status` | `0` |
| `$.is_traverse` | `0` |
| `$.financing_apply_amount` | `0.00` |
| `$.financing_apply_amount_cny` | `0.00` |
| `$.financing_apply_amount_usd` | `0.00` |
| `$.sys_upttime` | `2026-07-01 13:15:35` |
| `$.reverse_status_name` | `否` |
| `$.is_delayed_recovery_name` | `否` |
| `$.order_sub_no` | `` |
| `$.main_ids_name` | `易汇瀚,易海,易航道` |
| `$.policy_main_arr[0].fee_main_id` | `15` |
| `$.policy_main_arr[0].main_name` | `成都易汇瀚供应链管理有限公司` |
| `$.policy_main_arr[1].fee_main_id` | `16` |
| `$.policy_main_arr[1].main_name` | `青岛易海供应链管理有限公司` |
| `$.policy_main_arr[2].fee_main_id` | `1` |
| `$.policy_main_arr[2].main_name` | `青岛易航道物流科技有限公司` |
| `$.policy_type_name` | `结算业务` |
| `$.business_type_name` | `海运整箱` |
| `$.cargo_type_name` | `` |
| `$.period_rule_name` | `` |
| `$.trade_term_name` | `CIF` |
| `$.carrier_name` | `中国远洋运输（集团）总公司` |
| `$.terms_transport_name` | `CY/CY` |
| `$.terms_payment_name` | `T/T` |
| `$.pay_type_name` | `FREIGHT PREPAID` |
| `$.m_delivery_type_name` | `` |
| `$.enable` | `1` |
| `$.policy_match` | `semi` |
| `$.policy_match_name` | `手动选择` |
| `$.real_discount_status_name` | `—` |
| `$.expect_discount_status_name` | `—` |
| `$.expect_policy_status_name` | `` |
| `$.policy_status_name` | `` |
| `$.subsidy_category_name` | `—` |
| `$.expect_subsidy_category_name` | `—` |
| `$.real_subsidy_category_name` | `—` |
| `$.action` | `submit` |

**Step 10 (idx=14, POST `/api/order/order/orderPage`)**

| jsonpath | literal |
|---|---|
| `$.sort_field` | `update_time` |
| `$.sort_order` | `desc` |

**Step 11 (idx=16, POST `/api/order/orderFee/toggleRealAmount`)**

| jsonpath | literal |
|---|---|
| `$.order_id` | `330576955302739968` |

**Step 12 (idx=17, POST `/api/order/orderFee/bookRealAmountEdit`)**

| jsonpath | literal |
|---|---|
| `$.action` | `check` |
| `$.order_id` | `330576955302739968` |
| `$.discount_ratio` | `` |
| `$.service_project` | `booking_space` |
| `$.to_customer.put_amount.standard_list[0].policy_sub_id` | `470` |
| `$.to_customer.put_amount.standard_list[0].service_project` | `booking_space` |
| `$.to_customer.put_amount.standard_list[0].cost_id` | `17` |
| `$.to_customer.put_amount.standard_list[0].settle_object_id` | `829` |
| `$.to_customer.put_amount.standard_list[0].subsidy_category` | `0` |
| `$.to_customer.put_amount.standard_list[0].currency` | `USD` |
| `$.to_customer.put_amount.standard_list[0].unit_price` | `1` |
| `$.to_customer.put_amount.standard_list[0].unit` | `box` |
| `$.to_customer.put_amount.standard_list[0].specs` | `40HQ` |
| `$.to_customer.put_amount.standard_list[0].num` | `1` |
| `$.to_customer.put_amount.standard_list[0].discount_amount` | `1.00` |
| `$.to_customer.put_amount.standard_list[0].discount_status` | `0` |
| `$.to_customer.put_amount.standard_list[0].policy_sub_status_name` | `正常` |
| `$.to_customer.put_amount.standard_list[0].unique_id` | `61abfbc5-106d-45e2-8a83-0fbacbd7c648` |
| `$.to_customer.put_amount.standard_list[0].init_main_name` | `成都易汇瀚供应链管理有限公司` |
| `$.to_customer.put_amount.standard_list[0].main_name` | `成都易汇瀚供应链管理有限公司` |
| `$.to_supplier.pay_amount.standard_list[0].policy_sub_id` | `470` |
| `$.to_supplier.pay_amount.standard_list[0].service_project` | `booking_space` |
| `$.to_supplier.pay_amount.standard_list[0].cost_id` | `17` |
| `$.to_supplier.pay_amount.standard_list[0].settle_object_id` | `1384` |
| `$.to_supplier.pay_amount.standard_list[0].subsidy_category` | `0` |
| `$.to_supplier.pay_amount.standard_list[0].currency` | `USD` |
| `$.to_supplier.pay_amount.standard_list[0].unit_price` | `1` |
| `$.to_supplier.pay_amount.standard_list[0].unit` | `box` |
| `$.to_supplier.pay_amount.standard_list[0].specs` | `40HQ` |
| `$.to_supplier.pay_amount.standard_list[0].num` | `1` |
| `$.to_supplier.pay_amount.standard_list[0].discount_amount` | `1.00` |
| `$.to_supplier.pay_amount.standard_list[0].discount_status` | `0` |
| `$.to_supplier.pay_amount.standard_list[0].policy_sub_status_name` | `异常` |
| `$.to_supplier.pay_amount.standard_list[0].unique_id` | `61abfbc5-106d-45e2-8a83-0fbacbd7c648` |
| `$.to_supplier.pay_amount.standard_list[0].init_main_name` | `—` |
| `$.to_supplier.pay_amount.standard_list[0].main_name` | `成都易汇瀚供应链管理有限公司` |
| `$.to_supplier.pay_amount.standard_list[0].related_unique_id` | `61abfbc5-106d-45e2-8a83-0fbacbd7c648` |

**Step 13 (idx=18, POST `/api/order/orderFee/bookRealAmountEdit`)**

| jsonpath | literal |
|---|---|
| `$.action` | `submit` |
| `$.order_id` | `330576955302739968` |
| `$.discount_ratio` | `` |
| `$.service_project` | `booking_space` |
| `$.to_customer.put_amount.standard_list[0].policy_sub_id` | `470` |
| `$.to_customer.put_amount.standard_list[0].service_project` | `booking_space` |
| `$.to_customer.put_amount.standard_list[0].cost_id` | `17` |
| `$.to_customer.put_amount.standard_list[0].settle_object_id` | `829` |
| `$.to_customer.put_amount.standard_list[0].subsidy_category` | `0` |
| `$.to_customer.put_amount.standard_list[0].currency` | `USD` |
| `$.to_customer.put_amount.standard_list[0].unit_price` | `1` |
| `$.to_customer.put_amount.standard_list[0].unit` | `box` |
| `$.to_customer.put_amount.standard_list[0].specs` | `40HQ` |
| `$.to_customer.put_amount.standard_list[0].num` | `1` |
| `$.to_customer.put_amount.standard_list[0].discount_amount` | `1.00` |
| `$.to_customer.put_amount.standard_list[0].discount_status` | `0` |
| `$.to_customer.put_amount.standard_list[0].policy_sub_status_name` | `正常` |
| `$.to_customer.put_amount.standard_list[0].unique_id` | `61abfbc5-106d-45e2-8a83-0fbacbd7c648` |
| `$.to_customer.put_amount.standard_list[0].init_main_name` | `成都易汇瀚供应链管理有限公司` |
| `$.to_customer.put_amount.standard_list[0].main_name` | `成都易汇瀚供应链管理有限公司` |
| `$.to_supplier.pay_amount.standard_list[0].policy_sub_id` | `470` |
| `$.to_supplier.pay_amount.standard_list[0].service_project` | `booking_space` |
| `$.to_supplier.pay_amount.standard_list[0].cost_id` | `17` |
| `$.to_supplier.pay_amount.standard_list[0].settle_object_id` | `1384` |
| `$.to_supplier.pay_amount.standard_list[0].subsidy_category` | `0` |
| `$.to_supplier.pay_amount.standard_list[0].currency` | `USD` |
| `$.to_supplier.pay_amount.standard_list[0].unit_price` | `1` |
| `$.to_supplier.pay_amount.standard_list[0].unit` | `box` |
| `$.to_supplier.pay_amount.standard_list[0].specs` | `40HQ` |
| `$.to_supplier.pay_amount.standard_list[0].num` | `1` |
| `$.to_supplier.pay_amount.standard_list[0].discount_amount` | `1.00` |
| `$.to_supplier.pay_amount.standard_list[0].discount_status` | `0` |
| `$.to_supplier.pay_amount.standard_list[0].policy_sub_status_name` | `异常` |
| `$.to_supplier.pay_amount.standard_list[0].unique_id` | `61abfbc5-106d-45e2-8a83-0fbacbd7c648` |
| `$.to_supplier.pay_amount.standard_list[0].init_main_name` | `—` |
| `$.to_supplier.pay_amount.standard_list[0].main_name` | `成都易汇瀚供应链管理有限公司` |
| `$.to_supplier.pay_amount.standard_list[0].related_unique_id` | `61abfbc5-106d-45e2-8a83-0fbacbd7c648` |

**Step 14 (idx=21, POST `/api/order/order/checkGenerateOrderSub`)**

| jsonpath | literal |
|---|---|
| `$.order_id` | `330576955302739968` |

**Step 15 (idx=22, POST `/api/order/order/generateOrderSub`)**

| jsonpath | literal |
|---|---|
| `$.order_id` | `330576955302739968` |

**Step 16 (idx=24, POST `/api/order/orderFee/toggleRealAmount`)**

| jsonpath | literal |
|---|---|
| `$.order_id` | `330576955302739968` |

**Step 17 (idx=25, POST `/api/order/orderFee/realAmountLockSubmit`)**

| jsonpath | literal |
|---|---|
| `$.action` | `check` |
| `$.order_id` | `330576955302739968` |
| `$.order_fee_real_ids[0]` | `330577494820257792` |

**Step 18 (idx=26, POST `/api/order/orderFee/realAmountLockSubmit`)**

| jsonpath | literal |
|---|---|
| `$.action` | `audit` |
| `$.order_id` | `330576955302739968` |
| `$.order_fee_real_ids[0]` | `330577494820257792` |

**Step 19 (idx=27, POST `/api/order/orderFee/realAmountLockSubmit`)**

| jsonpath | literal |
|---|---|
| `$.action` | `submit` |
| `$.order_id` | `330576955302739968` |
| `$.order_fee_real_ids[0]` | `330577494820257792` |
| `$.audit_msg.title` | `业务订单ID` |
| `$.audit_msg.code` | `ZDD20260701016910` |
| `$.audit_msg.msgs[0]` | `费用锁定申请` |
| `$.select_node_user[0].node_sort` | `0` |
| `$.select_node_user[0].user_id` | `828` |

**Step 20 (idx=29, POST `/api/order/order/orderDetail`)**

| jsonpath | literal |
|---|---|
| `$.order_id` | `330576955302739968` |

**Step 21 (idx=33, POST `/api/home/audit/auditExecute`)**

| jsonpath | literal |
|---|---|
| `$.audit_ids[0]` | `330577547932729344` |

**Step 22 (idx=38, POST `/api/order/order/orderDetail`)**

| jsonpath | literal |
|---|---|
| `$.order_id` | `330576955302739968` |

**Step 23 (idx=42, POST `/api/home/audit/auditExecute`)**

| jsonpath | literal |
|---|---|
| `$.audit_ids[0]` | `330577661850025984` |
