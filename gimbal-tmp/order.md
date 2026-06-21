# 业务请求过程

1\. 订单创建检查

https://fin-tidb.21eflag.com/api/order/orderEntrust/orderAdd

```json
{"client_expand_name":"孙硕","client_expand_id":"250","m_delivery_type":"1","customer_id":"16","customer_name":"","service_id":"55","service_name":"曲静霞","operator_id":"327","operator_name":"","customer_contact_id":"1547","customer_contact_name":"","main_sort":"易汇智-易航道","policy_id":"112","policy_name":"【SPV对客】易汇智","policy_type":"JSZX","service_items":["booking_space"],"business_type":"1","trade_term":"CIF","carrier":"ACL","carrier_id":"1","bl_no":"codfishe2e1","etd":1781020800,"atd":1781020800,"ship_name":"codfishe2e1","voy":"codfishe2e1","pol":"QINGDAO,CHINA","pot":"QINGDAO,CHINA","pod":"QINGDAO,CHINA","del":"QINGDAO,CHINA","country_name":"CHINA","airline_type":"中国","ocean_type":"近洋","terms_payment":"T/T","terms_transport":"CY/CY","pay_type":"FREIGHT PREPAID","customer_order_sn":"codfishe2e1","terms_shipment":"codfishe2e1","shipper":"codfishe2e1","consignee":"codfishe2e1","notifier":"codfishe2e1","ship_mark":"codfishe2e1","commodity":"codfishe2e1","notes":"codfishe2e1","cargo_type":"goods","packer":"","num":"1","gross_weight":"100","bulk":"100","sea_trans_cost":"100.00","teu":"","volume":"1*40HQ","volume_desc":"普柜","order_sn":"","status":"1","sea_trans_currency":"USD","container":[{"box_type":"40HQ","box_num":"1","box_no":["1"],"seal_number":[""],"sea_trans_unit_price":"100"}],"message_board":[],"customer_file_list":[],"supplier":[{"is_manual":"","is_primary":"1","isset_fee":"0","isset_supplier":"1","order_id":"","order_supplier_id":"","service_item":"booking_space","service_item_name":"订舱","settle_object_id":"","settlement_date":null,"supplier_id":"8","supplier_name":"上海华运船务有限公司青岛分公司","supplier_pay_date":null,"supplier_period":null,"user_id":"16","user_name":"荣洋"}],"remark":"","policy_type_name":"","main_ids":"31,1","pol_cn":"青岛流亭机场","pol_port_name":"QINGDAO,CHINA","pol_country_id":"1","pol_country":"CHINA","pol_country_cn":"中国","pot_cn":"青岛港","pot_port_name":"QINGDAO,CHINA","pod_cn":"青岛港","pod_port_name":"QINGDAO,CHINA","del_cn":"青岛港","del_port_name":"QINGDAO,CHINA","country_id":"1","country_name_cn":"中国","action":"check","entrust_status":1,"order_file":[]}
```


2. 订单创建提交

https://fin-tidb.21eflag.com/api/order/orderEntrust/orderAdd

```json
{"client_expand_name":"孙硕","client_expand_id":"250","m_delivery_type":"1","customer_id":"16","customer_name":"","service_id":"55","service_name":"曲静霞","operator_id":"327","operator_name":"","customer_contact_id":"1547","customer_contact_name":"","main_sort":"易汇智-易航道","policy_id":"112","policy_name":"【SPV对客】易汇智","policy_type":"JSZX","service_items":["booking_space"],"business_type":"1","trade_term":"CIF","carrier":"ACL","carrier_id":"1","bl_no":"codfishe2e1","etd":1781020800,"atd":1781020800,"ship_name":"codfishe2e1","voy":"codfishe2e1","pol":"QINGDAO,CHINA","pot":"QINGDAO,CHINA","pod":"QINGDAO,CHINA","del":"QINGDAO,CHINA","country_name":"CHINA","airline_type":"中国","ocean_type":"近洋","terms_payment":"T/T","terms_transport":"CY/CY","pay_type":"FREIGHT PREPAID","customer_order_sn":"codfishe2e1","terms_shipment":"codfishe2e1","shipper":"codfishe2e1","consignee":"codfishe2e1","notifier":"codfishe2e1","ship_mark":"codfishe2e1","commodity":"codfishe2e1","notes":"codfishe2e1","cargo_type":"goods","packer":"","num":"1","gross_weight":"100","bulk":"100","sea_trans_cost":"100.00","teu":"","volume":"1*40HQ","volume_desc":"普柜","order_sn":"","status":"1","sea_trans_currency":"USD","container":[{"box_type":"40HQ","box_num":"1","box_no":["1"],"seal_number":[""],"sea_trans_unit_price":"100"}],"message_board":[],"customer_file_list":[],"supplier":[{"is_manual":"","is_primary":"1","isset_fee":"0","isset_supplier":"1","order_id":"","order_supplier_id":"","service_item":"booking_space","service_item_name":"订舱","settle_object_id":"","settlement_date":null,"supplier_id":"8","supplier_name":"上海华运船务有限公司青岛分公司","supplier_pay_date":null,"supplier_period":null,"user_id":"16","user_name":"荣洋"}],"remark":"","policy_type_name":"","main_ids":"31,1","pol_cn":"青岛流亭机场","pol_port_name":"QINGDAO,CHINA","pol_country_id":"1","pol_country":"CHINA","pol_country_cn":"中国","pot_cn":"青岛港","pot_port_name":"QINGDAO,CHINA","pod_cn":"青岛港","pod_port_name":"QINGDAO,CHINA","del_cn":"青岛港","del_port_name":"QINGDAO,CHINA","country_id":"1","country_name_cn":"中国","action":"submit","entrust_status":1,"order_file":[]}
```


3. 查询订单获取订单号信息

https://fin-tidb.21eflag.com/api/order/orderEntrust/orderPage

```json
{"page_no":1,"page_size":20,"order_no":"","customer_id":[],"bl_nos":[],"bl_no":"codfishe2e1","sort_field":"update_time","sort_order":"desc","params":{}}
```


4. 查询订单接口 

https://fin-tidb.21eflag.com/api/order/order/orderDetail

```json
{"order_id":"322933109106409472"}
```


5. 分发

https://fin-tidb.21eflag.com/api/order/orderEntrust/orderAdd

```json
{"client_expand_name":"孙硕","client_expand_id":"250","m_delivery_type":"1","customer_id":"16","customer_name":"兰森玻璃（青岛）有限公司","service_id":"55","service_name":"曲静霞","operator_id":"327","operator_name":"王晓涵","customer_contact_id":"1547","customer_contact_name":"周经理","main_sort":"易汇智,易航道","policy_id":"112","policy_name":"【SPV对客】易汇智","policy_type":"JSZX","service_items":["booking_space"],"business_type":"1","trade_term":"CIF","carrier":"ACL","carrier_id":"1","bl_no":"codfishe2e1","etd":1781020800,"atd":1781020800,"ship_name":"codfishe2e1","voy":"codfishe2e1","pol":"QINGDAO,CHINA","pot":"QINGDAO,CHINA","pod":"QINGDAO,CHINA","del":"QINGDAO,CHINA","country_name":"CHINA","airline_type":"中国","ocean_type":"近洋","terms_payment":"T/T","terms_transport":"CY/CY","pay_type":"FREIGHT PREPAID","customer_order_sn":"codfishe2e1","terms_shipment":"codfishe2e1","shipper":"codfishe2e1","consignee":"codfishe2e1","notifier":"codfishe2e1","ship_mark":"codfishe2e1","commodity":"codfishe2e1","notes":"codfishe2e1","cargo_type":"goods","packer":"","num":"1","gross_weight":"100.000","bulk":"100.000","sea_trans_cost":"100.00","teu":"2","volume":"1*40HQ","volume_desc":"普柜","order_sn":"","status":"1","sea_trans_currency":"USD","container":[{"order_container_id":"322933109785886720","box_type":"40HQ","box_num":"1","box_no":["1"],"seal_number":[""],"sea_trans_unit_price":100}],"message_board":[],"customer_file_list":[],"supplier":[{"order_supplier_id":"322933110742188032","order_id":"322933109106409472","isset_supplier":"1","is_primary":"1","supplier_id":"8","supplier_name":"上海华运船务有限公司青岛分公司","settle_object_id":"39","user_id":"16","user_name":"荣洋","service_item":"booking_space","supplier_period":"30","settlement_date":"20","supplier_pay_date":"0","is_manual":"0","sys_upttime":"2026-06-10 11:00:53","supplier_label":"上海华运船务有限公司青岛分公司-订舱","service_item_name":"订舱","isset_fee":false}],"remark":"","order_id":"322933109106409472","order_no":"YWDD20260610106678","customer_category":",2,","customer_tax_number":"91370283591262431N","customer_address_cn":"山东省青岛市平度市南村镇东王府庄村","customer_contact_phone":"18561657088","customer_main_id":"31","customer_main_name":"青岛易汇智供应链管理有限公司","business_main_id":"1","business_main_name":"青岛易航道物流科技有限公司","fund_code":"","fund_name":null,"track_atd":"0","finance_date":"1781020800","pol_cn":"青岛流亭机场","pol_country_id":"1","pol_country":"CHINA","pol_country_cn":"中国","pod_cn":"青岛港","pot_cn":"青岛港","del_cn":"青岛港","country_id":"1","country_name_cn":"中国","customer_period":"60","customer_settlement_date":"10","period_rule":"0","term_rule_name":null,"customer_due_date":"0","customer_put_date":"0","customer_payment_collection_date":null,"customer_put_date_manual":"0","customer_put_writeoff_date":"","supplier_due_date":"0","discount_start":"0","discount_rule":"","discount_end":"0","discount_ratio":"","discount_status":"2","discount_currency":"","book_upload_date":"0","trans_cost_put_preserve_date":"0","bl_no_upload_date":"0","supplier_invoice_date":"0","supplier_invoice_taketime":"","real_cost_date":"0","customer_invoice_request_date":"0","first_financing_doc_ok_date":"0","second_financing_doc_ok_date":"0","insurance_doc_ok_date":"0","customer_confirm_date":"0","is_delayed_recovery":"否","delayed_recovery_usd":"","delayed_recovery_cny":"","delayed_time":"","expect_fee_status":"0","real_fee_status":"0","fee_lock_status":"0","pay_account_status":"0","account_status":"0","real_pay_usd":"0.00","real_pay_cny":"0.00","real_put_usd":"0.00","real_put_cny":"0.00","real_put_discount_rate":"0.00","exchange_rate":"0.0000","folde_pay_usd":"0.00","folde_put_usd":"0.00","folde_pay_total":"0.00","folde_put_total":"0.00","gross_margin":"0.00","gross_margin_rate":"0.00","is_special_pay":"0","is_loan_before_invoice":"0","is_fee_miss":"0","fee_miss_name":"","cancel_remark":"","cancel_time":"0","effective_id":"0","effective_by":"","effective_time":"0","create_id":"828","create_by":"GIMBAL","create_time":"1781060453","update_id":"828","update_by":"GIMBAL","update_time":"1781060453","delete_time":"0","business_time":"0","main_ids":"31,1","reverse_status":"0","proprietary_business_status":"0","loan_status":null,"first_status":null,"second_status":null,"loan_pay_status":"","change_type":"0","copy_order_id":"0","real_fee_locked":false,"is_usd_project":"2","pay_status":"1","is_sync_es":"0","expect_discount_status":"0","real_discount_status":"0","entrust_status":2,"audit_type":"","is_system_generate":"0","is_financing":"0","confirm_status":"0","is_traverse":"0","financing_apply_amount":"0.00","financing_apply_amount_cny":"0.00","financing_apply_amount_usd":"0.00","sys_upttime":"2026-06-10 11:00:53","reverse_status_name":"否","is_delayed_recovery_name":"否","order_finance_arr":[],"order_main_bank_arr":[],"order_sub":[],"order_sub_no":"","service_project":{"booking_space":false,"customs_clearance":false,"manifest":false,"insurance":false,"trucking":false},"service_project_amount":{"booking_space":false,"customs_clearance":false,"manifest":false,"insurance":false,"trucking":false},"finance_status":true,"main_ids_name":"易汇智,易航道","policy_main_arr":[{"fee_main_id":"31","main_name":"青岛易汇智供应链管理有限公司"},{"fee_main_id":"1","main_name":"青岛易航道物流科技有限公司"}],"policy_type_name":"结算业务","business_type_name":"海运整箱","cargo_type_name":"普货","period_rule_name":"","trade_term_name":"CIF","carrier_name":"大西洋航运","terms_transport_name":"CY/CY","terms_payment_name":"T/T","pay_type_name":"FREIGHT PREPAID","m_delivery_type_name":"正本","audit":[],"enable":"1","policy_match":"semi","policy_match_name":"手动选择","real_discount_status_name":"—","expect_discount_status_name":"—","expect_policy_status_name":"","policy_status_name":"","subsidy_category_name":"—","expect_subsidy_category_name":"—","real_subsidy_category_name":"—","action":"check","order_file":[]}
```


6. 分发的托单确认（不必接口化）

https://fin-tidb.21eflag.com/api/order/OrderEntrust/checkOrderCustomerContainer

```json
{"customer_id":"16","order_id":"322933109106409472","container":[{"order_container_id":"322933109785886720","box_type":"40HQ","box_num":"1","box_no":["1"],"seal_number":[""],"sea_trans_unit_price":100}],"policy_type":"JSZX"}
```


7. 提交分发

https://fin-tidb.21eflag.com/api/order/orderEntrust/orderAdd

```json
{"client_expand_name":"孙硕","client_expand_id":"250","m_delivery_type":"1","customer_id":"16","customer_name":"兰森玻璃（青岛）有限公司","service_id":"55","service_name":"曲静霞","operator_id":"327","operator_name":"王晓涵","customer_contact_id":"1547","customer_contact_name":"周经理","main_sort":"易汇智,易航道","policy_id":"112","policy_name":"【SPV对客】易汇智","policy_type":"JSZX","service_items":["booking_space"],"business_type":"1","trade_term":"CIF","carrier":"ACL","carrier_id":"1","bl_no":"codfishe2e1","etd":1781020800,"atd":1781020800,"ship_name":"codfishe2e1","voy":"codfishe2e1","pol":"QINGDAO,CHINA","pot":"QINGDAO,CHINA","pod":"QINGDAO,CHINA","del":"QINGDAO,CHINA","country_name":"CHINA","airline_type":"中国","ocean_type":"近洋","terms_payment":"T/T","terms_transport":"CY/CY","pay_type":"FREIGHT PREPAID","customer_order_sn":"codfishe2e1","terms_shipment":"codfishe2e1","shipper":"codfishe2e1","consignee":"codfishe2e1","notifier":"codfishe2e1","ship_mark":"codfishe2e1","commodity":"codfishe2e1","notes":"codfishe2e1","cargo_type":"goods","packer":"","num":"1","gross_weight":"100.000","bulk":"100.000","sea_trans_cost":"100.00","teu":"2","volume":"1*40HQ","volume_desc":"普柜","order_sn":"","status":"1","sea_trans_currency":"USD","container":[{"order_container_id":"322933109785886720","box_type":"40HQ","box_num":"1","box_no":["1"],"seal_number":[""],"sea_trans_unit_price":100}],"message_board":[],"customer_file_list":[],"supplier":[{"order_supplier_id":"322933110742188032","order_id":"322933109106409472","isset_supplier":"1","is_primary":"1","supplier_id":"8","supplier_name":"上海华运船务有限公司青岛分公司","settle_object_id":"39","user_id":"16","user_name":"荣洋","service_item":"booking_space","supplier_period":"30","settlement_date":"20","supplier_pay_date":"0","is_manual":"0","sys_upttime":"2026-06-10 11:00:53","supplier_label":"上海华运船务有限公司青岛分公司-订舱","service_item_name":"订舱","isset_fee":false}],"remark":"","order_id":"322933109106409472","order_no":"YWDD20260610106678","customer_category":",2,","customer_tax_number":"91370283591262431N","customer_address_cn":"山东省青岛市平度市南村镇东王府庄村","customer_contact_phone":"18561657088","customer_main_id":"31","customer_main_name":"青岛易汇智供应链管理有限公司","business_main_id":"1","business_main_name":"青岛易航道物流科技有限公司","fund_code":"","fund_name":null,"track_atd":"0","finance_date":"1781020800","pol_cn":"青岛流亭机场","pol_country_id":"1","pol_country":"CHINA","pol_country_cn":"中国","pod_cn":"青岛港","pot_cn":"青岛港","del_cn":"青岛港","country_id":"1","country_name_cn":"中国","customer_period":"60","customer_settlement_date":"10","period_rule":"0","term_rule_name":null,"customer_due_date":"0","customer_put_date":"0","customer_payment_collection_date":null,"customer_put_date_manual":"0","customer_put_writeoff_date":"","supplier_due_date":"0","discount_start":"0","discount_rule":"","discount_end":"0","discount_ratio":"","discount_status":"2","discount_currency":"","book_upload_date":"0","trans_cost_put_preserve_date":"0","bl_no_upload_date":"0","supplier_invoice_date":"0","supplier_invoice_taketime":"","real_cost_date":"0","customer_invoice_request_date":"0","first_financing_doc_ok_date":"0","second_financing_doc_ok_date":"0","insurance_doc_ok_date":"0","customer_confirm_date":"0","is_delayed_recovery":"否","delayed_recovery_usd":"","delayed_recovery_cny":"","delayed_time":"","expect_fee_status":"0","real_fee_status":"0","fee_lock_status":"0","pay_account_status":"0","account_status":"0","real_pay_usd":"0.00","real_pay_cny":"0.00","real_put_usd":"0.00","real_put_cny":"0.00","real_put_discount_rate":"0.00","exchange_rate":"0.0000","folde_pay_usd":"0.00","folde_put_usd":"0.00","folde_pay_total":"0.00","folde_put_total":"0.00","gross_margin":"0.00","gross_margin_rate":"0.00","is_special_pay":"0","is_loan_before_invoice":"0","is_fee_miss":"0","fee_miss_name":"","cancel_remark":"","cancel_time":"0","effective_id":"0","effective_by":"","effective_time":"0","create_id":"828","create_by":"GIMBAL","create_time":"1781060453","update_id":"828","update_by":"GIMBAL","update_time":"1781060453","delete_time":"0","business_time":"0","main_ids":"31,1","reverse_status":"0","proprietary_business_status":"0","loan_status":null,"first_status":null,"second_status":null,"loan_pay_status":"","change_type":"0","copy_order_id":"0","real_fee_locked":false,"is_usd_project":"2","pay_status":"1","is_sync_es":"0","expect_discount_status":"0","real_discount_status":"0","entrust_status":2,"audit_type":"","is_system_generate":"0","is_financing":"0","confirm_status":"0","is_traverse":"0","financing_apply_amount":"0.00","financing_apply_amount_cny":"0.00","financing_apply_amount_usd":"0.00","sys_upttime":"2026-06-10 11:00:53","reverse_status_name":"否","is_delayed_recovery_name":"否","order_finance_arr":[],"order_main_bank_arr":[],"order_sub":[],"order_sub_no":"","service_project":{"booking_space":false,"customs_clearance":false,"manifest":false,"insurance":false,"trucking":false},"service_project_amount":{"booking_space":false,"customs_clearance":false,"manifest":false,"insurance":false,"trucking":false},"finance_status":true,"main_ids_name":"易汇智,易航道","policy_main_arr":[{"fee_main_id":"31","main_name":"青岛易汇智供应链管理有限公司"},{"fee_main_id":"1","main_name":"青岛易航道物流科技有限公司"}],"policy_type_name":"结算业务","business_type_name":"海运整箱","cargo_type_name":"普货","period_rule_name":"","trade_term_name":"CIF","carrier_name":"大西洋航运","terms_transport_name":"CY/CY","terms_payment_name":"T/T","pay_type_name":"FREIGHT PREPAID","m_delivery_type_name":"正本","audit":[],"enable":"1","policy_match":"semi","policy_match_name":"手动选择","real_discount_status_name":"—","expect_discount_status_name":"—","expect_policy_status_name":"","policy_status_name":"","subsidy_category_name":"—","expect_subsidy_category_name":"—","real_subsidy_category_name":"—","action":"submit","order_file":[]}
```


