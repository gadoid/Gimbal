---
id: fin.order_entrust.order_add
type: endpoints
system: fin
service: fin-service
---

# 委托订舱下单

```gimbal:endpoint
review: reviewed
id: fin.order_entrust.order_add
system: fin
service: fin-service
name: 委托订舱下单
description: 委托订舱下单
binding:
  protocol: http
  method: POST
  path: /api/order/orderEntrust/orderAdd
request:
  declarations:
  - name: bl_no
    path: $.bl_no
    type: string
    default: Codfish_TEST_001
    example: Codfish_TEST_001
    ui_kind: text
    value_source:
      view: pending_orders
      column: bl_no
  - name: track_bl_no
    path: $.track_bl_no
    type: string
    default: Codfish_TEST_001
    example: Codfish_TEST_001
    ui_kind: text
  - name: action
    path: $.action
    type: string
    default: check
    example: submit
    description: check[校验]/submit[提交]
    enum:
    - check
    - submit
    ui_kind: text
  - name: client_expand_name
    path: $.client_expand_name
    type: string
    state: carry
    value_source:
      view: customer_part
      column: handover_form.client_expand_name
  - name: client_expand_id
    path: $.client_expand_id
    type: string
    state: carry
    value_source:
      view: customer_part
      column: handover_form.client_expand_id
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
  - name: receive_time_limit
    path: $.receive_time_limit
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
  - name: product_id
    path: $.product_id
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
    type: string
  - name: sea_trans_currency
    path: $.sea_trans_currency
    type: string
    state: carry
  - name: container
    path: $.container
    type: array
    state: carry
    children:
    - name: box_type
      path: $.container.box_type
      type: string
      state: carry
    - name: box_num
      path: $.container.box_num
      type: string
      state: carry
    - name: box_no
      path: $.container.box_no
      type: array
      state: carry
    - name: seal_number
      path: $.container.seal_number
      type: array
      state: carry
    - name: sea_trans_unit_price
      path: $.container.sea_trans_unit_price
      type: string
      state: carry
  - name: message_board
    path: $.message_board
    type: array
    state: carry
  - name: customer_file_list
    path: $.customer_file_list
    type: array
    state: carry
  - name: supplier
    path: $.supplier
    type: array
    state: carry
    children:
    - name: is_manual
      path: $.supplier.is_manual
      type: string
      state: carry
    - name: is_primary
      path: $.supplier.is_primary
      type: string
      state: carry
    - name: isset_fee
      path: $.supplier.isset_fee
      type: string
      state: carry
    - name: isset_supplier
      path: $.supplier.isset_supplier
      type: string
      state: carry
    - name: order_id
      path: $.supplier.order_id
      type: string
      state: carry
    - name: order_supplier_id
      path: $.supplier.order_supplier_id
      type: string
      state: carry
    - name: service_item
      path: $.supplier.service_item
      type: string
      state: carry
    - name: service_item_name
      path: $.supplier.service_item_name
      type: string
      state: carry
    - name: settle_object_id
      path: $.supplier.settle_object_id
      type: string
      state: carry
    - name: settlement_date
      path: $.supplier.settlement_date
      type: string
      state: carry
    - name: pay_time_limit
      path: $.supplier.pay_time_limit
      type: string
      state: carry
    - name: supplier_id
      path: $.supplier.supplier_id
      type: string
      state: carry
    - name: supplier_name
      path: $.supplier.supplier_name
      type: string
      state: carry
    - name: supplier_pay_date
      path: $.supplier.supplier_pay_date
      type: string
      state: carry
    - name: supplier_period
      path: $.supplier.supplier_period
      type: string
      state: carry
    - name: user_id
      path: $.supplier.user_id
      type: string
      state: carry
    - name: user_name
      path: $.supplier.user_name
      type: string
      state: carry
    - name: settle_type
      path: $.supplier.settle_type
      type: string
      state: carry
    - name: supplier_name_clean
      path: $.supplier.supplier_name_clean
      type: string
      state: carry
    - name: supplier_name_en
      path: $.supplier.supplier_name_en
      type: string
      state: carry
    - name: tax_number
      path: $.supplier.tax_number
      type: string
      state: carry
    - name: settle_object
      path: $.supplier.settle_object
      type: string
      state: carry
    - name: settle_object_clean
      path: $.supplier.settle_object_clean
      type: string
      state: carry
    - name: settle_type_name
      path: $.supplier.settle_type_name
      type: string
      state: carry
  - name: remark
    path: $.remark
    type: string
    state: carry
  - name: payment_type_name
    path: $.payment_type_name
    type: string
    state: carry
  - name: payment_type
    path: $.payment_type
    type: string
    state: carry
  - name: policy_type_name
    path: $.policy_type_name
    type: string
    state: carry
  - name: main_ids
    path: $.main_ids
    type: string
    state: carry
  - name: pot_cn
    path: $.pot_cn
    type: string
    state: carry
  - name: pot_port_name
    path: $.pot_port_name
    type: string
    state: carry
  - name: pol_cn
    path: $.pol_cn
    type: string
    state: carry
  - name: pol_port_name
    path: $.pol_port_name
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
  - name: del_cn
    path: $.del_cn
    type: string
    state: carry
  - name: del_port_name
    path: $.del_port_name
    type: string
    state: carry
  - name: pod_cn
    path: $.pod_cn
    type: string
    state: carry
  - name: pod_port_name
    path: $.pod_port_name
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
  - name: entrust_status
    path: $.entrust_status
    type: integer
    default: ''
    example: "1"
    description: 1是检查，2是分发
    ui_kind: text
  - name: order_file
    path: $.order_file
    type: array
    state: carry
  - name: create_time
    path: $.create_time
    type: string
  - name: update_time
    path: $.update_time
    type: string
responses:
  "200": {}
metadata:
  module: fin
  tags:
  - fin
  owner: fin-team
```