8. 业务订单提交

https://fin-tidb.21eflag.com/api/order/order/orderAdd

```json
{"client_expand_name":"孙硕","m_delivery_type":"1","customer_id":"16","customer_name":"兰森玻璃（青岛）有限公司","service_id":"55","service_name":"曲静霞","operator_id":"327","operator_name":"王晓涵","customer_contact_id":"1547","customer_contact_name":"周经理","main_sort":"易汇智,易航道","policy_id":"112","policy_name":"【SPV对客】易汇智","policy_type":"JSZX","service_items":["booking_space"],"business_type":"1","trade_term":"CIF","carrier":"ACL","carrier_id":"1","bl_no":"codfishe2e1","etd":1781020800,"atd":1781020800,"ship_name":"codfishe2e1","voy":"codfishe2e1","pol":"QINGDAO,CHINA","pot":"QINGDAO,CHINA","pod":"QINGDAO,CHINA","del":"QINGDAO,CHINA","country_name":"CHINA","airline_type":"中国","ocean_type":"近洋","terms_payment":"T/T","terms_transport":"CY/CY","pay_type":"FREIGHT PREPAID","customer_order_sn":"codfishe2e1","terms_shipment":"codfishe2e1","shipper":"codfishe2e1","consignee":"codfishe2e1","notifier":"codfishe2e1","ship_mark":"codfishe2e1","commodity":"codfishe2e1","notes":"codfishe2e1","cargo_type":"goods","packer":"","num":"1","gross_weight":"100.000","bulk":"100.000","sea_trans_cost":"100.00","teu":"2","volume":"1*40HQ","volume_desc":"普柜","order_sn":"","status":2,"sea_trans_currency":"USD","container":[{"order_container_id":"322934357176090624","box_type":"40HQ","box_num":"1","box_no":["1"],"seal_number":[""],"sea_trans_unit_price":100}],"message_board":[],"customer_file_list":[],"supplier":[{"order_supplier_id":"322933110742188032","order_id":"322933109106409472","isset_supplier":"1","is_primary":"1","supplier_id":"8","supplier_name":"上海华运船务有限公司青岛分公司","settle_object_id":"39","user_id":"16","user_name":"荣洋","service_item":"booking_space","supplier_period":"30","settlement_date":"20","supplier_pay_date":"0","is_manual":"0","sys_upttime":"2026-06-10 11:00:53","supplier_label":"上海华运船务有限公司青岛分公司-订舱","service_item_name":"订舱","isset_fee":false}],"order_id":"322933109106409472","order_no":"YWDD20260610106678","customer_category":",2,","customer_tax_number":"91370283591262431N","customer_address_cn":"山东省青岛市平度市南村镇东王府庄村","client_expand_id":"250","customer_contact_phone":"18561657088","customer_main_id":"31","customer_main_name":"青岛易汇智供应链管理有限公司","business_main_id":"1","business_main_name":"青岛易航道物流科技有限公司","fund_code":"","fund_name":null,"track_atd":"0","finance_date":"1781020800","pol_cn":"青岛流亭机场","pol_country_id":"1","pol_country":"CHINA","pol_country_cn":"中国","pod_cn":"青岛港","pot_cn":"青岛港","del_cn":"青岛港","country_id":"1","country_name_cn":"中国","customer_period":"60","customer_settlement_date":"10","period_rule":"0","term_rule_name":null,"customer_due_date":"0","customer_put_date":"0","customer_payment_collection_date":null,"customer_put_date_manual":"0","customer_put_writeoff_date":"","supplier_due_date":"0","discount_start":"0","discount_rule":"","discount_end":"0","discount_ratio":"","discount_status":"2","discount_currency":"","book_upload_date":"0","trans_cost_put_preserve_date":"0","bl_no_upload_date":"0","supplier_invoice_date":"0","supplier_invoice_taketime":"","real_cost_date":"0","customer_invoice_request_date":"0","first_financing_doc_ok_date":"0","second_financing_doc_ok_date":"0","insurance_doc_ok_date":"0","customer_confirm_date":"0","is_delayed_recovery":"否","delayed_recovery_usd":"","delayed_recovery_cny":"","delayed_time":"","expect_fee_status":"0","real_fee_status":"0","fee_lock_status":"0","pay_account_status":"0","account_status":"0","real_pay_usd":"0.00","real_pay_cny":"0.00","real_put_usd":"0.00","real_put_cny":"0.00","real_put_discount_rate":"0.00","exchange_rate":"7.7000","folde_pay_usd":"0.00","folde_put_usd":"0.00","folde_pay_total":"0.00","folde_put_total":"0.00","gross_margin":"0.00","gross_margin_rate":"0.00","is_special_pay":"0","is_loan_before_invoice":"0","is_fee_miss":"0","fee_miss_name":"","cancel_remark":"","cancel_time":"0","effective_id":"0","effective_by":"","effective_time":"0","create_id":"828","create_by":"GIMBAL","create_time":"1781060453","update_id":"828","update_by":"GIMBAL","update_time":"1781060750","delete_time":"0","business_time":"0","main_ids":",31,1,","reverse_status":"0","proprietary_business_status":"0","loan_status":null,"first_status":null,"second_status":null,"loan_pay_status":"","change_type":"0","copy_order_id":"0","real_fee_locked":false,"is_usd_project":"2","pay_status":"1","is_sync_es":"0","expect_discount_status":"0","real_discount_status":"0","entrust_status":"2","remark":"","audit_type":"","is_system_generate":"0","is_financing":"0","confirm_status":"0","is_traverse":"0","financing_apply_amount":"0.00","financing_apply_amount_cny":"0.00","financing_apply_amount_usd":"0.00","sys_upttime":"2026-06-10 11:05:50","reverse_status_name":"否","is_delayed_recovery_name":"否","order_finance_arr":[],"order_main_bank_arr":[],"order_sub":[],"order_sub_no":"","service_project":{"booking_space":false,"customs_clearance":false,"manifest":false,"insurance":false,"trucking":false},"service_project_amount":{"booking_space":false,"customs_clearance":false,"manifest":false,"insurance":false,"trucking":false},"finance_status":true,"main_ids_name":"易汇智,易航道","policy_main_arr":[{"fee_main_id":"31","main_name":"青岛易汇智供应链管理有限公司"},{"fee_main_id":"1","main_name":"青岛易航道物流科技有限公司"}],"policy_type_name":"结算业务","business_type_name":"海运整箱","cargo_type_name":"普货","period_rule_name":"","trade_term_name":"CIF","carrier_name":"大西洋航运","terms_transport_name":"CY/CY","terms_payment_name":"T/T","pay_type_name":"FREIGHT PREPAID","m_delivery_type_name":"正本","audit":[],"enable":"1","policy_match":"semi","policy_match_name":"手动选择","real_discount_status_name":"—","expect_discount_status_name":"—","expect_policy_status_name":"","policy_status_name":"","subsidy_category_name":"—","expect_subsidy_category_name":"—","real_subsidy_category_name":"—","action":"check","order_file":[]}
```


9. 用户订单检查

https://fin-tidb.21eflag.com/api/order/OrderEntrust/checkOrderCustomerContainer

```json
{"customer_id":"16","order_id":"322933109106409472","container":[{"order_container_id":"322934357176090624","box_type":"40HQ","box_num":"1","box_no":["1"],"seal_number":[""],"sea_trans_unit_price":100}],"policy_type":"JSZX"}
```


10. 托书确认

https://fin-tidb.21eflag.com/api/order/order/orderBook

```json
{"client_expand_name":"孙硕","m_delivery_type":"1","customer_id":"16","customer_name":"兰森玻璃（青岛）有限公司","service_id":"55","service_name":"曲静霞","operator_id":"327","operator_name":"王晓涵","customer_contact_id":"1547","customer_contact_name":"周经理","main_sort":"易汇智,易航道","policy_id":"112","policy_name":"【SPV对客】易汇智","policy_type":"JSZX","service_items":["booking_space"],"business_type":"1","trade_term":"CIF","carrier":"ACL","carrier_id":"1","bl_no":"codfishe2e1","etd":1781020800,"atd":1781020800,"ship_name":"codfishe2e1","voy":"codfishe2e1","pol":"QINGDAO,CHINA","pot":"QINGDAO,CHINA","pod":"QINGDAO,CHINA","del":"QINGDAO,CHINA","country_name":"CHINA","airline_type":"中国","ocean_type":"近洋","terms_payment":"T/T","terms_transport":"CY/CY","pay_type":"FREIGHT PREPAID","customer_order_sn":"codfishe2e1","terms_shipment":"codfishe2e1","shipper":"codfishe2e1","consignee":"codfishe2e1","notifier":"codfishe2e1","ship_mark":"codfishe2e1","commodity":"codfishe2e1","notes":"codfishe2e1","cargo_type":"goods","packer":"","num":"1","gross_weight":"100.000","bulk":"100.000","sea_trans_cost":"100.00","teu":"2","volume":"1*40HQ","volume_desc":"普柜","order_sn":"","status":2,"sea_trans_currency":"USD","container":[{"order_container_id":"322934357176090624","box_type":"40HQ","box_num":"1","box_no":["1"],"seal_number":[""],"sea_trans_unit_price":100}],"message_board":[],"customer_file_list":[],"supplier":[{"order_supplier_id":"322933110742188032","order_id":"322933109106409472","isset_supplier":"1","is_primary":"1","supplier_id":"8","supplier_name":"上海华运船务有限公司青岛分公司","settle_object_id":"39","user_id":"16","user_name":"荣洋","service_item":"booking_space","supplier_period":"30","settlement_date":"20","supplier_pay_date":"0","is_manual":"0","sys_upttime":"2026-06-10 11:00:53","supplier_label":"上海华运船务有限公司青岛分公司-订舱","service_item_name":"订舱","isset_fee":false}],"order_id":"322933109106409472","order_no":"YWDD20260610106678","customer_category":",2,","customer_tax_number":"91370283591262431N","customer_address_cn":"山东省青岛市平度市南村镇东王府庄村","client_expand_id":"250","customer_contact_phone":"18561657088","customer_main_id":"31","customer_main_name":"青岛易汇智供应链管理有限公司","business_main_id":"1","business_main_name":"青岛易航道物流科技有限公司","fund_code":"","fund_name":null,"track_atd":"0","finance_date":"1781020800","pol_cn":"青岛流亭机场","pol_country_id":"1","pol_country":"CHINA","pol_country_cn":"中国","pod_cn":"青岛港","pot_cn":"青岛港","del_cn":"青岛港","country_id":"1","country_name_cn":"中国","customer_period":"60","customer_settlement_date":"10","period_rule":"0","term_rule_name":null,"customer_due_date":"0","customer_put_date":"0","customer_payment_collection_date":null,"customer_put_date_manual":"0","customer_put_writeoff_date":"","supplier_due_date":"0","discount_start":"0","discount_rule":"","discount_end":"0","discount_ratio":"","discount_status":"2","discount_currency":"","book_upload_date":"0","trans_cost_put_preserve_date":"0","bl_no_upload_date":"0","supplier_invoice_date":"0","supplier_invoice_taketime":"","real_cost_date":"0","customer_invoice_request_date":"0","first_financing_doc_ok_date":"0","second_financing_doc_ok_date":"0","insurance_doc_ok_date":"0","customer_confirm_date":"0","is_delayed_recovery":"否","delayed_recovery_usd":"","delayed_recovery_cny":"","delayed_time":"","expect_fee_status":"0","real_fee_status":"0","fee_lock_status":"0","pay_account_status":"0","account_status":"0","real_pay_usd":"0.00","real_pay_cny":"0.00","real_put_usd":"0.00","real_put_cny":"0.00","real_put_discount_rate":"0.00","exchange_rate":"7.7000","folde_pay_usd":"0.00","folde_put_usd":"0.00","folde_pay_total":"0.00","folde_put_total":"0.00","gross_margin":"0.00","gross_margin_rate":"0.00","is_special_pay":"0","is_loan_before_invoice":"0","is_fee_miss":"0","fee_miss_name":"","cancel_remark":"","cancel_time":"0","effective_id":"0","effective_by":"","effective_time":"0","create_id":"828","create_by":"GIMBAL","create_time":"1781060453","update_id":"828","update_by":"GIMBAL","update_time":"1781060750","delete_time":"0","business_time":"0","main_ids":",31,1,","reverse_status":"0","proprietary_business_status":"0","loan_status":null,"first_status":null,"second_status":null,"loan_pay_status":"","change_type":"0","copy_order_id":"0","real_fee_locked":false,"is_usd_project":"2","pay_status":"1","is_sync_es":"0","expect_discount_status":"0","real_discount_status":"0","entrust_status":"2","remark":"","audit_type":"","is_system_generate":"0","is_financing":"0","confirm_status":"0","is_traverse":"0","financing_apply_amount":"0.00","financing_apply_amount_cny":"0.00","financing_apply_amount_usd":"0.00","sys_upttime":"2026-06-10 11:05:50","reverse_status_name":"否","is_delayed_recovery_name":"否","order_finance_arr":[],"order_main_bank_arr":[],"order_sub":[],"order_sub_no":"","service_project":{"booking_space":false,"customs_clearance":false,"manifest":false,"insurance":false,"trucking":false},"service_project_amount":{"booking_space":false,"customs_clearance":false,"manifest":false,"insurance":false,"trucking":false},"finance_status":true,"main_ids_name":"易汇智,易航道","policy_main_arr":[{"fee_main_id":"31","main_name":"青岛易汇智供应链管理有限公司"},{"fee_main_id":"1","main_name":"青岛易航道物流科技有限公司"}],"policy_type_name":"结算业务","business_type_name":"海运整箱","cargo_type_name":"普货","period_rule_name":"","trade_term_name":"CIF","carrier_name":"大西洋航运","terms_transport_name":"CY/CY","terms_payment_name":"T/T","pay_type_name":"FREIGHT PREPAID","m_delivery_type_name":"正本","audit":[],"enable":"1","policy_match":"semi","policy_match_name":"手动选择","real_discount_status_name":"—","expect_discount_status_name":"—","expect_policy_status_name":"","policy_status_name":"","subsidy_category_name":"—","expect_subsidy_category_name":"—","real_subsidy_category_name":"—","action":"check","order_file":[]}
```


11. 订单查询

https://fin-tidb.21eflag.com/api/order/order/orderDetail

```json
{"order_id":"322933109106409472"}
```

12 . 费用编辑，确认

https://fin-tidb.21eflag.com/api/order/orderFee/bookRealAmountEdit

```json
{"action":"check","order_id":"322933109106409472","discount_ratio":"","service_project":"booking_space","import_status":0,"to_customer":{"put_amount":{"standard_list":[{"order_fee_real_id":null,"fee_type":0,"policy_sub_id":"365","service_project":"booking_space","cost_id":"17","settle_object_id":"37","subsidy_category":"0","currency":"USD","unit_price":"100","unit":"box","specs":"40HQ","num":"1","remark":null,"discount_ratio":100,"discount_amount":"100.00","discount_status":"0","policy_sub_status_name":"正常","pay_sync_status":1,"unique_id":"91c9f422-ae3c-4cfe-968e-085a23828cab","init_main_name":"青岛易汇智供应链管理有限公司","main_name":"青岛易汇智供应链管理有限公司","rowIndex":0}]}},"to_supplier":{"pay_amount":{"standard_list":[{"order_fee_real_id":null,"fee_type":0,"policy_sub_id":"365","service_project":"booking_space","cost_id":"17","settle_object_id":"39","subsidy_category":"0","currency":"USD","unit_price":"100","unit":"box","specs":"40HQ","num":"1","remark":null,"discount_ratio":100,"discount_amount":"100.00","discount_status":"0","policy_sub_status_name":"异常","pay_sync_status":1,"unique_id":"91c9f422-ae3c-4cfe-968e-085a23828cab","init_main_name":"—","main_name":"青岛易汇智供应链管理有限公司","rowIndex":0}]}}}
```


13. 费用编辑，提交

https://fin-tidb.21eflag.com/api/order/orderFee/bookRealAmountEdit

```json
{"action":"submit","order_id":"322933109106409472","discount_ratio":"","service_project":"booking_space","import_status":0,"to_customer":{"put_amount":{"standard_list":[{"order_fee_real_id":null,"fee_type":0,"policy_sub_id":"365","service_project":"booking_space","cost_id":"17","settle_object_id":"37","subsidy_category":"0","currency":"USD","unit_price":"100","unit":"box","specs":"40HQ","num":"1","remark":null,"discount_ratio":100,"discount_amount":"100.00","discount_status":"0","policy_sub_status_name":"正常","pay_sync_status":1,"unique_id":"91c9f422-ae3c-4cfe-968e-085a23828cab","init_main_name":"青岛易汇智供应链管理有限公司","main_name":"青岛易汇智供应链管理有限公司","rowIndex":0}]}},"to_supplier":{"pay_amount":{"standard_list":[{"order_fee_real_id":null,"fee_type":0,"policy_sub_id":"365","service_project":"booking_space","cost_id":"17","settle_object_id":"39","subsidy_category":"0","currency":"USD","unit_price":"100","unit":"box","specs":"40HQ","num":"1","remark":null,"discount_ratio":100,"discount_amount":"100.00","discount_status":"0","policy_sub_status_name":"异常","pay_sync_status":1,"unique_id":"91c9f422-ae3c-4cfe-968e-085a23828cab","init_main_name":"—","main_name":"青岛易汇智供应链管理有限公司","rowIndex":0}]}}}
```


14. 检查费用 （不用处理接口）

https://fin-tidb.21eflag.com/api/order/orderFee/toggleRealAmount

```json
{"order_id":"322933109106409472"}
```


15. 检查生成子订单

https://fin-tidb.21eflag.com/api/order/order/checkGenerateOrderSub

```json
{"order_id":"322933109106409472"}
```


16. 生成子订单

https://fin-tidb.21eflag.com/api/order/order/generateOrderSub

```json
{"order_id":"322933109106409472"}
```


17. 费用锁定

https://fin-tidb.21eflag.com/api/order/orderFee/realAmountLockSubmit

```json
{"action":"check","order_id":"322933109106409472","order_fee_real_ids":["322978255550283776"]}
```


18. 费用审批

https://fin-tidb.21eflag.com/api/order/orderFee/realAmountLockSubmit

```json
{"action":"audit","order_id":"322933109106409472","order_fee_real_ids":["322978255550283776"]}
```


19. 费用提交

https://fin-tidb.21eflag.com/api/order/orderFee/realAmountLockSubmit

```json
{"action":"submit","order_id":"322933109106409472","order_fee_real_ids":["322978255550283776"],"audit_msg":{"title":"业务订单ID","code":"ZDD20260610015012","msgs":["费用锁定申请"]},"select_node_user":[{"node_sort":"0","user_id":"828"}]}
```


20. 查询发起的审批号

https://fin-tidb.21eflag.com/api/home/audit/auditRecord

```json
{"relation_id":"322933109106409472","type":"order"}
```


21. 查询审批

https://fin-tidb.21eflag.com/api/home/audit/auditDetail

```json
{"audit_id":"322983853553614848"}
```


22. 审批批准

https://fin-tidb.21eflag.com/api/home/audit/auditExecute

```json
{"audit_ids":["322983853553614848"],"audit_status":2,"audit_remark":null}
```


23. 对账确认

https://fin-tidb.21eflag.com/api/order/order/orderConfirmAccount

```json
{"order_id":"322933109106409472","action":"check"}
```


24. 对账结果提交

<https://fin-tidb.21eflag.com/api/order/order/orderConfirmAccount>

finance_ids : 通过customer_finance_id和flag 字段进行拼接

bank_ids : 通过main_bank_id和flag字段拼接

```json
{"action":"submit","order_id":"322933109106409472","finance_ids":["2896_CustomerFinance","2895_CustomerFinance"],"bank_ids":["78_MainBank","77_MainBank"]}
```


25. 未放款开票申请

https://fin-tidb.21eflag.com/api/order/order/changeInvoiceApply

```json
{"audit_note":"","order_ids":["322933109106409472"],"action":"check","audit_msg":{"title":"业务订单ID","code":"","msgs":["未放款开票申请"]}}
```


26. 未放款开票审批

https://fin-tidb.21eflag.com/api/order/order/changeInvoiceApply

```json
{"audit_note":"","order_ids":["322933109106409472"],"action":"audit","audit_msg":{"title":"业务订单ID","code":"","msgs":["未放款开票申请"]}}
```


27. 未放款开票提交

https://fin-tidb.21eflag.com/api/order/order/changeInvoiceApply

```json
{"audit_note":"","order_ids":["322933109106409472"],"action":"submit","audit_msg":{"title":"业务订单ID","code":"","msgs":["未放款开票申请"]},"select_node_user":[{"node_sort":"0","user_id":"828"}]}
```


28. 查询审批

https://fin-tidb.21eflag.com/api/home/audit/auditRecord

```json
{"relation_id":"322933109106409472","type":"order"}
```


29. 批准审批

https://fin-tidb.21eflag.com/api/home/audit/auditExecute

```json
{"audit_ids":["322992855406608384"],"audit_status":2,"audit_remark":null}
```


30. 对账查询

https://fin-tidb.21eflag.com/api/finance/accountFee/financePutList

```json
{"page_no":1,"page_size":50,"bl_nos":[],"bl_no":"codfishe2e1","operate_type":1,"search_style":"account","account_simple_name":null,"account_type":"1","customer_id":["16"],"put_settle_object_id":"665","main_id":"1","pay_settle_object_id":null}
```


31. 对账提交检查

https://fin-tidb.21eflag.com/api/finance/receiveAccount/orderReceiveAccountEdit

```json
{"account_simple_name":null,"account_type":"1","customer_id":["16"],"put_settle_object_id":"665","main_id":"1","pay_settle_object_id":null,"selection_time":1781073932,"action":"check","operate_type":1,"receive_account_id":null,"main_name":"青岛易航道物流科技有限公司","put_settle_object":"青岛易汇智供应链管理有限公司","pay_settle_object":null,"select_list":[{"order_id":"322933109106409472","order_no":"YWDD20260610106678","bl_no":"codfishe2e1","customer_id":"16","customer_name":"兰森玻璃（青岛）有限公司","customer_main_id":"31","customer_main_name":"青岛易汇智供应链管理有限公司","business_main_id":"1","business_main_name":"青岛易航道物流科技有限公司","policy_type":"JSZX","trade_term":"CIF","customer_period":"60","customer_put_date":"1786291200","atd":"1781020800","etd":"1781020800","create_time":"1781060453","finance_date":"1781020800","fund_name":"青岛海发商业保理有限公司","ship_name":"codfishe2e1","voy":"codfishe2e1","status":"2","is_special_pay":"0","pay_status":"0","is_loan_before_invoice":"1","customer_order_sn":"codfishe2e1","order_sub_id":"322978240647921664","order_sub_no":"ZDD20260610015029","main_id":"1","main_name":"青岛易航道物流科技有限公司","service_project":"booking_space","currency":"USD","amount_total":"100.00","pay_settle_object_type":"2","put_settle_object_id":"665","put_settle_object":"青岛易汇智供应链管理有限公司","pay_settle_object":"上海华运船务有限公司青岛分公司","book_supplier_period":"30","book_supplier_pay_date":"1784476800","book_supplier_name":"上海华运船务有限公司青岛分公司","operable_amount":"100.00","un_operable_amount":"0.00","operable_flag":"all","policy_type_name":"结算业务","order_sub_currency":"USD322978240647921664","order_main_finance":"青岛银行股份有限公司江西路支行+USD+802051200001568","order_error_messages":[],"order_error_message":"","order_error_flag":false,"amount_list":[{"order_id":"322933109106409472","order_no":"YWDD20260610106678","customer_name":"兰森玻璃（青岛）有限公司","bl_no":"codfishe2e1","main_name":"青岛易航道物流科技有限公司","order_sub_no":"ZDD20260610015029","order_sub_id":"322978240647921664","order_fee_real_id":"322978255550285824","fee_real_no":"FY202606101285504","fee_type":"0","service_project":"booking_space","fee_real_name":"海运费","currency":"USD","symbol":"1","real_amount":"100.00","supplier_id":null,"cost_no":"0001","fee_status":"1","account_no":"","pay_account_no":"","account_status":"0","pay_account_status":"0","invoice_status":"0","receive_invoice_batch_no":null,"pay_invoice_batch_no":null,"receive_invoice_apply_no":null,"pay_invoice_apply_no":null,"put_settle_object_id":"665","put_settle_object":"青岛易汇智供应链管理有限公司","pay_settle_object_id":"39","pay_settle_object":"上海华运船务有限公司青岛分公司","writeoff_status":"1","un_writeoff_amount":"100.00","use_writeoff_amount":"0.00","writeoff_nos":"","pay_form_no":"","pay_demand_no":"","amount_error_messages":[],"amount_error_message":"","amount_error_flag":false}]}]}
```


32. 对账提交

https://fin-tidb.21eflag.com/api/finance/receiveAccount/orderReceiveAccountEdit

```json
{"account_simple_name":null,"account_type":"1","customer_id":["16"],"put_settle_object_id":"665","main_id":"1","pay_settle_object_id":null,"selection_time":1781073932,"action":"submit","operate_type":1,"receive_account_id":null,"main_name":"青岛易航道物流科技有限公司","put_settle_object":"青岛易汇智供应链管理有限公司","pay_settle_object":null,"select_list":[{"order_id":"322933109106409472","order_no":"YWDD20260610106678","bl_no":"codfishe2e1","customer_id":"16","customer_name":"兰森玻璃（青岛）有限公司","customer_main_id":"31","customer_main_name":"青岛易汇智供应链管理有限公司","business_main_id":"1","business_main_name":"青岛易航道物流科技有限公司","policy_type":"JSZX","trade_term":"CIF","customer_period":"60","customer_put_date":"1786291200","atd":"1781020800","etd":"1781020800","create_time":"1781060453","finance_date":"1781020800","fund_name":"青岛海发商业保理有限公司","ship_name":"codfishe2e1","voy":"codfishe2e1","status":"2","is_special_pay":"0","pay_status":"0","is_loan_before_invoice":"1","customer_order_sn":"codfishe2e1","order_sub_id":"322978240647921664","order_sub_no":"ZDD20260610015029","main_id":"1","main_name":"青岛易航道物流科技有限公司","service_project":"booking_space","currency":"USD","amount_total":"100.00","pay_settle_object_type":"2","put_settle_object_id":"665","put_settle_object":"青岛易汇智供应链管理有限公司","pay_settle_object":"上海华运船务有限公司青岛分公司","book_supplier_period":"30","book_supplier_pay_date":"1784476800","book_supplier_name":"上海华运船务有限公司青岛分公司","operable_amount":"100.00","un_operable_amount":"0.00","operable_flag":"all","policy_type_name":"结算业务","order_sub_currency":"USD322978240647921664","order_main_finance":"青岛银行股份有限公司江西路支行+USD+802051200001568","order_error_messages":[],"order_error_message":"","order_error_flag":false,"amount_list":[{"order_id":"322933109106409472","order_no":"YWDD20260610106678","customer_name":"兰森玻璃（青岛）有限公司","bl_no":"codfishe2e1","main_name":"青岛易航道物流科技有限公司","order_sub_no":"ZDD20260610015029","order_sub_id":"322978240647921664","order_fee_real_id":"322978255550285824","fee_real_no":"FY202606101285504","fee_type":"0","service_project":"booking_space","fee_real_name":"海运费","currency":"USD","symbol":"1","real_amount":"100.00","supplier_id":null,"cost_no":"0001","fee_status":"1","account_no":"","pay_account_no":"","account_status":"0","pay_account_status":"0","invoice_status":"0","receive_invoice_batch_no":null,"pay_invoice_batch_no":null,"receive_invoice_apply_no":null,"pay_invoice_apply_no":null,"put_settle_object_id":"665","put_settle_object":"青岛易汇智供应链管理有限公司","pay_settle_object_id":"39","pay_settle_object":"上海华运船务有限公司青岛分公司","writeoff_status":"1","un_writeoff_amount":"100.00","use_writeoff_amount":"0.00","writeoff_nos":"","pay_form_no":"","pay_demand_no":"","amount_error_messages":[],"amount_error_message":"","amount_error_flag":false}]}]}
```


33. 对账查询

https://fin-tidb.21eflag.com/api/finance/receiveAccount/receiveAccountDetail

```json
{"receive_account_id":"322996617806348288"}
```


34. 对账查询2

https://fin-tidb.21eflag.com/api/finance/receiveAccount/receiveConfirmList

```json
{"confirm_type":0,"receive_account_id":"322996617806348288","order_ids":[]}
```


35. 对账确认

<https://fin-tidb.21eflag.com/api/finance/receiveAccount/accountConfirm>

```json
{"confirm_type":0,"receive_account_id":"322996617806348288","confirm_list":[{"main_id":"31","main_name":"青岛易汇智供应链管理有限公司","symbol":"0","settle_object_id":"1","order_ids":"322933109106409472","order_sub_ids":"322974684981231616","order_sub_types":"0","unique_ids":"91c9f422-ae3c-4cfe-968e-085a23828cab","receive_account_no":"","account_simple_name":"codfishe2e1","symbol_name":"应付","settle_object":"青岛易航道物流科技有限公司","account_batch_name":"青岛易汇智供应链管理有限公司+青岛易航道物流科技有限公司+26.06+USD100","order_sub_type":1,"only_adjust_status":0,"real_amount_ids":["322978255550284800"],"currency_list":["USD"],"_XID":"row_3720"}]}
```


36. 开票批次管理

<https://fin-tidb.21eflag.com/api/finance/accountFee/financePutList>

```json
{"page_no":1,"page_size":50,"customer_id":"16","put_settle_object_id":"665","put_settle_object":"青岛易汇智供应链管理有限公司","main_id":"1","bl_no":"codfishe2e1","operate_type":1,"batch_type":1,"search_style":"invoice","pay_settle_object_id":[],"account_type":"1","bl_nos":[]}
```


37. 开票批次检查1

<https://fin-tidb.21eflag.com/api/Finance/ReceiveInvoiceBatch/checkStep1>

```json
{"cny_file":[],"usd_file":[],"debitno_file":[],"style":"1","apply_type":"1","customer_id":"16","customer_name":["兰森玻璃（青岛）有限公司"],"put_settle_object_id":"665","main_id":"1","pay_settle_object_id":[],"turn_rate":"","merge_with_cny":"2","selectRadio":"","receive_invoice_batch_id":"","batch_apply_name":"","invoice_form":"","invoice_type":"","invoice_items":"","invoice_rate_type":"","rate_type":"","usd_is_turn":"","order_fee_real_id":["322978255550285824"],"usd_requireinvoice_form":"","usd_requireinvoice_type":"","usd_requiretruck_remark":"","usd_requireinvoice_items_count":"","usd_requireinvoice_items":"","usd_requireinvoice_rate":"","usd_requireinvoice_rate_type":"","usd_requireseller_name":"","cny_requireinvoice_form":"","cny_requireinvoice_type":"","cny_requiretruck_remark":"","cny_requireinvoice_items_count":"","cny_requireinvoice_items":"","cny_requireinvoice_rate":"","cny_requireinvoice_rate_type":"","cny_requireseller_name":"","usd_require":{"fast_remark":[],"currency":"","amount_total_usd":"","amount_total_cny":"","rate":"","turn_amount_total_cny":"","turn_amount_total_usd":"","turn_amount_total":"","invoice_apply_name":"","invoice_apply_simple":"","invoice_form":"","invoice_type":"","purchaser_id":"","purchaser_head_cn":"","purchaser_tax_number":"","seller_id":"","seller_name":"","bank_account":"","seller_info":"","invoice_items":"","invoice_rate_type":"","invoice_rate":"","require_other":"","remark":"","rate_list":[]},"cny_require":{"fast_remark":[],"currency":"","amount_total_usd":"","amount_total_cny":"","rate":"","turn_amount_total_cny":"","turn_amount_total_usd":"","turn_amount_total":"","invoice_apply_name":"","invoice_apply_simple":"","invoice_form":"","invoice_type":"","purchaser_id":"","purchaser_head_cn":"","purchaser_tax_number":"","seller_id":"","seller_name":"","bank_account":"","seller_info":"","invoice_items":"","invoice_rate_type":"","invoice_rate":"","require_other":"","remark":"","rate_list":[]},"usd_file_id":[],"cny_file_id":[],"debitno_file_id":[],"batch_order_remark":[],"batch_type":"1","cost_usd":"100.00","cost_cny":"0.00","put_settle_object":"青岛易汇智供应链管理有限公司","main_name_cn":"青岛易航道物流科技有限公司","order_sub_id":["322978240647921664"]}
```


38. 开票批次检查2

<https://fin-tidb.21eflag.com/api/Finance/ReceiveInvoiceBatch/checkStep2>

```json
{"cny_file":[],"usd_file":[],"debitno_file":[],"style":"1","apply_type":"1","customer_id":"16","customer_name":["兰森玻璃（青岛）有限公司"],"put_settle_object_id":"665","main_id":"1","pay_settle_object_id":[],"turn_rate":"7.7","merge_with_cny":"2","selectRadio":"","receive_invoice_batch_id":"","batch_apply_name":"","invoice_form":"","invoice_type":"","invoice_items":"","invoice_rate_type":"","rate_type":"1","usd_is_turn":"1","order_fee_real_id":["322978255550285824"],"usd_requireinvoice_form":"","usd_requireinvoice_type":"","usd_requiretruck_remark":"","usd_requireinvoice_items_count":"","usd_requireinvoice_items":"","usd_requireinvoice_rate":"","usd_requireinvoice_rate_type":"","usd_requireseller_name":"","cny_requireinvoice_form":"","cny_requireinvoice_type":"","cny_requiretruck_remark":"","cny_requireinvoice_items_count":"","cny_requireinvoice_items":"","cny_requireinvoice_rate":"","cny_requireinvoice_rate_type":"","cny_requireseller_name":"","usd_require":{"fast_remark":[],"currency":"CNY","amount_total_usd":100,"amount_total_cny":"","rate":7.7,"turn_amount_total_cny":"770.00","turn_amount_total_usd":"","turn_amount_total":"770.00","invoice_apply_name":"青岛易航道物流科技有限公司 + 青岛易汇智供应链管理有限公司 + 2026-06 + USD 100.00","invoice_apply_simple":"","invoice_form":"2","invoice_type":"1","purchaser_id":"665","purchaser_head_cn":"青岛易汇智供应链管理有限公司","purchaser_tax_number":"91370202MAEWF5RN7G","seller_id":"10","seller_name":"224746757829","bank_account":"","seller_info":{"main_bank_id":"10","main_id":"1","chinese_header":"青岛易航道物流科技有限公司","english_header":"","identifier_no":"91370202MABU30PK3F","currency":"CNY","is_public":"0","fund_code":"","bank_account":"224746757829","swift_code":"","register_address_cn":"山东省青岛市市南区香港西路48号海天中心2座2101","register_address_en":"","open_bank_no":"","open_bank_cn":"中国银行青岛市北支行","open_bank_en":"","bank_address_en":"","remark":"","create_id":"294","create_by":"于佳倩TIDB","create_time":"1776062439","pay_default":"0","put_default":"0","sys_upttime":"2026-05-15 10:48:52","fund_name":"","is_public_name":"否","value":"10"},"invoice_items":"","invoice_rate_type":"","invoice_rate":"","require_other":"","remark":"","rate_list":[{"cost_name":"海运费","fee_real_no":"FY202606101285504","cost_no":"0001","invoice_rate":"6","real_amount":"100.00","currency":"USD","invoice_item":"2","amount_error_flag":false,"rowIndex":0,"invoice_item_name":"国际货物运输代理海运费"}],"purchaser_name":"青岛易汇智供应链管理有限公司","fund_name":"青岛海发商业保理有限公司"},"cny_require":{"fast_remark":[],"currency":"","amount_total_usd":"","amount_total_cny":"","rate":"","turn_amount_total_cny":"","turn_amount_total_usd":"","turn_amount_total":"","invoice_apply_name":"","invoice_apply_simple":"","invoice_form":"","invoice_type":"","purchaser_id":"","purchaser_head_cn":"","purchaser_tax_number":"","seller_id":"","seller_name":"","bank_account":"","seller_info":"","invoice_items":"","invoice_rate_type":"","invoice_rate":"","require_other":"","remark":"","rate_list":[]},"usd_file_id":[],"cny_file_id":[],"debitno_file_id":[],"batch_order_remark":[],"batch_type":"1","cost_usd":"100.00","cost_cny":"0.00","put_settle_object":"青岛易汇智供应链管理有限公司","main_name_cn":"青岛易航道物流科技有限公司","order_sub_id":["322978240647921664"],"sys_rate":"","appoint_rate":""}
```


39. 开票提交检查

https://fin-tidb.21eflag.com/api/Finance/ReceiveInvoiceBatch/batchOrderEdit

```json
{"cny_file":[],"usd_file":[],"debitno_file":[],"style":"1","apply_type":"1","customer_id":"16","customer_name":["兰森玻璃（青岛）有限公司"],"put_settle_object_id":"665","main_id":"1","pay_settle_object_id":[],"turn_rate":"7.7","merge_with_cny":"2","selectRadio":"","receive_invoice_batch_id":"","batch_apply_name":"","invoice_form":"","invoice_type":"","invoice_items":"","invoice_rate_type":"","rate_type":"1","usd_is_turn":"1","order_fee_real_id":["322978255550285824"],"usd_requireinvoice_form":"","usd_requireinvoice_type":"","usd_requiretruck_remark":"","usd_requireinvoice_items_count":"","usd_requireinvoice_items":"","usd_requireinvoice_rate":"","usd_requireinvoice_rate_type":"","usd_requireseller_name":"","cny_requireinvoice_form":"","cny_requireinvoice_type":"","cny_requiretruck_remark":"","cny_requireinvoice_items_count":"","cny_requireinvoice_items":"","cny_requireinvoice_rate":"","cny_requireinvoice_rate_type":"","cny_requireseller_name":"","usd_require":{"fast_remark":"[]","currency":"CNY","amount_total_usd":100,"amount_total_cny":"","rate":7.7,"turn_amount_total_cny":"770.00","turn_amount_total_usd":"","turn_amount_total":"770.00","invoice_apply_name":"青岛易航道物流科技有限公司 + 青岛易汇智供应链管理有限公司 + 2026-06 + USD 100.00","invoice_apply_simple":"","invoice_form":"2","invoice_type":"1","purchaser_id":"665","purchaser_head_cn":"青岛易汇智供应链管理有限公司","purchaser_tax_number":"91370202MAEWF5RN7G","seller_id":"10","seller_name":"224746757829","bank_account":"","seller_info":"{\"main_bank_id\":\"10\",\"main_id\":\"1\",\"chinese_header\":\"青岛易航道物流科技有限公司\",\"english_header\":\"\",\"identifier_no\":\"91370202MABU30PK3F\",\"currency\":\"CNY\",\"is_public\":\"0\",\"fund_code\":\"\",\"bank_account\":\"224746757829\",\"swift_code\":\"\",\"register_address_cn\":\"山东省青岛市市南区香港西路48号海天中心2座2101\",\"register_address_en\":\"\",\"open_bank_no\":\"\",\"open_bank_cn\":\"中国银行青岛市北支行\",\"open_bank_en\":\"\",\"bank_address_en\":\"\",\"remark\":\"\",\"create_id\":\"294\",\"create_by\":\"于佳倩TIDB\",\"create_time\":\"1776062439\",\"pay_default\":\"0\",\"put_default\":\"0\",\"sys_upttime\":\"2026-05-15 10:48:52\",\"fund_name\":\"\",\"is_public_name\":\"否\",\"value\":\"10\"}","invoice_items":"","invoice_rate_type":"","invoice_rate":"","require_other":"","remark":"青岛海发商业保理有限公司","rate_list":[{"cost_name":"海运费","fee_real_no":"FY202606101285504","cost_no":"0001","invoice_rate":"6","real_amount":"100.00","currency":"USD","invoice_item":"2","amount_error_flag":false,"rowIndex":0,"invoice_item_name":"国际货物运输代理海运费"}],"purchaser_name":"青岛易汇智供应链管理有限公司","fund_name":"青岛海发商业保理有限公司"},"cny_require":{"fast_remark":"[]","currency":"","amount_total_usd":"","amount_total_cny":"","rate":"","turn_amount_total_cny":"","turn_amount_total_usd":"","turn_amount_total":"","invoice_apply_name":"","invoice_apply_simple":"","invoice_form":"","invoice_type":"","purchaser_id":"","purchaser_head_cn":"","purchaser_tax_number":"","seller_id":"","seller_name":"","bank_account":"","seller_info":"","invoice_items":"","invoice_rate_type":"","invoice_rate":"","require_other":"","remark":"—","rate_list":[]},"usd_file_id":[],"cny_file_id":[],"debitno_file_id":[],"batch_order_remark":[{"order_sub_id":"322978240647921664","currency":"USD"}],"batch_type":"1","cost_usd":"100.00","cost_cny":"0.00","put_settle_object":"青岛易汇智供应链管理有限公司","main_name_cn":"青岛易航道物流科技有限公司","order_sub_id":["322978240647921664"],"sys_rate":"","appoint_rate":"","action":"check","fee_currency":"USD","order_sub_customer_id":["16"]}
```


40. 开票提交审批

https://fin-tidb.21eflag.com/api/Finance/ReceiveInvoiceBatch/batchOrderEdit

```json
{"cny_file":[],"usd_file":[],"debitno_file":[],"style":"1","apply_type":"1","customer_id":"16","customer_name":["兰森玻璃（青岛）有限公司"],"put_settle_object_id":"665","main_id":"1","pay_settle_object_id":[],"turn_rate":"7.7","merge_with_cny":"2","selectRadio":"","receive_invoice_batch_id":"","batch_apply_name":"","invoice_form":"","invoice_type":"","invoice_items":"","invoice_rate_type":"","rate_type":"1","usd_is_turn":"1","order_fee_real_id":["322978255550285824"],"usd_requireinvoice_form":"","usd_requireinvoice_type":"","usd_requiretruck_remark":"","usd_requireinvoice_items_count":"","usd_requireinvoice_items":"","usd_requireinvoice_rate":"","usd_requireinvoice_rate_type":"","usd_requireseller_name":"","cny_requireinvoice_form":"","cny_requireinvoice_type":"","cny_requiretruck_remark":"","cny_requireinvoice_items_count":"","cny_requireinvoice_items":"","cny_requireinvoice_rate":"","cny_requireinvoice_rate_type":"","cny_requireseller_name":"","usd_require":{"fast_remark":"[]","currency":"CNY","amount_total_usd":100,"amount_total_cny":"","rate":7.7,"turn_amount_total_cny":"770.00","turn_amount_total_usd":"","turn_amount_total":"770.00","invoice_apply_name":"青岛易航道物流科技有限公司 + 青岛易汇智供应链管理有限公司 + 2026-06 + USD 100.00","invoice_apply_simple":"","invoice_form":"2","invoice_type":"1","purchaser_id":"665","purchaser_head_cn":"青岛易汇智供应链管理有限公司","purchaser_tax_number":"91370202MAEWF5RN7G","seller_id":"10","seller_name":"224746757829","bank_account":"","seller_info":"{\"main_bank_id\":\"10\",\"main_id\":\"1\",\"chinese_header\":\"青岛易航道物流科技有限公司\",\"english_header\":\"\",\"identifier_no\":\"91370202MABU30PK3F\",\"currency\":\"CNY\",\"is_public\":\"0\",\"fund_code\":\"\",\"bank_account\":\"224746757829\",\"swift_code\":\"\",\"register_address_cn\":\"山东省青岛市市南区香港西路48号海天中心2座2101\",\"register_address_en\":\"\",\"open_bank_no\":\"\",\"open_bank_cn\":\"中国银行青岛市北支行\",\"open_bank_en\":\"\",\"bank_address_en\":\"\",\"remark\":\"\",\"create_id\":\"294\",\"create_by\":\"于佳倩TIDB\",\"create_time\":\"1776062439\",\"pay_default\":\"0\",\"put_default\":\"0\",\"sys_upttime\":\"2026-05-15 10:48:52\",\"fund_name\":\"\",\"is_public_name\":\"否\",\"value\":\"10\"}","invoice_items":"","invoice_rate_type":"","invoice_rate":"","require_other":"","remark":"青岛海发商业保理有限公司","rate_list":[{"cost_name":"海运费","fee_real_no":"FY202606101285504","cost_no":"0001","invoice_rate":"6","real_amount":"100.00","currency":"USD","invoice_item":"2","amount_error_flag":false,"rowIndex":0,"invoice_item_name":"国际货物运输代理海运费"}],"purchaser_name":"青岛易汇智供应链管理有限公司","fund_name":"青岛海发商业保理有限公司"},"cny_require":{"fast_remark":"[]","currency":"","amount_total_usd":"","amount_total_cny":"","rate":"","turn_amount_total_cny":"","turn_amount_total_usd":"","turn_amount_total":"","invoice_apply_name":"","invoice_apply_simple":"","invoice_form":"","invoice_type":"","purchaser_id":"","purchaser_head_cn":"","purchaser_tax_number":"","seller_id":"","seller_name":"","bank_account":"","seller_info":"","invoice_items":"","invoice_rate_type":"","invoice_rate":"","require_other":"","remark":"—","rate_list":[]},"usd_file_id":[],"cny_file_id":[],"debitno_file_id":[],"batch_order_remark":[{"order_sub_id":"322978240647921664","currency":"USD"}],"batch_type":"1","cost_usd":"100.00","cost_cny":"0.00","put_settle_object":"青岛易汇智供应链管理有限公司","main_name_cn":"青岛易航道物流科技有限公司","order_sub_id":["322978240647921664"],"sys_rate":"","appoint_rate":"","action":"audit","fee_currency":"USD","order_sub_customer_id":["16"]}
```


41. 开票提交

https://fin-tidb.21eflag.com/api/Finance/ReceiveInvoiceBatch/batchOrderEdit

```json
{"cny_file":[],"usd_file":[],"debitno_file":[],"style":"1","apply_type":"1","customer_id":"16","customer_name":["兰森玻璃（青岛）有限公司"],"put_settle_object_id":"665","main_id":"1","pay_settle_object_id":[],"turn_rate":"7.7","merge_with_cny":"2","selectRadio":"","receive_invoice_batch_id":"","batch_apply_name":"","invoice_form":"","invoice_type":"","invoice_items":"","invoice_rate_type":"","rate_type":"1","usd_is_turn":"1","order_fee_real_id":["322978255550285824"],"usd_requireinvoice_form":"","usd_requireinvoice_type":"","usd_requiretruck_remark":"","usd_requireinvoice_items_count":"","usd_requireinvoice_items":"","usd_requireinvoice_rate":"","usd_requireinvoice_rate_type":"","usd_requireseller_name":"","cny_requireinvoice_form":"","cny_requireinvoice_type":"","cny_requiretruck_remark":"","cny_requireinvoice_items_count":"","cny_requireinvoice_items":"","cny_requireinvoice_rate":"","cny_requireinvoice_rate_type":"","cny_requireseller_name":"","usd_require":{"fast_remark":"[]","currency":"CNY","amount_total_usd":100,"amount_total_cny":"","rate":7.7,"turn_amount_total_cny":"770.00","turn_amount_total_usd":"","turn_amount_total":"770.00","invoice_apply_name":"青岛易航道物流科技有限公司 + 青岛易汇智供应链管理有限公司 + 2026-06 + USD 100.00","invoice_apply_simple":"","invoice_form":"2","invoice_type":"1","purchaser_id":"665","purchaser_head_cn":"青岛易汇智供应链管理有限公司","purchaser_tax_number":"91370202MAEWF5RN7G","seller_id":"10","seller_name":"224746757829","bank_account":"","seller_info":"{\"main_bank_id\":\"10\",\"main_id\":\"1\",\"chinese_header\":\"青岛易航道物流科技有限公司\",\"english_header\":\"\",\"identifier_no\":\"91370202MABU30PK3F\",\"currency\":\"CNY\",\"is_public\":\"0\",\"fund_code\":\"\",\"bank_account\":\"224746757829\",\"swift_code\":\"\",\"register_address_cn\":\"山东省青岛市市南区香港西路48号海天中心2座2101\",\"register_address_en\":\"\",\"open_bank_no\":\"\",\"open_bank_cn\":\"中国银行青岛市北支行\",\"open_bank_en\":\"\",\"bank_address_en\":\"\",\"remark\":\"\",\"create_id\":\"294\",\"create_by\":\"于佳倩TIDB\",\"create_time\":\"1776062439\",\"pay_default\":\"0\",\"put_default\":\"0\",\"sys_upttime\":\"2026-05-15 10:48:52\",\"fund_name\":\"\",\"is_public_name\":\"否\",\"value\":\"10\"}","invoice_items":"","invoice_rate_type":"","invoice_rate":"","require_other":"","remark":"青岛海发商业保理有限公司","rate_list":[{"cost_name":"海运费","fee_real_no":"FY202606101285504","cost_no":"0001","invoice_rate":"6","real_amount":"100.00","currency":"USD","invoice_item":"2","amount_error_flag":false,"rowIndex":0,"invoice_item_name":"国际货物运输代理海运费"}],"purchaser_name":"青岛易汇智供应链管理有限公司","fund_name":"青岛海发商业保理有限公司"},"cny_require":{"fast_remark":"[]","currency":"","amount_total_usd":"","amount_total_cny":"","rate":"","turn_amount_total_cny":"","turn_amount_total_usd":"","turn_amount_total":"","invoice_apply_name":"","invoice_apply_simple":"","invoice_form":"","invoice_type":"","purchaser_id":"","purchaser_head_cn":"","purchaser_tax_number":"","seller_id":"","seller_name":"","bank_account":"","seller_info":"","invoice_items":"","invoice_rate_type":"","invoice_rate":"","require_other":"","remark":"—","rate_list":[]},"usd_file_id":[],"cny_file_id":[],"debitno_file_id":[],"batch_order_remark":[{"order_sub_id":"322978240647921664","currency":"USD"}],"batch_type":"1","cost_usd":"100.00","cost_cny":"0.00","put_settle_object":"青岛易汇智供应链管理有限公司","main_name_cn":"青岛易航道物流科技有限公司","order_sub_id":["322978240647921664"],"sys_rate":"","appoint_rate":"","action":"submit","fee_currency":"USD","order_sub_customer_id":["16"],"audit_msg":{"title":"开票批次ID","code":null,"msgs":["应收开票批次申请"]},"select_node_user":[]}
```


42. 查询开票

https://fin-tidb.21eflag.com/api/Finance/ReceiveInvoiceBatch/applyPage

```json
{"page_no":1,"page_size":20,"order_no":"","create_time":[1765296000000,1781107199000],"cancel_status":[],"bl_nos":["codfishe2e1"],"sort_field":"create_time","sort_order":"desc","params":{},"create_time_start":"1765296000","create_time_end":"1781107199"}
```


43. 查询开票详情

https://fin-tidb.21eflag.com/api/Finance/ReceiveInvoiceBatch/batchDetail

```json
{receive_invoice_batch_id: "323006563193192448"}
```


44. 查询开票(开票申请，可以先不做接口) 

https://fin-tidb.21eflag.com/api/Finance/ReceiveInvoiceBatch/batchpage

```json
{"page_no":1,"page_size":20,"order_no":"","create_time":[1765296000000,1781107199000],"bl_nos":["codfishe2e1"],"sort_field":"create_time","sort_order":"desc","params":{},"create_time_start":"1765296000","create_time_end":"1781107199"}
```


45. 查询开票详情具体信息

https://fin-tidb.21eflag.com/api/Finance/ReceiveInvoiceBatch/applyDetail

```json
{"receive_invoice_apply_id":"323008151559340032"}
```


46. 开票信息 （暂时无用）

https://fin-tidb.21eflag.com/api/Finance/ReceiveInvoiceBatch/getAmountStatistics

```json
{"receive_invoice_apply_id":"323008151559340032","invoice_form":"2"}
```


47. 上传发票确认

https://fin-tidb.21eflag.com/api/finance/receiveInvoice/invoiceAddCheck

```json
{"invoice_number":"25922000000029755889","invoice_type":"1","invoice_amount":"50000","invoice_tax_amount":"0.00","invoice_date":1771603200,"currency":"CNY","usd_amount":"","invoice_exchange_rate":"1","invoice_original":{"file_id":"323021107122667520","file_name":"6a2925594f5ea.pdf","file_type":"pdf","original_name":"电子发票（普通发票）5.pdf","file_url":"http://192.168.20.102:8001/file/o/MTA2NDc="},"buyer_chinese_header":"青岛易汇智供应链管理有限公司","buyer_identifier_no":"91370202MAEWF5RN7G","buyer_identity":"main","isbuyer_identity":"main","seller_chinese_header":"青岛易航道物流科技有限公司","seller_identifier_no":"91370202MABU30PK3F","seller_identity":"main","invoice_image_name":"6a29255d33aca.png","file_path":"http://192.168.20.102:8001/file/o/MTA2NDc=","main_name":"青岛易航道物流科技有限公司","invoice_apply_type":"1","put_settle_object":"青岛易汇智供应链管理有限公司"}
```


48. 发票添加

https://fin-tidb.21eflag.com/api/finance/receiveInvoice/invoiceAdd

```json
[{"invoice_number":"25922000000029755889","invoice_type":"1","invoice_type_name":"增值税数电普通发票","invoice_amount":"50000.00","invoice_tax_amount":"0.00","invoice_date":1771603200,"currency":"CNY","usd_amount":"","invoice_exchange_rate":"1.0000","invoice_original":{"file_id":"323021107122667520","file_name":"6a2925594f5ea.pdf","file_type":"pdf","original_name":"电子发票（普通发票）5.pdf","file_url":"http://192.168.20.102:8001/file/o/MTA2NDc="},"buyer_chinese_header":"青岛易汇智供应链管理有限公司","buyer_identifier_no":"91370202MAEWF5RN7G","buyer_identity":"main","isbuyer_identity":"main","seller_chinese_header":"青岛易航道物流科技有限公司","seller_identifier_no":"91370202MABU30PK3F","seller_identity":"main","invoice_image_name":"6a29255d33aca.png","file_path":"http://192.168.20.102:8001/file/o/MTA2NDc="}]
```


49. 提交检查

https://fin-tidb.21eflag.com/api/Finance/ReceiveInvoiceBatch/allocationInvoiceFee

```json
{"receive_invoice_apply_id":"323008151559340032","invoice_arr":[{"receive_invoice_id":"323021953671626752","invoice_amount_use":"770.00"}],"action":"check"}
```


50. 提交确认

https://fin-tidb.21eflag.com/api/Finance/ReceiveInvoiceBatch/allocationInvoiceFee

```json
{"receive_invoice_apply_id":"323008151559340032","invoice_arr":[{"receive_invoice_id":"323021953671626752","invoice_amount_use":"770.00"}],"action":"submit"}
```


51. 核销，查询提单明细

需要维护主体的信息

<https://fin-tidb.21eflag.com/api/order/orderFee/putOrderItem>

```json
{"order_no":"","create_time":[1765296000000,1781107199000],"main_id":["31"],"settle_object_id":["37"],"bl_nos":["codfishe2e1"],"sort_field":"order_create_time","sort_order":"desc","params":{},"create_time_start":"1765296000","create_time_end":"1781107199"}
```


52. 费用检查

https://fin-tidb.21eflag.com/api/finance/receiveWriteoff/feeWriteoffCheck

```json
{"order_fee_real_ids":["322978255550285824"]}
```


53. 核销处理

https://fin-tidb.21eflag.com/api/finance/receiveWriteoff/orderFeePage

```json
{"order_fee_real_ids":["322978255550285824"]}
```


54. 提交核销检查

https://fin-tidb.21eflag.com/api/finance/receiveWriteoff/writeoffBatch

```json
{"action":"check","writeoff_object":[{"order_fee_real_id":"322978255550285824","un_writeoff_amount":"100.00","use_writeoff_amount":"0.00"}],"writeoff_name":"","fee_match_type":"1","writeoff_type":"1","writeoff_mode":"order","currency":"","un_writeoff_amount_usd_total":"0.00","un_writeoff_amount_cny_total":"0.00","use_writeoff_amount_usd_total":"100.00","use_writeoff_amount_cny_total":"0.00","statement_amount_cny_total":"770.00","statement_amount_usd_total":"0.00","statement":[{"is_exchange":"","statement_currency":"CNY","statement_amount":"770","writeoff_amount_cny":"0.00","writeoff_amount_usd":"100.00","exchange_rate":7.7,"ischangeRate":true,"main_bank_id":"10","receipt_time":1781020800,"receipt_voucher":"","use_statement_amount_cny_total":null,"use_statement_amount_usd_total":null}],"main_id":"1","main_name":"青岛易航道物流科技有限公司","select_node_user":[]}
```


55. 提交核销

https://fin-tidb.21eflag.com/api/finance/receiveWriteoff/writeoffBatch

```json
{"action":"submit","writeoff_object":[{"order_fee_real_id":"322978255550285824","un_writeoff_amount":"100.00","use_writeoff_amount":"0.00"}],"writeoff_name":"","fee_match_type":"1","writeoff_type":"1","writeoff_mode":"order","currency":"","un_writeoff_amount_usd_total":"0.00","un_writeoff_amount_cny_total":"0.00","use_writeoff_amount_usd_total":"100.00","use_writeoff_amount_cny_total":"0.00","statement_amount_cny_total":"770.00","statement_amount_usd_total":"0.00","statement":[{"is_exchange":"","statement_currency":"CNY","statement_amount":"770","writeoff_amount_cny":"0.00","writeoff_amount_usd":"100.00","exchange_rate":7.7,"ischangeRate":true,"main_bank_id":"10","receipt_time":1781020800,"receipt_voucher":"","use_statement_amount_cny_total":null,"use_statement_amount_usd_total":null}],"main_id":"1","main_name":"青岛易航道物流科技有限公司","select_node_user":[]}
```


56. 查询核销记录

https://fin-tidb.21eflag.com/api/finance/receiveWriteoff/writeoffPage

```json
{"page_no":1,"page_size":20,"create_time":[1765296000000,1781107199000],"main_id":[],"receive_settle_object_id":[],"bl_nos":["codfishe2e1"],"sort_field":"create_time","sort_order":"desc","params":{},"create_time_start":"1765296000","create_time_end":"1781107199"}
```


\
51 返回信息

```json
{
    "code": 200,
    "msg": "成功",
    "data": {
        "total": 1,
        "data": [
            {
                "_class": "org.fin.es.entity.EsFeeReal",
                "order_fee_real_id": "322978255550285824",
                "order_id": "322933109106409472",
                "order_sub_id": "322978240647921664",
                "unique_id": "91c9f422-ae3c-4cfe-968e-085a23828cab",
                "order_fee_expect_no": "",
                "finance_fee": "0",
                "cost_id": "17",
                "cost_no": "0001",
                "cost_name": "海运费",
                "cost_label": "0",
                "service_project": "booking_space",
                "customer_period": "60",
                "take_date": "1786291200",
                "supplier_period": "30",
                "supplier_id": "8",
                "pay_date": "1784476800",
                "fee_type": "0",
                "fee_real_no": "FY202606101285504",
                "settle_object_id": "37",
                "settle_object": "兰森玻璃（青岛）有限公司",
                "put_settle_object": "青岛易汇智供应链管理有限公司",
                "put_settle_object_id": "665",
                "pay_settle_object": "上海华运船务有限公司青岛分公司",
                "pay_settle_object_id": "39",
                "real_settle_object_id": "39",
                "real_settle_object": "上海华运船务有限公司青岛分公司",
                "fee_real_name": "海运费",
                "version": "",
                "symbol": "1",
                "currency": "USD",
                "unit": "box",
                "unit_price": 100,
                "amount": 100,
                "discount_amount": 100,
                "real_total": 100,
                "folde_total": 770,
                "discount_ratio": "100",
                "discount_status": "2",
                "exchange_rate": 7.7,
                "specs": "40HQ",
                "num": "1",
                "pay_account_id": "0",
                "pay_account_no": "",
                "pay_account_status": "0",
                "pay_account_time": "0",
                "account_id": "322996617806348288",
                "account_no": "YSDZPC20260610002377",
                "account_status": "2",
                "account_time": "1781075594",
                "receive_invoice_batch_id": "323006563193192448",
                "receive_invoice_batch_no": "YSKPPC20260610001395",
                "receive_invoice_apply_id": "323008151559340032",
                "receive_invoice_apply_no": "YSKPSQ20260610001750",
                "tax_rate": "6",
                "invoice_status": "1",
                "invoice_ids": "323021953671626752",
                "invoice_nos": "YSFP20260610001844",
                "invoice_numbers": "25922000000029755889",
                "invoice_amount": 100,
                "invoice_exchange_rate": "1.0000",
                "invoice_time": "1781081696",
                "writeoff_ids": "",
                "writeoff_nos": "",
                "writeoff_status": "1",
                "writeoff_time": "",
                "writeoff_force_audit_status": "0",
                "un_writeoff_amount": "100.00",
                "use_writeoff_amount": "0.00",
                "writeoff_exchange_rate": "",
                "writeoff_banks": "",
                "pay_demand_id": "0",
                "pay_form_id": "",
                "fee_status": "1",
                "examine_status": "2",
                "lock_time": "1781073551",
                "lock_exchange_rate": 7.7,
                "create_id": "828",
                "fee_create_time": "1781060453",
                "update_id": "828",
                "update_by": "GIMBAL",
                "update_time": "1781075135",
                "delete_time": "0",
                "cancel_time": "0",
                "conduct_ratio": "100",
                "pay_invoice_batch_id": "0",
                "pay_invoice_apply_id": "0",
                "is_round": "1",
                "invoice_date": "1771603200",
                "customer_fee": "0",
                "supplier_fee": "0",
                "policy_id": "112",
                "policy_name": "【SPV对客】易汇智",
                "policy_sub_id": "365",
                "policy_sub_name": "100%穿行",
                "policy_sub_status": "1",
                "subsidy_category": "0",
                "pay_demand_no": "",
                "pay_form_no": "",
                "fee_same_id": "322978255550284800",
                "opposite_fee_no": "FY202606101285503",
                "is_penetrate": "1",
                "fee_main_id": "1",
                "order_no": "YWDD20260610106678",
                "bl_no": "codfishe2e1",
                "main_id": "1",
                "main_name": "青岛易航道物流科技有限公司",
                "customer_id": "16",
                "customer_name": "兰森玻璃（青岛）有限公司",
                "customer_category": ",2,",
                "customer_main_id": "31",
                "customer_main_name": "青岛易汇智供应链管理有限公司",
                "fund_code": "F0036",
                "fund_name": "青岛海发商业保理有限公司",
                "pay_status": "0",
                "business_main_id": "1",
                "business_main_name": "青岛易航道物流科技有限公司",
                "booking_space_supplier_id": "8",
                "booking_space_supplier_name": "上海华运船务有限公司青岛分公司",
                "policy_type": "JSZX",
                "main_ids": ",31,1,",
                "main_sort": "易汇智,易航道",
                "status": "2",
                "business_type": "1",
                "trade_term": "CIF",
                "carrier_id": "1",
                "carrier": "ACL",
                "etd": "1781020800",
                "atd": "1781020800",
                "track_atd": "0",
                "finance_date": "1781020800",
                "ship_name": "codfishe2e1",
                "voy": "codfishe2e1",
                "pol": "QINGDAO,CHINA",
                "pol_cn": "青岛流亭机场",
                "pol_country_id": "1",
                "pol_country": "CHINA",
                "pol_country_cn": "中国",
                "pod": "QINGDAO,CHINA",
                "pod_cn": "青岛港",
                "pot": "QINGDAO,CHINA",
                "pot_cn": "青岛港",
                "del": "QINGDAO,CHINA",
                "del_cn": "青岛港",
                "country_id": "1",
                "country_name": "CHINA",
                "country_name_cn": "中国",
                "ocean_type": "近洋",
                "airline_type": "中国",
                "volume": "1*40HQ",
                "volume_desc": "普柜",
                "teu": "2",
                "discount_rule": "",
                "discount_currency": "",
                "book_upload_date": "0",
                "trans_cost_put_preserve_date": "1781071216",
                "bl_no_upload_date": "0",
                "supplier_invoice_date": "0",
                "supplier_invoice_taketime": "0",
                "real_cost_date": "1781072551",
                "customer_invoice_request_date": "0",
                "sale_id": "0",
                "sale_name": "",
                "service_id": "55",
                "service_name": "曲静霞",
                "operator_id": "327",
                "operator_name": "王晓涵",
                "period_rule": "1",
                "is_special_pay": "0",
                "term_rule_name": "标准规则",
                "cancel_remark": "",
                "order_create_time": "1781060453",
                "order_create_id": "828",
                "create_by": "GIMBAL",
                "order_sub_no": "ZDD20260610015029",
                "business_no": "YHD20260610033811",
                "audit_type": "",
                "fee_lock_status": "2",
                "client_expand_name": "孙硕",
                "client_expand_id": "250",
                "is_loan_before_invoice": "1",
                "pay_status_name": "",
                "customer_put_date": "1786291200",
                "business_type_name": "海运整箱",
                "policy_type_name": "结算业务",
                "trade_term_name": "CIF",
                "negative_fee": 0,
                "book_supplier_name": "上海华运船务有限公司青岛分公司",
                "order_fee_real_ids": [
                    "322978255550285824"
                ],
                "writeoff_object": [
                    {
                        "order_fee_real_id": "322978255550285824",
                        "un_writeoff_amount": "100.00",
                        "use_writeoff_amount": "0.00"
                    }
                ],
                "invoice_currency": [
                    "CNY"
                ]
            }
        ]
    },
    "request_id": "a488860fab9e15b4a122f2c7d35602df"
}
```

46 返回信息

```json
{
    "code": 200,
    "msg": "成功",
    "data": [
        {
            "bl_no": "codfishe2e1",
            "invoice_item": "2",
            "invoice_item_name": "国际货物运输代理海运费",
            "invoice_rate": "6",
            "turn_cost_cny": "770.00"
        }
    ],
    "request_id": "e4c5acca82d9d6e0fcb8b236edca7fed"
}
```

45 返回信息

```json
{
    "code": 200,
    "msg": "成功",
    "data": {
        "base_info": {
            "batch_apply_name": "青岛易航道物流科技有限公司 + 青岛易汇智供应链管理有限公司 + 2026-06 + USD 100.00",
            "batch_apply_simple": null,
            "style": "1",
            "apply_type": "1",
            "customer_name": "兰森玻璃（青岛）有限公司",
            "customer_main_name": "青岛易汇智供应链管理有限公司",
            "put_settle_object_id": "665",
            "put_settle_object": "青岛易汇智供应链管理有限公司",
            "main_id": "1",
            "main_name": null,
            "main_name_cn": "青岛易航道物流科技有限公司",
            "pay_settle_object": "上海华运船务有限公司青岛分公司",
            "business_main_name": "青岛易航道物流科技有限公司",
            "book_supplier_name": "上海华运船务有限公司青岛分公司",
            "batch_status": "1",
            "audit_status": "2",
            "usd_is_turn": "1",
            "merge_with_cny": "2",
            "rate_type": "1",
            "turn_rate": "7.7000",
            "sys_rate": null,
            "appoint_rate": null,
            "batch_type": "1",
            "debit_note_id_no": null,
            "batch_status_name": "生效",
            "audit_status_name": "审批通过",
            "usd_is_turn_name": "是",
            "merge_with_cny_name": "否",
            "style_name": "正式发票",
            "apply_type_name": "同一下单客户",
            "invoice_status_name": "未开票",
            "receive_invoice_apply_id": "323008151559340032",
            "receive_invoice_apply_no": "YSKPSQ20260610001750",
            "receive_invoice_batch_id": "323006563193192448",
            "receive_invoice_batch_no": "YSKPPC20260610001395",
            "batch_same_status": "0",
            "pay_invoice_apply_id": null,
            "pay_invoice_apply_no": null,
            "invoice_apply_name": "青岛易航道物流科技有限公司 + 青岛易汇智供应链管理有限公司 + 2026-06 + USD 100.00",
            "invoice_apply_simple": null,
            "book_supplier_id": null,
            "cost_usd": "100.00",
            "cost_cny": null,
            "fee_currency": "USD",
            "currency": "CNY",
            "rate": "7.7000",
            "turn_cost_cny": "770.00",
            "turn_cost_usd": null,
            "invoice_apply_amount": "770.00",
            "invoice_status": "2",
            "cancel_status": "1",
            "invoice_used_amount": "0.00",
            "invoice_unused_amount": "770.00",
            "receive_invoice_id": null,
            "invoice_no": null,
            "registration_type": null,
            "registration_time": null,
            "writeoff_status": "1",
            "un_writeoff_amount_cny": "0.00",
            "use_writeoff_amount_cny": "0.00",
            "un_writeoff_amount_usd": "100.00",
            "use_writeoff_amount_usd": "0.00",
            "writeoff_id": null,
            "writeoff_no": null,
            "create_id": "828",
            "create_by": "GIMBAL",
            "create_time": "1781078344",
            "update_id": "828",
            "update_by": "GIMBAL",
            "update_time": "1781078344",
            "bl_nos": "codfishe2e1",
            "invoice_date": null,
            "cancel_remark": null,
            "sys_upttime": "2026-06-10 15:59:05",
            "registration_type_name": null,
            "writeoff_status_name": "未核销",
            "batch_same_status_name": "否",
            "turn_cost_cny_z": 0,
            "turn_cost_cny_f": 0,
            "turn_cost_usd_z": 0,
            "turn_cost_usd_f": 0,
            "cancel_status_name": "已生效",
            "customer_id": "16",
            "pay_settle_object_id": "39",
            "order_fee_real_id_list": [
                "322978255550285824"
            ]
        },
        "require": {
            "receive_invoice_batch_require_id": "323006564380180480",
            "require_currency": "USD",
            "receive_invoice_batch_id": "323006563193192448",
            "receive_invoice_apply_id": "323008151559340032",
            "currency": "CNY",
            "amount_total_usd": "100.00",
            "amount_total_cny": null,
            "rate": "7.7000",
            "turn_amount_total_cny": "770.00",
            "turn_amount_total_usd": null,
            "turn_amount_total": "770.00",
            "invoice_apply_name": "青岛易航道物流科技有限公司 + 青岛易汇智供应链管理有限公司 + 2026-06 + USD 100.00",
            "invoice_apply_simple": null,
            "invoice_form": "2",
            "invoice_type": "1",
            "invoice_items": [],
            "invoice_rate_type": null,
            "invoice_rate": null,
            "require_other": null,
            "remark": "青岛海发商业保理有限公司",
            "purchaser_id": "665",
            "purchaser_name": "青岛易汇智供应链管理有限公司",
            "purchaser_head_cn": "青岛易汇智供应链管理有限公司",
            "purchaser_tax_number": "91370202MAEWF5RN7G",
            "seller_id": "10",
            "seller_name": "224746757829",
            "seller_info": "{\"main_bank_id\":\"10\",\"main_id\":\"1\",\"chinese_header\":\"青岛易航道物流科技有限公司\",\"english_header\":\"\",\"identifier_no\":\"91370202MABU30PK3F\",\"currency\":\"CNY\",\"is_public\":\"0\",\"fund_code\":\"\",\"bank_account\":\"224746757829\",\"swift_code\":\"\",\"register_address_cn\":\"山东省青岛市市南区香港西路48号海天中心2座2101\",\"register_address_en\":\"\",\"open_bank_no\":\"\",\"open_bank_cn\":\"中国银行青岛市北支行\",\"open_bank_en\":\"\",\"bank_address_en\":\"\",\"remark\":\"\",\"create_id\":\"294\",\"create_by\":\"于佳倩TIDB\",\"create_time\":\"1776062439\",\"pay_default\":\"0\",\"put_default\":\"0\",\"sys_upttime\":\"2026-05-15 10:48:52\",\"fund_name\":\"\",\"is_public_name\":\"否\",\"value\":\"10\"}",
            "fast_remark": "[]",
            "truck_remark": null,
            "invoice_items_count": "1",
            "sys_upttime": "2026-06-10 15:59:04",
            "invoice_items_name": "",
            "rate_list": [
                {
                    "receive_invoice_batch_fee_rate_id": "323006564480843776",
                    "receive_invoice_batch_id": "323006563193192448",
                    "receive_invoice_batch_require_id": "323006564380180480",
                    "invoice_item": "2",
                    "cost_no": "0001",
                    "cost_name": "海运费",
                    "invoice_rate": "6",
                    "invoice_items": null,
                    "turn_cost_cny": null,
                    "currency": "USD",
                    "sys_upttime": "2026-06-10 15:52:46",
                    "invoice_item_name": "国际货物运输代理海运费"
                }
            ],
            "file_list": [],
            "trade_terms": "CIF"
        },
        "batch_order_split": [
            {
                "receive_invoice_apply_order_id": "323008154109476864",
                "currency": "USD",
                "amount_total": "100.00",
                "amount_total_cny": "0.00",
                "amount_total_usd": "100.00",
                "exchange_rate": "7.7000",
                "turn_amount_total_cny": "770.00",
                "turn_amount_total_usd": null,
                "usd_invoice_remark": "",
                "order_sub_currency": "USD322978240647921664",
                "invoice_total": "770.00",
                "receive_invoice_batch_id": "323006563193192448",
                "receive_invoice_apply_id": "323008151559340032",
                "receive_invoice_apply_no": "YSKPSQ20260610001750",
                "order_id": "322933109106409472",
                "order_no": "YWDD20260610106678",
                "order_sub_id": "322978240647921664",
                "order_sub_no": "ZDD20260610015029",
                "bl_no": "codfishe2e1",
                "delete_id": null,
                "delete_time": null,
                "customer_id": "16",
                "customer_name": "兰森玻璃（青岛）有限公司",
                "customer_main_id": "31",
                "customer_main_name": "青岛易汇智供应链管理有限公司",
                "put_settle_object_id": "665",
                "put_settle_object": "青岛易汇智供应链管理有限公司",
                "main_id": "1",
                "main_name": "青岛易航道物流科技有限公司",
                "pay_settle_object_id": "39",
                "pay_settle_object": "上海华运船务有限公司青岛分公司",
                "business_main_id": "1",
                "business_main_name": "青岛易航道物流科技有限公司",
                "book_supplier_id": "8",
                "book_supplier_name": "上海华运船务有限公司青岛分公司",
                "policy_type": "JSZX",
                "trade_term": "CIF",
                "customer_period": "60",
                "customer_put_date": "1786291200",
                "atd": "1781020800",
                "create_time": "1781060453",
                "finance_date": "1781020800",
                "our_company_settle_no": null,
                "remark_cny": null,
                "remark_usd": null,
                "ship_name": "codfishe2e1",
                "voy": "codfishe2e1",
                "etd": "1781020800",
                "book_supplier_period": "30",
                "book_supplier_pay_date": "1784476800",
                "order_main_finance_usd": "青岛银行股份有限公司江西路支行+USD+802051200001568",
                "order_main_finance_cny": null,
                "sys_upttime": "2026-06-10 15:52:45",
                "policy_type_name": "结算业务",
                "customer_order_sn": "codfishe2e1",
                "remark": null,
                "order_main_finance": "青岛银行股份有限公司江西路支行+USD+802051200001568"
            }
        ],
        "batch_order": [
            {
                "receive_invoice_apply_order_id": "323008154109476864",
                "currency": "USD",
                "amount_total": "100.00",
                "amount_total_cny": "0.00",
                "amount_total_usd": "100.00",
                "exchange_rate": "7.7000",
                "turn_amount_total_cny": "770.00",
                "turn_amount_total_usd": null,
                "usd_invoice_remark": "",
                "order_sub_currency": "USD322978240647921664",
                "invoice_total": "770.00",
                "receive_invoice_batch_id": "323006563193192448",
                "receive_invoice_apply_id": "323008151559340032",
                "receive_invoice_apply_no": "YSKPSQ20260610001750",
                "order_id": "322933109106409472",
                "order_no": "YWDD20260610106678",
                "order_sub_id": "322978240647921664",
                "order_sub_no": "ZDD20260610015029",
                "bl_no": "codfishe2e1",
                "delete_id": null,
                "delete_time": null,
                "customer_id": "16",
                "customer_name": "兰森玻璃（青岛）有限公司",
                "customer_main_id": "31",
                "customer_main_name": "青岛易汇智供应链管理有限公司",
                "put_settle_object_id": "665",
                "put_settle_object": "青岛易汇智供应链管理有限公司",
                "main_id": "1",
                "main_name": "青岛易航道物流科技有限公司",
                "pay_settle_object_id": "39",
                "pay_settle_object": "上海华运船务有限公司青岛分公司",
                "business_main_id": "1",
                "business_main_name": "青岛易航道物流科技有限公司",
                "book_supplier_id": "8",
                "book_supplier_name": "上海华运船务有限公司青岛分公司",
                "policy_type": "JSZX",
                "trade_term": "CIF",
                "customer_period": "60",
                "customer_put_date": "1786291200",
                "atd": "1781020800",
                "create_time": "1781060453",
                "finance_date": "1781020800",
                "our_company_settle_no": null,
                "remark_cny": null,
                "remark_usd": null,
                "ship_name": "codfishe2e1",
                "voy": "codfishe2e1",
                "etd": "1781020800",
                "book_supplier_period": "30",
                "book_supplier_pay_date": "1784476800",
                "order_main_finance_usd": "青岛银行股份有限公司江西路支行+USD+802051200001568",
                "order_main_finance_cny": null,
                "sys_upttime": "2026-06-10 15:52:45",
                "policy_type_name": "结算业务",
                "customer_order_sn": "codfishe2e1",
                "remark": ""
            }
        ],
        "invoice": [],
        "fee_invoice_list": [],
        "batch_order_merge": [
            {
                "receive_invoice_apply_order_id": "323008154109476864",
                "currency": "CNY",
                "amount_total": "770.00",
                "amount_total_cny": "0.00",
                "amount_total_usd": "100.00",
                "exchange_rate": "7.7000",
                "turn_amount_total_cny": "770.00",
                "turn_amount_total_usd": null,
                "usd_invoice_remark": "",
                "order_sub_currency": "USD322978240647921664",
                "invoice_total": "770.00",
                "receive_invoice_batch_id": "323006563193192448",
                "receive_invoice_apply_id": "323008151559340032",
                "receive_invoice_apply_no": "YSKPSQ20260610001750",
                "order_id": "322933109106409472",
                "order_no": "YWDD20260610106678",
                "order_sub_id": "322978240647921664",
                "order_sub_no": "ZDD20260610015029",
                "bl_no": "codfishe2e1",
                "delete_id": null,
                "delete_time": null,
                "customer_id": "16",
                "customer_name": "兰森玻璃（青岛）有限公司",
                "customer_main_id": "31",
                "customer_main_name": "青岛易汇智供应链管理有限公司",
                "put_settle_object_id": "665",
                "put_settle_object": "青岛易汇智供应链管理有限公司",
                "main_id": "1",
                "main_name": "青岛易航道物流科技有限公司",
                "pay_settle_object_id": "39",
                "pay_settle_object": "上海华运船务有限公司青岛分公司",
                "business_main_id": "1",
                "business_main_name": "青岛易航道物流科技有限公司",
                "book_supplier_id": "8",
                "book_supplier_name": "上海华运船务有限公司青岛分公司",
                "policy_type": "JSZX",
                "trade_term": "CIF",
                "customer_period": "60",
                "customer_put_date": "1786291200",
                "atd": "1781020800",
                "create_time": "1781060453",
                "finance_date": "1781020800",
                "our_company_settle_no": null,
                "remark_cny": null,
                "remark_usd": null,
                "ship_name": "codfishe2e1",
                "voy": "codfishe2e1",
                "etd": "1781020800",
                "book_supplier_period": "30",
                "book_supplier_pay_date": "1784476800",
                "order_main_finance_usd": "青岛银行股份有限公司江西路支行+USD+802051200001568",
                "order_main_finance_cny": null,
                "sys_upttime": "2026-06-10 15:52:45",
                "policy_type_name": "结算业务",
                "customer_order_sn": "codfishe2e1",
                "remark": "",
                "receive_invoice_id": null,
                "invoice_no": null,
                "invoice_number": null,
                "invoice_type": null,
                "invoice_type_name": null,
                "invoice_amount": null,
                "invoice_tax_amount": null,
                "invoice_date": null,
                "usd_amount": null,
                "invoice_exchange_rate": null,
                "invoice_original": null,
                "use_amount": null,
                "un_amount": null,
                "used_cny": "0.00",
                "used_usd": "100.00"
            }
        ],
        "invoice_item_str": "6%；国际货物运输代理海运费"
    },
    "request_id": "f1246d02a67f638ff569fc58c529e2ce"
}
```


44 返回信息

```json
{
    "code": 200,
    "msg": "成功",
    "data": {
        "total": 1,
        "total_data": {
            "cost_usd": "100.00",
            "cost_cny": "0.00"
        },
        "data": [
            {
                "receive_invoice_batch_id": "323006563193192448",
                "receive_invoice_batch_no": "YSKPPC20260610001395",
                "receive_invoice_apply_no": "YSKPSQ20260610001750",
                "batch_apply_name": "青岛易航道物流科技有限公司 + 青岛易汇智供应链管理有限公司 + 2026-06 + USD 100.00",
                "batch_apply_simple": null,
                "style": "1",
                "apply_type": "1",
                "customer_name": "兰森玻璃（青岛）有限公司",
                "customer_main_name": "青岛易汇智供应链管理有限公司",
                "put_settle_object": "青岛易汇智供应链管理有限公司",
                "main_name": null,
                "main_name_cn": "青岛易航道物流科技有限公司",
                "pay_settle_object": "上海华运船务有限公司青岛分公司",
                "business_main_name": "青岛易航道物流科技有限公司",
                "book_supplier_name": "上海华运船务有限公司青岛分公司",
                "cost_usd": "100.00",
                "cost_cny": "0.00",
                "currency": "CNY",
                "usd_is_turn": "1",
                "merge_with_cny": "2",
                "turn_rate": "7.7000",
                "sys_rate": null,
                "appoint_rate": null,
                "create_id": "828",
                "create_by": "GIMBAL",
                "create_time": "1781077965",
                "batch_status": "1",
                "audit_status": "2",
                "audit_id": "487",
                "audit_by": "刘常春TiDB",
                "bl_no": "codfishe2e1",
                "batch_same_status": "0",
                "pay_invoice_batch_id": null,
                "pay_invoice_batch_no": null,
                "batch_status_name": "生效",
                "audit_status_name": "审批通过",
                "usd_is_turn_name": "是",
                "merge_with_cny_name": "否",
                "style_name": "正式发票",
                "apply_type_name": "同一下单客户",
                "batch_same_status_name": "否"
            }
        ]
    },
    "request_id": "d783c48c23bdb36f9e6cd1a666899f99"
}
```

43返回信息

```json
{
    "code": 200,
    "msg": "成功",
    "data": {
        "receive_invoice_batch_id": "323006563193192448",
        "receive_invoice_batch_no": "YSKPPC20260610001395",
        "receive_invoice_apply_id": ",323008151559340032,",
        "receive_invoice_apply_no": "YSKPSQ20260610001750",
        "batch_same_status": "0",
        "pay_invoice_batch_id": null,
        "pay_invoice_batch_no": null,
        "debit_note_id_no": null,
        "batch_apply_name": "青岛易航道物流科技有限公司 + 青岛易汇智供应链管理有限公司 + 2026-06 + USD 100.00",
        "batch_apply_simple": null,
        "style": "1",
        "apply_type": "1",
        "invoice_form": null,
        "invoice_type": null,
        "invoice_items": null,
        "invoice_rate_type": null,
        "invoice_rate": null,
        "customer_name": "兰森玻璃（青岛）有限公司",
        "customer_id": "16",
        "put_settle_object_id": "665",
        "put_settle_object": "青岛易汇智供应链管理有限公司",
        "pay_settle_object_id": [
            "39"
        ],
        "pay_settle_object": [
            "上海华运船务有限公司青岛分公司"
        ],
        "batch_type": "1",
        "main_id": "1",
        "main_name": null,
        "main_name_cn": "青岛易航道物流科技有限公司",
        "customer_main_id": null,
        "customer_main_name": "青岛易汇智供应链管理有限公司",
        "business_main_id": null,
        "business_main_name": "青岛易航道物流科技有限公司",
        "book_supplier_id": null,
        "book_supplier_name": "上海华运船务有限公司青岛分公司",
        "cost_usd": "100.00",
        "cost_cny": "0.00",
        "turn_cost_usd": null,
        "turn_cost_cny": null,
        "currency": "CNY",
        "usd_is_turn": "1",
        "rate_type": "1",
        "merge_with_cny": "2",
        "turn_rate": "7.7000",
        "sys_rate": null,
        "appoint_rate": null,
        "create_id": "828",
        "create_by": "GIMBAL",
        "create_time": "1781077965",
        "update_id": null,
        "update_by": null,
        "update_time": null,
        "batch_status": "1",
        "audit_status": "2",
        "cancel_status": null,
        "audit_id": "487",
        "audit_by": "刘常春TiDB",
        "bl_no": "codfishe2e1",
        "sys_upttime": "2026-06-10 15:59:05",
        "fee_list": [
            {
                "receive_invoice_batch_fee_id": "323006563394519040",
                "receive_invoice_batch_id": "323006563193192448",
                "receive_invoice_apply_id": "323008151559340032",
                "receive_invoice_apply_no": "YSKPSQ20260610001750",
                "order_fee_real_id": "322978255550285824",
                "fee_same_id": "322978255550284800",
                "cost_no": "0001",
                "fee_real_no": "FY202606101285504",
                "fee_type": "0",
                "fee_type_name": "标准费用",
                "service_project": "booking_space",
                "service_project_name": "订舱",
                "fee_real_name": "海运费",
                "currency": "USD",
                "real_total": "100.00",
                "order_id": "322933109106409472",
                "order_no": "YWDD20260610106678",
                "order_sub_id": "322978240647921664",
                "order_sub_no": "ZDD20260610015029",
                "bl_no": "codfishe2e1",
                "delete_id": null,
                "delete_time": null,
                "customer_id": "16",
                "customer_name": "兰森玻璃（青岛）有限公司",
                "customer_main_id": "31",
                "customer_main_name": "青岛易汇智供应链管理有限公司",
                "put_settle_object_id": "665",
                "put_settle_object": "青岛易汇智供应链管理有限公司",
                "main_id": "1",
                "main_name": "青岛易航道物流科技有限公司",
                "pay_settle_object_id": "39",
                "pay_settle_object": "上海华运船务有限公司青岛分公司",
                "business_main_id": "1",
                "business_main_name": "青岛易航道物流科技有限公司",
                "book_supplier_id": "8",
                "book_supplier_name": "上海华运船务有限公司青岛分公司",
                "policy_type": "JSZX",
                "trade_term": "CIF",
                "customer_period": "60",
                "customer_put_date": "1786291200",
                "atd": "1781020800",
                "create_time": "1781060453",
                "finance_date": "1781020800",
                "our_company_settle_no": null,
                "pay_date": "1784476800",
                "supplier_period": "30",
                "ship_name": "codfishe2e1",
                "voy": "codfishe2e1",
                "etd": "1781020800",
                "policy_type_name": "结算业务",
                "order_main_finance_id": null,
                "f_main_name": null,
                "bank_account_cny": null,
                "open_bank_cny": null,
                "bank_account_usd": "802051200001568",
                "open_bank_usd": "青岛银行股份有限公司江西路支行",
                "book_supplier_period": "30",
                "book_supplier_pay_date": "1784476800",
                "order_main_finance": "青岛银行股份有限公司江西路支行+USD+802051200001568",
                "sys_upttime": "2026-06-10 15:59:05",
                "real_amount": "100.00",
                "customer_order_sn": "codfishe2e1"
            }
        ],
        "order_fee_real_id": [
            "322978255550285824"
        ],
        "order_list": [
            {
                "receive_invoice_batch_order_id": "323006563499376640",
                "currency": "USD",
                "amount_total": "100.00",
                "amount_total_cny": null,
                "amount_total_usd": "100.00",
                "exchange_rate": "7.7000",
                "turn_amount_total_cny": "770.00",
                "turn_amount_total_usd": null,
                "usd_invoice_remark": null,
                "order_sub_currency": "USD322978240647921664",
                "receive_invoice_batch_id": "323006563193192448",
                "receive_invoice_apply_id": null,
                "receive_invoice_apply_no": null,
                "order_id": "322933109106409472",
                "order_no": "YWDD20260610106678",
                "order_sub_id": "322978240647921664",
                "order_sub_no": "ZDD20260610015029",
                "bl_no": "codfishe2e1",
                "delete_id": null,
                "delete_time": null,
                "customer_id": "16",
                "customer_name": "兰森玻璃（青岛）有限公司",
                "customer_main_id": "31",
                "customer_main_name": "青岛易汇智供应链管理有限公司",
                "put_settle_object_id": "665",
                "put_settle_object": "青岛易汇智供应链管理有限公司",
                "main_id": "1",
                "main_name": "青岛易航道物流科技有限公司",
                "pay_settle_object_id": "39",
                "pay_settle_object": "上海华运船务有限公司青岛分公司",
                "business_main_id": "1",
                "business_main_name": "青岛易航道物流科技有限公司",
                "book_supplier_id": "8",
                "book_supplier_name": "上海华运船务有限公司青岛分公司",
                "policy_type": "JSZX",
                "trade_term": "CIF",
                "customer_period": "60",
                "customer_put_date": "1786291200",
                "atd": "1781020800",
                "create_time": "1781060453",
                "finance_date": "1781020800",
                "our_company_settle_no": null,
                "remark_cny": null,
                "remark_usd": null,
                "ship_name": "codfishe2e1",
                "voy": "codfishe2e1",
                "etd": "1781020800",
                "service_project_name": "订舱",
                "fee_type_name": "标准费用",
                "policy_type_name": "结算业务",
                "order_main_finance_id": null,
                "f_main_name": null,
                "bank_account_cny": null,
                "open_bank_cny": null,
                "bank_account_usd": "802051200001568",
                "open_bank_usd": "青岛银行股份有限公司江西路支行",
                "book_supplier_period": "30",
                "book_supplier_pay_date": "1784476800",
                "order_main_finance_usd": "青岛银行股份有限公司江西路支行+USD+802051200001568",
                "order_main_finance_cny": null,
                "sys_upttime": "2026-06-10 15:52:45",
                "customer_order_sn": "codfishe2e1",
                "operable_amount": "100.00",
                "remark": null,
                "amount_list": [
                    {
                        "receive_invoice_batch_fee_id": "323006563394519040",
                        "receive_invoice_batch_id": "323006563193192448",
                        "receive_invoice_apply_id": "323008151559340032",
                        "receive_invoice_apply_no": "YSKPSQ20260610001750",
                        "order_fee_real_id": "322978255550285824",
                        "fee_same_id": "322978255550284800",
                        "cost_no": "0001",
                        "fee_real_no": "FY202606101285504",
                        "fee_type": "0",
                        "fee_type_name": "标准费用",
                        "service_project": "booking_space",
                        "service_project_name": "订舱",
                        "fee_real_name": "海运费",
                        "currency": "USD",
                        "real_total": "100.00",
                        "order_id": "322933109106409472",
                        "order_no": "YWDD20260610106678",
                        "order_sub_id": "322978240647921664",
                        "order_sub_no": "ZDD20260610015029",
                        "bl_no": "codfishe2e1",
                        "delete_id": null,
                        "delete_time": null,
                        "customer_id": "16",
                        "customer_name": "兰森玻璃（青岛）有限公司",
                        "customer_main_id": "31",
                        "customer_main_name": "青岛易汇智供应链管理有限公司",
                        "put_settle_object_id": "665",
                        "put_settle_object": "青岛易汇智供应链管理有限公司",
                        "main_id": "1",
                        "main_name": "青岛易航道物流科技有限公司",
                        "pay_settle_object_id": "39",
                        "pay_settle_object": "上海华运船务有限公司青岛分公司",
                        "business_main_id": "1",
                        "business_main_name": "青岛易航道物流科技有限公司",
                        "book_supplier_id": "8",
                        "book_supplier_name": "上海华运船务有限公司青岛分公司",
                        "policy_type": "JSZX",
                        "trade_term": "CIF",
                        "customer_period": "60",
                        "customer_put_date": "1786291200",
                        "atd": "1781020800",
                        "create_time": "1781060453",
                        "finance_date": "1781020800",
                        "our_company_settle_no": null,
                        "pay_date": "1784476800",
                        "supplier_period": "30",
                        "ship_name": "codfishe2e1",
                        "voy": "codfishe2e1",
                        "etd": "1781020800",
                        "policy_type_name": "结算业务",
                        "order_main_finance_id": null,
                        "f_main_name": null,
                        "bank_account_cny": null,
                        "open_bank_cny": null,
                        "bank_account_usd": "802051200001568",
                        "open_bank_usd": "青岛银行股份有限公司江西路支行",
                        "book_supplier_period": "30",
                        "book_supplier_pay_date": "1784476800",
                        "order_main_finance": "青岛银行股份有限公司江西路支行+USD+802051200001568",
                        "sys_upttime": "2026-06-10 15:59:05",
                        "real_amount": "100.00"
                    }
                ]
            }
        ],
        "order_sub_id": [
            "322978240647921664"
        ],
        "usd_file_id": [],
        "invoice_item_str": "6%；国际货物运输代理海运费",
        "usd_require": {
            "receive_invoice_batch_require_id": "323006564380180480",
            "require_currency": "USD",
            "receive_invoice_batch_id": "323006563193192448",
            "receive_invoice_apply_id": "323008151559340032",
            "currency": "CNY",
            "amount_total_usd": "100.00",
            "amount_total_cny": null,
            "rate": "7.7000",
            "turn_amount_total_cny": "770.00",
            "turn_amount_total_usd": null,
            "turn_amount_total": "770.00",
            "invoice_apply_name": "青岛易航道物流科技有限公司 + 青岛易汇智供应链管理有限公司 + 2026-06 + USD 100.00",
            "invoice_apply_simple": null,
            "invoice_form": "2",
            "invoice_type": "1",
            "invoice_items": null,
            "invoice_rate_type": null,
            "invoice_rate": null,
            "require_other": null,
            "remark": "青岛海发商业保理有限公司",
            "purchaser_id": "665",
            "purchaser_name": "青岛易汇智供应链管理有限公司",
            "purchaser_head_cn": "青岛易汇智供应链管理有限公司",
            "purchaser_tax_number": "91370202MAEWF5RN7G",
            "seller_id": "10",
            "seller_name": "224746757829",
            "seller_info": "{\"main_bank_id\":\"10\",\"main_id\":\"1\",\"chinese_header\":\"青岛易航道物流科技有限公司\",\"english_header\":\"\",\"identifier_no\":\"91370202MABU30PK3F\",\"currency\":\"CNY\",\"is_public\":\"0\",\"fund_code\":\"\",\"bank_account\":\"224746757829\",\"swift_code\":\"\",\"register_address_cn\":\"山东省青岛市市南区香港西路48号海天中心2座2101\",\"register_address_en\":\"\",\"open_bank_no\":\"\",\"open_bank_cn\":\"中国银行青岛市北支行\",\"open_bank_en\":\"\",\"bank_address_en\":\"\",\"remark\":\"\",\"create_id\":\"294\",\"create_by\":\"于佳倩TIDB\",\"create_time\":\"1776062439\",\"pay_default\":\"0\",\"put_default\":\"0\",\"sys_upttime\":\"2026-05-15 10:48:52\",\"fund_name\":\"\",\"is_public_name\":\"否\",\"value\":\"10\"}",
            "fast_remark": "[]",
            "truck_remark": null,
            "invoice_items_count": "1",
            "sys_upttime": "2026-06-10 15:59:04",
            "invoice_items_name": null,
            "trade_terms": "CIF",
            "rate_list": [
                {
                    "receive_invoice_batch_fee_rate_id": "323006564480843776",
                    "receive_invoice_batch_id": "323006563193192448",
                    "receive_invoice_batch_require_id": "323006564380180480",
                    "invoice_item": "2",
                    "cost_no": "0001",
                    "cost_name": "海运费",
                    "invoice_rate": "6",
                    "invoice_items": null,
                    "turn_cost_cny": null,
                    "currency": "USD",
                    "sys_upttime": "2026-06-10 15:52:46",
                    "invoice_item_name": "国际货物运输代理海运费"
                }
            ]
        },
        "audit_records": {
            "audit_no": "SP20260610002397",
            "audit_status": "2",
            "audit_status_name": "审批通过",
            "record": [
                {
                    "audit_by": "刘常春TiDB",
                    "audit_user_time": "1781078344",
                    "audit_user_status": "2",
                    "audit_user_status_name": "审批通过",
                    "audit_remark": "",
                    "node_name": "开票批次申请-财务",
                    "audit_no": "SP20260610002397",
                    "audit_status": "2",
                    "audit_status_name": "审批通过"
                }
            ]
        },
        "apply_list": [
            {
                "receive_invoice_apply_no": "YSKPSQ20260610001750",
                "invoice_status": "2",
                "cancel_status": "1",
                "invoice_apply_name": "青岛易航道物流科技有限公司 + 青岛易汇智供应链管理有限公司 + 2026-06 + USD 100.00",
                "invoice_apply_simple": null,
                "batch_apply_name": "青岛易航道物流科技有限公司 + 青岛易汇智供应链管理有限公司 + 2026-06 + USD 100.00",
                "batch_apply_simple": null,
                "invoice_status_name": "未开票",
                "cancel_status_name": "已生效"
            }
        ]
    },
    "request_id": "c1208b318820d08867ad2ce12cba5140"
}
```


36 返回信息

```json
{
    "code": 200,
    "msg": "成功",
    "data": {
        "total": 1,
        "data": [
            {
                "_class": "org.fin.es.entity.EsFeeReal",
                "order_fee_real_id": "322978255550283776",
                "order_id": "322933109106409472",
                "order_sub_id": "322974684981231616",
                "unique_id": "91c9f422-ae3c-4cfe-968e-085a23828cab",
                "order_fee_expect_no": "",
                "finance_fee": "1",
                "cost_id": "17",
                "cost_no": "0001",
                "cost_name": "海运费",
                "cost_label": "0",
                "service_project": "booking_space",
                "customer_period": "60",
                "take_date": "1786291200",
                "supplier_period": "30",
                "supplier_id": "8",
                "pay_date": "1784476800",
                "fee_type": "0",
                "fee_real_no": "FY202606101285502",
                "settle_object_id": "37",
                "settle_object": "兰森玻璃（青岛）有限公司",
                "put_settle_object": "兰森玻璃（青岛）有限公司",
                "put_settle_object_id": "37",
                "pay_settle_object": "青岛易航道物流科技有限公司",
                "pay_settle_object_id": "1",
                "real_settle_object_id": "39",
                "real_settle_object": "上海华运船务有限公司青岛分公司",
                "fee_real_name": "海运费",
                "version": "",
                "symbol": "1",
                "currency": "USD",
                "unit": "box",
                "unit_price": 100,
                "amount": 100,
                "discount_amount": 100,
                "real_total": 100,
                "folde_total": 770,
                "discount_ratio": "100",
                "discount_status": "2",
                "exchange_rate": 7.7,
                "specs": "40HQ",
                "num": "1",
                "pay_account_id": "0",
                "pay_account_no": "",
                "pay_account_status": "0",
                "pay_account_time": "0",
                "account_no": "",
                "account_status": "0",
                "receive_invoice_batch_id": "0",
                "receive_invoice_apply_id": "0",
                "invoice_status": "0",
                "invoice_ids": "",
                "invoice_amount": 0,
                "writeoff_ids": "",
                "writeoff_nos": "",
                "writeoff_status": "1",
                "writeoff_time": "",
                "writeoff_force_audit_status": "0",
                "un_writeoff_amount": "100.00",
                "use_writeoff_amount": "0.00",
                "writeoff_exchange_rate": "",
                "writeoff_banks": "",
                "pay_demand_id": "0",
                "pay_form_id": "",
                "fee_status": "1",
                "examine_status": "2",
                "lock_time": "1781073551",
                "lock_exchange_rate": 7.7,
                "create_id": "828",
                "fee_create_time": "1781060453",
                "update_id": "828",
                "update_by": "GIMBAL",
                "update_time": "1781075135",
                "delete_time": "0",
                "cancel_time": "0",
                "conduct_ratio": "100",
                "pay_invoice_batch_id": "0",
                "pay_invoice_apply_id": "0",
                "is_round": "0",
                "customer_fee": "1",
                "supplier_fee": "0",
                "policy_id": "112",
                "policy_name": "【SPV对客】易汇智",
                "policy_sub_id": "365",
                "policy_sub_name": "100%穿行",
                "policy_sub_status": "1",
                "subsidy_category": "0",
                "pay_demand_no": "",
                "pay_form_no": "",
                "fee_same_id": "",
                "opposite_fee_no": "",
                "is_penetrate": "0",
                "fee_main_id": "665",
                "order_no": "YWDD20260610106678",
                "bl_no": "codfishe2e1",
                "main_id": "31",
                "main_name": "青岛易汇智供应链管理有限公司",
                "customer_id": "16",
                "customer_name": "兰森玻璃（青岛）有限公司",
                "customer_category": ",2,",
                "customer_main_id": "31",
                "customer_main_name": "青岛易汇智供应链管理有限公司",
                "fund_code": "F0036",
                "fund_name": "青岛海发商业保理有限公司",
                "pay_status": "0",
                "business_main_id": "1",
                "business_main_name": "青岛易航道物流科技有限公司",
                "booking_space_supplier_id": "8",
                "booking_space_supplier_name": "上海华运船务有限公司青岛分公司",
                "policy_type": "JSZX",
                "main_ids": ",31,1,",
                "main_sort": "易汇智,易航道",
                "status": "2",
                "business_type": "1",
                "trade_term": "CIF",
                "carrier_id": "1",
                "carrier": "ACL",
                "etd": "1781020800",
                "atd": "1781020800",
                "track_atd": "0",
                "finance_date": "1781020800",
                "ship_name": "codfishe2e1",
                "voy": "codfishe2e1",
                "pol": "QINGDAO,CHINA",
                "pol_cn": "青岛流亭机场",
                "pol_country_id": "1",
                "pol_country": "CHINA",
                "pol_country_cn": "中国",
                "pod": "QINGDAO,CHINA",
                "pod_cn": "青岛港",
                "pot": "QINGDAO,CHINA",
                "pot_cn": "青岛港",
                "del": "QINGDAO,CHINA",
                "del_cn": "青岛港",
                "country_id": "1",
                "country_name": "CHINA",
                "country_name_cn": "中国",
                "ocean_type": "近洋",
                "airline_type": "中国",
                "volume": "1*40HQ",
                "volume_desc": "普柜",
                "teu": "2",
                "discount_rule": "",
                "discount_currency": "",
                "book_upload_date": "0",
                "trans_cost_put_preserve_date": "1781071216",
                "bl_no_upload_date": "0",
                "supplier_invoice_date": "0",
                "supplier_invoice_taketime": "0",
                "real_cost_date": "1781072551",
                "customer_invoice_request_date": "0",
                "sale_id": "0",
                "sale_name": "",
                "service_id": "55",
                "service_name": "曲静霞",
                "operator_id": "327",
                "operator_name": "王晓涵",
                "period_rule": "1",
                "is_special_pay": "0",
                "term_rule_name": "标准规则",
                "cancel_remark": "",
                "order_create_time": "1781060453",
                "order_create_id": "828",
                "create_by": "GIMBAL",
                "order_sub_no": "ZDD20260610015012",
                "business_no": "YHZ20260610032835",
                "audit_type": "",
                "fee_lock_status": "2",
                "client_expand_name": "孙硕",
                "client_expand_id": "250",
                "is_loan_before_invoice": "1",
                "pay_status_name": "",
                "customer_put_date": "1786291200",
                "business_type_name": "海运整箱",
                "policy_type_name": "结算业务",
                "trade_term_name": "CIF",
                "negative_fee": 0,
                "book_supplier_name": "上海华运船务有限公司青岛分公司",
                "order_fee_real_ids": [
                    "322978255550283776"
                ],
                "writeoff_object": [
                    {
                        "order_fee_real_id": "322978255550283776",
                        "un_writeoff_amount": "100.00",
                        "use_writeoff_amount": "0.00"
                    }
                ],
                "invoice_currency": []
            }
        ]
    },
    "request_id": "0435c2b3ed736cadd5522f992a76c412"
}
```


34 返回信息

```json
{
    "code": 200,
    "msg": "成功",
    "data": [
        {
            "main_id": "31",
            "main_name": "青岛易汇智供应链管理有限公司",
            "symbol": "0",
            "settle_object_id": "1",
            "order_ids": "322933109106409472",
            "order_sub_ids": "322974684981231616",
            "order_sub_types": "0",
            "unique_ids": "91c9f422-ae3c-4cfe-968e-085a23828cab",
            "receive_account_no": "",
            "account_simple_name": "",
            "symbol_name": "应付",
            "settle_object": "青岛易航道物流科技有限公司",
            "account_batch_name": "青岛易汇智供应链管理有限公司+青岛易航道物流科技有限公司+26.06+USD100",
            "order_sub_type": 1,
            "only_adjust_status": 0,
            "real_amount_ids": [
                "322978255550284800"
            ],
            "currency_list": [
                "USD"
            ]
        }
    ],
    "request_id": "49b2642f2dadeacfe38304721bf90309"
}
```

33 返回信息

```json
{
    "code": 200,
    "msg": "成功",
    "data": {
        "receive_account": {
            "receive_account_id": "322996617806348288",
            "parent_id": "0",
            "order_id": "0",
            "receive_account_no": "YSDZPC20260610002377",
            "relation_account_no": null,
            "account_batch_name": "青岛易航道物流科技有限公司+青岛易汇智供应链管理有限公司+26.06+USD100",
            "account_simple_name": "",
            "customer_id": "16",
            "customer_ids": "16",
            "customer_num": "1",
            "customer_main_id": "1",
            "customer_main_name": "青岛易航道物流科技有限公司",
            "customer_main_num": "1",
            "business_main_id": "1",
            "business_main_name": "青岛易航道物流科技有限公司",
            "business_main_num": "1",
            "book_supplier_id": "8",
            "book_supplier_ids": "8",
            "book_supplier_num": "1",
            "pay_settle_object_id": "39",
            "pay_settle_object": "上海华运船务有限公司青岛分公司",
            "pay_settle_object_num": "1",
            "put_settle_object_id": "665",
            "put_settle_object": "青岛易汇智供应链管理有限公司",
            "put_settle_object_num": "1",
            "main_id": "1",
            "main_name": "青岛易航道物流科技有限公司",
            "account_type": "1",
            "batch_status": "1",
            "account_status": "1",
            "account_num": "1",
            "account_cny": "0.00",
            "account_usd": "100.00",
            "create_id": "828",
            "create_time": "1781075594",
            "cancel_time": null,
            "create_by": "GIMBAL",
            "operate_type": "1",
            "etd": "202606",
            "atd": "202606",
            "account_time": null,
            "account_by": null,
            "currency": "USD",
            "bl_nos": "codfishe2e1",
            "cancel_remark": null,
            "sys_upttime": "2026-06-10 15:13:14",
            "account_status_name": "对账中",
            "batch_status_name": "已生效",
            "account_type_name": "同一客户",
            "put_settle_relation_id": "31",
            "put_settle_sorce": "main",
            "customer_name": "兰森玻璃（青岛）有限公司",
            "customer_remark_show": true,
            "customer_remark": "",
            "book_supplier_name": "上海华运船务有限公司青岛分公司"
        },
        "receive_account_orders": {
            "list": [
                {
                    "receive_order_id": "322996618414522368",
                    "receive_account_id": "322996617806348288",
                    "order_id": "322933109106409472",
                    "order_sub_id": "322978240647921664",
                    "order_no": "YWDD20260610106678",
                    "order_sub_no": "ZDD20260610015029",
                    "bl_no": "codfishe2e1",
                    "customer_name": "兰森玻璃（青岛）有限公司",
                    "put_settle_object": "青岛易汇智供应链管理有限公司",
                    "ship_name": "codfishe2e1",
                    "voy": "codfishe2e1",
                    "atd": "1781020800",
                    "etd": "1781020800",
                    "account_cny": "0.00",
                    "account_usd": "100.00",
                    "delete_id": "0",
                    "delete_time": "0",
                    "cancel_time": "0",
                    "sys_upttime": "2026-06-10 15:13:14",
                    "trade_term": "CIF"
                }
            ],
            "usd_total": "100.00",
            "cny_total": "0.00",
            "contain_amount_status": "usd"
        },
        "receive_account_file": []
    },
    "request_id": "234f344b70dca3f068922bc32730b4bd"
}
```

30 返回信息

```json
{
    "code": 200,
    "msg": "成功",
    "data": {
        "customer_name": [
            "兰森玻璃（青岛）有限公司"
        ],
        "main_name_cn": [
            "青岛易航道物流科技有限公司"
        ],
        "settle_object": [
            "青岛易汇智供应链管理有限公司"
        ],
        "total": 1,
        "data": [
            {
                "order_id": "322933109106409472",
                "order_no": "YWDD20260610106678",
                "bl_no": "codfishe2e1",
                "customer_id": "16",
                "customer_name": "兰森玻璃（青岛）有限公司",
                "customer_main_id": "31",
                "customer_main_name": "青岛易汇智供应链管理有限公司",
                "business_main_id": "1",
                "business_main_name": "青岛易航道物流科技有限公司",
                "policy_type": "JSZX",
                "trade_term": "CIF",
                "customer_period": "60",
                "customer_put_date": "1786291200",
                "atd": "1781020800",
                "etd": "1781020800",
                "create_time": "1781060453",
                "finance_date": "1781020800",
                "fund_name": "青岛海发商业保理有限公司",
                "ship_name": "codfishe2e1",
                "voy": "codfishe2e1",
                "status": "2",
                "is_special_pay": "0",
                "pay_status": "0",
                "is_loan_before_invoice": "1",
                "customer_order_sn": "codfishe2e1",
                "order_sub_id": "322978240647921664",
                "order_sub_no": "ZDD20260610015029",
                "main_id": "1",
                "main_name": "青岛易航道物流科技有限公司",
                "service_project": "booking_space",
                "currency": "USD",
                "amount_total": "100.00",
                "pay_settle_object_type": "2",
                "put_settle_object_id": "665",
                "put_settle_object": "青岛易汇智供应链管理有限公司",
                "pay_settle_object": "上海华运船务有限公司青岛分公司",
                "book_supplier_period": "30",
                "book_supplier_pay_date": "1784476800",
                "book_supplier_name": "上海华运船务有限公司青岛分公司",
                "operable_amount": "100.00",
                "un_operable_amount": "0.00",
                "operable_flag": "all",
                "policy_type_name": "结算业务",
                "order_sub_currency": "USD322978240647921664",
                "order_main_finance": "青岛银行股份有限公司江西路支行+USD+802051200001568",
                "order_error_messages": [],
                "order_error_message": "",
                "order_error_flag": false,
                "amount_list": [
                    {
                        "order_id": "322933109106409472",
                        "order_no": "YWDD20260610106678",
                        "customer_name": "兰森玻璃（青岛）有限公司",
                        "bl_no": "codfishe2e1",
                        "main_name": "青岛易航道物流科技有限公司",
                        "order_sub_no": "ZDD20260610015029",
                        "order_sub_id": "322978240647921664",
                        "order_fee_real_id": "322978255550285824",
                        "fee_real_no": "FY202606101285504",
                        "fee_type": "0",
                        "service_project": "booking_space",
                        "fee_real_name": "海运费",
                        "currency": "USD",
                        "symbol": "1",
                        "real_amount": "100.00",
                        "supplier_id": null,
                        "cost_no": "0001",
                        "fee_status": "1",
                        "account_no": "",
                        "pay_account_no": "",
                        "account_status": "0",
                        "pay_account_status": "0",
                        "invoice_status": "0",
                        "receive_invoice_batch_no": null,
                        "pay_invoice_batch_no": null,
                        "receive_invoice_apply_no": null,
                        "pay_invoice_apply_no": null,
                        "put_settle_object_id": "665",
                        "put_settle_object": "青岛易汇智供应链管理有限公司",
                        "pay_settle_object_id": "39",
                        "pay_settle_object": "上海华运船务有限公司青岛分公司",
                        "writeoff_status": "1",
                        "un_writeoff_amount": "100.00",
                        "use_writeoff_amount": "0.00",
                        "writeoff_nos": "",
                        "pay_form_no": "",
                        "pay_demand_no": "",
                        "amount_error_messages": [],
                        "amount_error_message": "",
                        "amount_error_flag": false
                    }
                ]
            }
        ],
        "select_summary": {
            "total_bl_no_num": 1,
            "total_bl_nos": [
                "codfishe2e1"
            ],
            "find_bl_no_num": 1,
            "find_bl_nos": [
                "codfishe2e1"
            ],
            "not_find_bl_no_num": 0,
            "not_find_bl_nos": [],
            "cancel_bl_no_num": 0,
            "cancel_bl_nos": []
        }
    },
    "request_id": "6daf41d11fcf1387c676b9044ba210bc"
}
```


28 返回信息

```json
{
    "code": 200,
    "msg": "成功",
    "data": [
        {
            "audit_id": "322979315513819136",
            "audit_no": "SP20260610002335",
            "audit_type": "actualCostFeeLockApplication",
            "audit_name": "费用锁定",
            "audit_status": "4",
            "create_by": "GIMBAL",
            "create_time": "1781071469",
            "current_node_id": "322979315673202688",
            "audit_status_name": "撤销审批",
            "node_name": "审批节点1"
        },
        {
            "audit_id": "322983853553614848",
            "audit_no": "SP20260610002336",
            "audit_type": "actualCostFeeLockApplication",
            "audit_name": "费用锁定",
            "audit_status": "2",
            "create_by": "GIMBAL",
            "create_time": "1781072551",
            "current_node_id": "322983853712998400",
            "audit_status_name": "审批通过",
            "node_name": "审批节点1"
        },
        {
            "audit_id": "322992855406608384",
            "audit_no": "SP20260610002375",
            "audit_type": "addLoanBeforeInvoiceApply",
            "audit_name": "未放款开票申请",
            "audit_status": "1",
            "create_by": "GIMBAL",
            "create_time": "1781074697",
            "current_node_id": "322992855561797632",
            "audit_status_name": "审批中",
            "node_name": "未放款开票申请"
        }
    ],
    "request_id": "19e98ec85a839c377e5883c910d427cb"
}
```


23的返回信息

```json
{
    "code": 200,
    "msg": "成功",
    "data": {
        "customer_currency_finance": {
            "USD": [
                {
                    "customer_finance_id": "2895",
                    "customer_id": "16",
                    "chinese_header": "兰森玻璃（青岛）有限公司",
                    "english_header": "",
                    "identifier_no": "91370283591262431N",
                    "phone": "15275268026",
                    "currency": "USD",
                    "bank_account": "91370283591262431N",
                    "swift_code": "",
                    "register_address": "青岛市平度市南村镇东王府庄村",
                    "open_bank_cn": "中国银行青岛澳门路支行",
                    "remark": "",
                    "update_id": "55",
                    "update_by": "曲静霞",
                    "delete_time": "0",
                    "sys_upttime": "2026-05-15 10:49:36",
                    "flag": "CustomerFinance"
                }
            ],
            "CNY": [
                {
                    "customer_finance_id": "2896",
                    "customer_id": "16",
                    "chinese_header": "兰森玻璃（青岛）有限公司",
                    "english_header": "",
                    "identifier_no": "91370283591262431N",
                    "phone": "15275268026",
                    "currency": "CNY",
                    "bank_account": "38-160901040007028",
                    "swift_code": "",
                    "register_address": "青岛市平度市南村镇东王府庄村",
                    "open_bank_cn": " 中国农业银行股份有限公司平度南村镇分理处",
                    "remark": "",
                    "update_id": "55",
                    "update_by": "曲静霞",
                    "delete_time": "0",
                    "sys_upttime": "2026-05-15 10:49:36",
                    "flag": "CustomerFinance"
                }
            ],
            "use_usd": false,
            "use_cny": false
        },
        "main_currency_bank": {
            "USD": [
                {
                    "main_bank_id": "77",
                    "main_id": "31",
                    "chinese_header": "青岛易汇智供应链管理有限公司",
                    "english_header": "",
                    "identifier_no": "91370202MAEWF5RN7G",
                    "currency": "USD",
                    "is_public": "1",
                    "fund_code": "青岛海发商业保理有限公司",
                    "bank_account": "802051200001568",
                    "swift_code": "QCCBCNBQ或 QCCBCNBQXXX",
                    "register_address_cn": "山东省青岛市市南区江西路89号3号楼乙102-A121",
                    "register_address_en": "",
                    "open_bank_no": "",
                    "open_bank_cn": "青岛银行股份有限公司江西路支行",
                    "open_bank_en": "",
                    "bank_address_en": "",
                    "remark": "",
                    "create_id": "41",
                    "create_by": "孙奉盛",
                    "create_time": "1766743074",
                    "pay_default": "1",
                    "put_default": "1",
                    "sys_upttime": "2026-05-15 10:48:52",
                    "flag": "MainBank",
                    "is_public_name": "是"
                }
            ],
            "CNY": [
                {
                    "main_bank_id": "78",
                    "main_id": "31",
                    "chinese_header": "青岛易汇智供应链管理有限公司",
                    "english_header": "",
                    "identifier_no": "91370202MAEWF5RN7G",
                    "currency": "CNY",
                    "is_public": "1",
                    "fund_code": "青岛海发商业保理有限公司",
                    "bank_account": "802050200740776",
                    "swift_code": "",
                    "register_address_cn": "山东省青岛市市南区江西路89号3号楼乙102-A121",
                    "register_address_en": "",
                    "open_bank_no": "",
                    "open_bank_cn": "青岛银行股份有限公司江西路支行",
                    "open_bank_en": "",
                    "bank_address_en": "",
                    "remark": "",
                    "create_id": "41",
                    "create_by": "孙奉盛",
                    "create_time": "1766743074",
                    "pay_default": "1",
                    "put_default": "1",
                    "sys_upttime": "2026-05-15 10:48:52",
                    "flag": "MainBank",
                    "is_public_name": "是"
                }
            ],
            "disable_usd": true,
            "disable_cny": true
        },
        "main_name": "青岛易汇智供应链管理有限公司"
    },
    "request_id": "7a313e2338e189fdb5f164d6a06b2bfc"
}
```


22的返回信息

```json
{
    "code": 200,
    "msg": "审批成功1条，审批失败0条",
    "data": [],
    "request_id": "2a12a764551cbbf14df4edce767a43f7"
}
```

20的返回信息

```json
{
    "code": 200,
    "msg": "成功",
    "data": [
        {
            "audit_id": "322979315513819136",
            "audit_no": "SP20260610002335",
            "audit_type": "actualCostFeeLockApplication",
            "audit_name": "费用锁定",
            "audit_status": "4",
            "create_by": "GIMBAL",
            "create_time": "1781071469",
            "current_node_id": "322979315673202688",
            "audit_status_name": "撤销审批",
            "node_name": "审批节点1"
        },
        {
            "audit_id": "322983853553614848",
            "audit_no": "SP20260610002336",
            "audit_type": "actualCostFeeLockApplication",
            "audit_name": "费用锁定",
            "audit_status": "1",
            "create_by": "GIMBAL",
            "create_time": "1781072551",
            "current_node_id": "322983853712998400",
            "audit_status_name": "审批中",
            "node_name": "审批节点1"
        }
    ],
    "request_id": "37a42c6b26125bea290ff51d1a7d54c9"
}
```

3的返回信息

```json
{
    "code": 200,
    "msg": "成功",
    "data": {
        "total": 1,
        "data": [
            {
                "_class": "org.fin.es.entity.EsOrder",
                "order_id": "322933109106409472",
                "order_no": "YWDD20260610106678",
                "customer_id": "16",
                "customer_name": "兰森玻璃（青岛）有限公司",
                "customer_category": "发货人",
                "customer_categories": [
                    "2"
                ],
                "customer_tax_number": "91370283591262431N",
                "customer_address_cn": "山东省青岛市平度市南村镇东王府庄村",
                "sale_id": "0",
                "sale_name": "",
                "service_id": "55",
                "service_name": "曲静霞",
                "operate_id": "327",
                "operator_name": "王晓涵",
                "customer_contact_id": "1547",
                "customer_contact_name": "周经理",
                "customer_contact_phone": "18561657088",
                "customer_main_id": "31",
                "customer_main_name": "青岛易汇智供应链管理有限公司",
                "business_main_id": "1",
                "business_main_name": "青岛易航道物流科技有限公司",
                "main_sort": "易汇智,易航道",
                "bl_no": "codfishe2e1",
                "policy_type": "JSZX",
                "fund_code": "",
                "policy_id": "112",
                "policy_name": "【SPV对客】易汇智",
                "business_type": "1",
                "trade_term": "CIF",
                "carrier_id": "1",
                "carrier": "ACL",
                "etd": "1781020800",
                "atd": "1781020800",
                "track_atd": "0",
                "finance_date": "1781020800",
                "ship_name": "codfishe2e1",
                "voy": "codfishe2e1",
                "pol": "QINGDAO,CHINA",
                "pol_cn": "青岛流亭机场",
                "pol_country_id": "1",
                "pol_country": "CHINA",
                "pol_country_cn": "中国",
                "pod": "QINGDAO,CHINA",
                "pod_cn": "青岛港",
                "pot": "QINGDAO,CHINA",
                "pot_cn": "青岛港",
                "del": "QINGDAO,CHINA",
                "del_cn": "青岛港",
                "country_id": "1",
                "country_name": "CHINA",
                "country_name_cn": "中国",
                "ocean_type": "近洋",
                "airline_type": "中国",
                "terms_payment": "T\/T",
                "terms_transport": "CY\/CY",
                "terms_shipment": "codfishe2e1",
                "pay_type": "FREIGHT PREPAID",
                "customer_order_sn": "codfishe2e1",
                "cargo_type": "goods",
                "num": "1",
                "packer": "",
                "gross_weight": 100,
                "bulk": 100,
                "volume": "1*40HQ",
                "volume_desc": "普柜",
                "teu": "2",
                "sea_trans_cost": 100,
                "sea_trans_currency": "USD",
                "shipper": "codfishe2e1",
                "consignee": "codfishe2e1",
                "notifier": "codfishe2e1",
                "ship_mark": "codfishe2e1",
                "commodity": "codfishe2e1",
                "notes": "codfishe2e1",
                "customer_period": "60",
                "customer_settlement_date": "10",
                "period_rule": "0",
                "customer_due_date": "0",
                "customer_put_date": "0",
                "customer_put_date_manual": "0",
                "customer_put_writeoff_date": "0",
                "supplier_dueDate": "0",
                "discount_start": "0",
                "discount_rule": "",
                "discount_end": "0",
                "discount_ratio": "0%",
                "discount_status": "2",
                "discount_currency": "",
                "book_upload_date": "0",
                "trans_cost_put_preserve_date": "0",
                "bl_no_upload_date": "0",
                "supplier_invoice_date": "0",
                "supplier_invoice_taketime": "0",
                "real_cost_date": "0",
                "customer_invoice_request_date": "0",
                "first_financing_doc_ok_date": "0",
                "second_financing_doc_ok_date": "0",
                "insurance_doc_ok_date": "0",
                "customer_confirm_date": "0",
                "is_delayed_recovery": "0",
                "delayed_recovery_usd": 0,
                "delayed_recovery_cny": 0,
                "delayed_time": "0",
                "expect_fee_status": "0",
                "real_fee_status": "0",
                "pay_account_status": "0",
                "account_status": "0",
                "real_pay_usd": 0,
                "real_pay_cny": 0,
                "real_put_usd": 0,
                "real_put_cny": 0,
                "real_put_discount_rate": 0,
                "exchange_rate": 0,
                "folde_pay_usd": 0,
                "folde_put_usd": 0,
                "folde_pay_total": 0,
                "folde_put_total": 0,
                "gross_margin": 0,
                "gross_margin_rate": "0%",
                "is_special_pay": "0",
                "is_fee_miss": "0",
                "fee_miss_name": "",
                "service_items": "booking_space",
                "status": "1",
                "cancel_remark": "",
                "cancel_time": "0",
                "effective_id": "0",
                "effective_by": "",
                "effective_time": "0",
                "create_id": "828",
                "create_by": "GIMBAL",
                "create_time": "1781060453",
                "update_id": "828",
                "update_by": "GIMBAL",
                "update_time": "1781060453",
                "delete_time": "0",
                "main_ids": "31,1",
                "reverse_status": "0",
                "proprietary_business_status": "0",
                "m_delivery_type": "1",
                "loan_pay_status": "",
                "change_type": "0",
                "copy_order_id": "0",
                "real_fee_locked": "0",
                "supplier_names": "上海华运船务有限公司青岛分公司",
                "supplier_ids": [
                    "8"
                ],
                "booking_space_supplier_id": "8",
                "booking_space_supplier_name": "上海华运船务有限公司青岛分公司",
                "booking_space_supplier_period": "30",
                "booking_space_supplier_pay_date": "0",
                "customs_clearance_supplier_name": "",
                "customs_clearance_supplier_period": "0",
                "manifest_supplier_name": "",
                "manifest_supplier_period": "0",
                "insurance_supplier_name": "",
                "trucking_supplier_name": "",
                "trucking_supplier_period": "0",
                "is_usd_project": "2",
                "pay_status": "1",
                "order_allowance_cny": 0,
                "order_allowance_usd": 0,
                "entrust_status": "1",
                "audit_type": "",
                "audit_type_list": [],
                "is_financing": "0",
                "confirm_status": "0",
                "is_traverse": "0",
                "financing_apply_amount": 0,
                "financing_apply_amount_cny": 0,
                "financing_apply_amount_usd": 0,
                "fee_lock_status": "0",
                "client_expand_name": "孙硕",
                "client_expand_id": "250",
                "is_loan_before_invoice": "0",
                "order_sub_no": "",
                "business_no": "",
                "status_name": "草稿",
                "real_fee_status_name": "创建中",
                "fee_lock_status_name": "创建中",
                "is_loan_before_invoice_name": "未申请",
                "service_items_name": "订舱",
                "discount_status_name": "—",
                "reverse_status_name": "否",
                "is_delayed_recovery_name": "否",
                "is_traverse_name": "未生成",
                "confirm_status_name": "待推送",
                "is_special_pay_name": "未申请",
                "is_fee_miss_name": "否",
                "period_rule_name": "",
                "policy_type_name": "结算业务",
                "business_type_name": "海运整箱",
                "is_financing_name": "否",
                "finance_status": true,
                "pay_status_name": "未放款",
                "fund_name": "",
                "customer_account_status_name": "未对账",
                "customer_invoice_status_name": "未开票",
                "customer_writeoff_status_name": "未核销",
                "supplier_account_status_name": "未对账",
                "supplier_invoice_status_name": "未开票",
                "supplier_writeoff_status_name": "未核销",
                "audit_type_name": "",
                "entrust_status_name": "未分发"
            }
        ]
    },
    "request_id": "69f3b7a4f9f96958bcbf3aeb9b3dce0f"
}
```


4. 的返回信息

```json
{
    "code": 200,
    "msg": "成功",
    "data": {
        "order_id": "322933109106409472",
        "order_no": "YWDD20260610106678",
        "customer_id": "16",
        "customer_name": "兰森玻璃（青岛）有限公司",
        "customer_category": ",2,",
        "customer_tax_number": "91370283591262431N",
        "customer_address_cn": "山东省青岛市平度市南村镇东王府庄村",
        "sale_id": "",
        "sale_name": "",
        "service_id": "55",
        "client_expand_id": "250",
        "client_expand_name": "孙硕",
        "service_name": "曲静霞",
        "operator_id": "327",
        "operator_name": "王晓涵",
        "customer_contact_id": "1547",
        "customer_contact_name": "周经理",
        "customer_contact_phone": "18561657088",
        "customer_main_id": "31",
        "customer_main_name": "青岛易汇智供应链管理有限公司",
        "business_main_id": "1",
        "business_main_name": "青岛易航道物流科技有限公司",
        "main_sort": "易汇智,易航道",
        "bl_no": "codfishe2e1",
        "policy_type": "JSZX",
        "fund_code": "",
        "fund_name": null,
        "policy_id": "112",
        "policy_name": "【SPV对客】易汇智",
        "business_type": "1",
        "trade_term": "CIF",
        "carrier_id": "1",
        "carrier": "ACL",
        "etd": "1781020800",
        "atd": "1781020800",
        "track_atd": "0",
        "finance_date": "1781020800",
        "ship_name": "codfishe2e1",
        "voy": "codfishe2e1",
        "pol": "QINGDAO,CHINA",
        "pol_cn": "青岛流亭机场",
        "pol_country_id": "1",
        "pol_country": "CHINA",
        "pol_country_cn": "中国",
        "pod": "QINGDAO,CHINA",
        "pod_cn": "青岛港",
        "pot": "QINGDAO,CHINA",
        "pot_cn": "青岛港",
        "del": "QINGDAO,CHINA",
        "del_cn": "青岛港",
        "country_id": "1",
        "country_name": "CHINA",
        "country_name_cn": "中国",
        "ocean_type": "近洋",
        "airline_type": "中国",
        "terms_payment": "T\/T",
        "terms_transport": "CY\/CY",
        "terms_shipment": "codfishe2e1",
        "pay_type": "FREIGHT PREPAID",
        "customer_order_sn": "codfishe2e1",
        "cargo_type": "goods",
        "num": "1",
        "packer": "",
        "gross_weight": "100.000",
        "bulk": "100.000",
        "volume": "1*40HQ",
        "volume_desc": "普柜",
        "teu": "2",
        "sea_trans_cost": "100.00",
        "sea_trans_currency": "USD",
        "shipper": "codfishe2e1",
        "consignee": "codfishe2e1",
        "notifier": "codfishe2e1",
        "ship_mark": "codfishe2e1",
        "commodity": "codfishe2e1",
        "notes": "codfishe2e1",
        "customer_period": "60",
        "customer_settlement_date": "10",
        "period_rule": "0",
        "term_rule_name": null,
        "customer_due_date": "0",
        "customer_put_date": "0",
        "customer_payment_collection_date": null,
        "customer_put_date_manual": "0",
        "customer_put_writeoff_date": "",
        "supplier_due_date": "0",
        "discount_start": "0",
        "discount_rule": "",
        "discount_end": "0",
        "discount_ratio": "",
        "discount_status": "2",
        "discount_currency": "",
        "book_upload_date": "0",
        "trans_cost_put_preserve_date": "0",
        "bl_no_upload_date": "0",
        "supplier_invoice_date": "0",
        "supplier_invoice_taketime": "",
        "real_cost_date": "0",
        "customer_invoice_request_date": "0",
        "first_financing_doc_ok_date": "0",
        "second_financing_doc_ok_date": "0",
        "insurance_doc_ok_date": "0",
        "customer_confirm_date": "0",
        "is_delayed_recovery": "否",
        "delayed_recovery_usd": "",
        "delayed_recovery_cny": "",
        "delayed_time": "",
        "expect_fee_status": "0",
        "real_fee_status": "0",
        "fee_lock_status": "0",
        "pay_account_status": "0",
        "account_status": "0",
        "real_pay_usd": "0.00",
        "real_pay_cny": "0.00",
        "real_put_usd": "0.00",
        "real_put_cny": "0.00",
        "real_put_discount_rate": "0.00",
        "exchange_rate": "0.0000",
        "folde_pay_usd": "0.00",
        "folde_put_usd": "0.00",
        "folde_pay_total": "0.00",
        "folde_put_total": "0.00",
        "gross_margin": "0.00",
        "gross_margin_rate": "0.00",
        "is_special_pay": "0",
        "is_loan_before_invoice": "0",
        "is_fee_miss": "0",
        "fee_miss_name": "",
        "service_items": [
            {
                "service_item_name": "订舱",
                "service_item": "booking_space",
                "self_support": false,
                "expect_api": "\/order\/orderFee\/bookExpectAmountEdit",
                "real_api": "order\/orderFee\/bookRealAmountEdit",
                "is_select": 1
            },
            {
                "service_item_name": "报关",
                "service_item": "customs_clearance",
                "self_support": true,
                "expect_api": "order\/orderFee\/customsExpectAmountEdit",
                "real_api": "order\/orderFee\/customsRealAmountEdit",
                "is_select": 0
            },
            {
                "service_item_name": "舱单",
                "service_item": "manifest",
                "self_support": true,
                "expect_api": "order\/orderFee\/manifestExpectAmountEdit",
                "real_api": "order\/orderFee\/manifestRealAmountEdit",
                "is_select": 0
            },
            {
                "service_item_name": "保险",
                "service_item": "insurance",
                "self_support": true,
                "expect_api": "order\/orderFee\/insuranceExpectAmountEdit",
                "real_api": "order\/orderFee\/insuranceRealAmountEdit",
                "is_select": 0
            },
            {
                "service_item_name": "拖车",
                "service_item": "trucking",
                "self_support": true,
                "expect_api": "order\/orderFee\/trailerExpectAmountEdit",
                "real_api": "order\/orderFee\/trailerRealAmountEdit",
                "is_select": 0
            }
        ],
        "status": "1",
        "cancel_remark": "",
        "cancel_time": "0",
        "effective_id": "0",
        "effective_by": "",
        "effective_time": "0",
        "create_id": "828",
        "create_by": "GIMBAL",
        "create_time": "1781060453",
        "update_id": "828",
        "update_by": "GIMBAL",
        "update_time": "1781060453",
        "delete_time": "0",
        "business_time": "0",
        "main_ids": "31,1",
        "reverse_status": "0",
        "proprietary_business_status": "0",
        "m_delivery_type": "1",
        "loan_status": null,
        "first_status": null,
        "second_status": null,
        "loan_pay_status": "",
        "change_type": "0",
        "copy_order_id": "0",
        "real_fee_locked": false,
        "is_usd_project": "2",
        "pay_status": "1",
        "is_sync_es": "0",
        "expect_discount_status": "0",
        "real_discount_status": "0",
        "entrust_status": "1",
        "remark": "",
        "audit_type": "",
        "is_system_generate": "0",
        "is_financing": "0",
        "confirm_status": "0",
        "is_traverse": "0",
        "financing_apply_amount": "0.00",
        "financing_apply_amount_cny": "0.00",
        "financing_apply_amount_usd": "0.00",
        "sys_upttime": "2026-06-10 11:00:53",
        "reverse_status_name": "否",
        "is_delayed_recovery_name": "否",
        "order_finance_arr": [],
        "order_main_bank_arr": [],
        "order_sub": [],
        "order_sub_no": "",
        "container": [
            {
                "order_container_id": "322933109785886720",
                "box_type": "40HQ",
                "box_num": "1",
                "box_no": [
                    "1"
                ],
                "seal_number": [
                    ""
                ],
                "sea_trans_unit_price": 100
            }
        ],
        "service_project": {
            "booking_space": false,
            "customs_clearance": false,
            "manifest": false,
            "insurance": false,
            "trucking": false
        },
        "service_project_amount": {
            "booking_space": false,
            "customs_clearance": false,
            "manifest": false,
            "insurance": false,
            "trucking": false
        },
        "finance_status": true,
        "main_ids_name": "易汇智,易航道",
        "policy_main_arr": [
            {
                "fee_main_id": "31",
                "main_name": "青岛易汇智供应链管理有限公司"
            },
            {
                "fee_main_id": "1",
                "main_name": "青岛易航道物流科技有限公司"
            }
        ],
        "policy_type_name": "结算业务",
        "business_type_name": "海运整箱",
        "cargo_type_name": "普货",
        "period_rule_name": "",
        "trade_term_name": "CIF",
        "carrier_name": "大西洋航运",
        "terms_transport_name": "CY\/CY",
        "terms_payment_name": "T\/T",
        "pay_type_name": "FREIGHT PREPAID",
        "m_delivery_type_name": "正本",
        "supplier": [
            {
                "order_supplier_id": "322933110742188032",
                "order_id": "322933109106409472",
                "isset_supplier": "1",
                "is_primary": "1",
                "supplier_id": "8",
                "supplier_name": "上海华运船务有限公司青岛分公司",
                "settle_object_id": "39",
                "user_id": "16",
                "user_name": "荣洋",
                "service_item": "booking_space",
                "supplier_period": "30",
                "settlement_date": "20",
                "supplier_pay_date": "0",
                "is_manual": "0",
                "sys_upttime": "2026-06-10 11:00:53",
                "supplier_label": "上海华运船务有限公司青岛分公司-订舱",
                "service_item_name": "订舱",
                "isset_fee": false
            }
        ],
        "audit": [],
        "enable": "1",
        "policy_match": "semi",
        "policy_match_name": "手动选择",
        "real_discount_status_name": "—",
        "expect_discount_status_name": "—",
        "expect_policy_status_name": "",
        "policy_status_name": "",
        "subsidy_category_name": "—",
        "expect_subsidy_category_name": "—",
        "real_subsidy_category_name": "—"
    },
    "request_id": "ae2524ebf26e5a6eee07a5c8067c3f32"
}
```