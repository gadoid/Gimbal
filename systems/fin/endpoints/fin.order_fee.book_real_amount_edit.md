---
id: fin.order_fee.book_real_amount_edit
type: endpoints
system: fin
service: fin-service
---

# 订舱实收实付金额配置

```gimbal:endpoint
review: reviewed
id: fin.order_fee.book_real_amount_edit
system: fin
service: fin-service
name: 订舱实收实付金额配置
description: '由 Scenario_Test_14 提取: 订舱实收实付金额配置'
binding:
  protocol: http
  method: POST
  path: /api/order/orderFee/bookRealAmountEdit
  auth: bearer
request:
  declarations:
  - name: action
    path: $.action
    type: string
    example: check
    enum:
    - check
    - submit
    ui_kind: text
  - name: order_id
    path: $.order_id
    type: string
    example: '355255812731438080'
    ui_kind: text
  - name: discount_ratio
    path: $.discount_ratio
    type: string
    example: ''
    ui_kind: text
  - name: service_project
    path: $.service_project
    type: string
    example: booking_space
    ui_kind: text
  - name: import_status
    path: $.import_status
    type: integer
    example: 0
    ui_kind: number
  - name: to_customer
    path: $.to_customer
    type: object
    children:
    - name: put_amount
      path: $.to_customer.put_amount
      type: object
      children:
      - name: standard_list
        path: $.to_customer.put_amount.standard_list
        type: array
        children:
        - name: order_fee_real_id
          path: $.to_customer.put_amount.standard_list.order_fee_real_id
          type: string
          ui_kind: text
        - name: fee_type
          path: $.to_customer.put_amount.standard_list.fee_type
          type: integer
          ui_kind: number
        - name: policy_sub_id
          path: $.to_customer.put_amount.standard_list.policy_sub_id
          type: string
          ui_kind: text
        - name: service_project
          path: $.to_customer.put_amount.standard_list.service_project
          type: string
          ui_kind: text
        - name: cost_id
          path: $.to_customer.put_amount.standard_list.cost_id
          type: string
          ui_kind: text
          value_source:
            view: cost_list
            column: cost_id
            group: cost_list#to_customer
        - name: settle_object_id
          path: $.to_customer.put_amount.standard_list.settle_object_id
          type: string
          ui_kind: text
        - name: subsidy_category
          path: $.to_customer.put_amount.standard_list.subsidy_category
          type: string
          ui_kind: text
        - name: subsidy_id
          path: $.to_customer.put_amount.standard_list.subsidy_id
          type: string
          ui_kind: text
        - name: currency
          path: $.to_customer.put_amount.standard_list.currency
          type: string
          ui_kind: text
        - name: unit_price
          path: $.to_customer.put_amount.standard_list.unit_price
          type: string
          ui_kind: text
        - name: unit
          path: $.to_customer.put_amount.standard_list.unit
          type: string
          ui_kind: text
        - name: specs
          path: $.to_customer.put_amount.standard_list.specs
          type: string
          ui_kind: text
        - name: num
          path: $.to_customer.put_amount.standard_list.num
          type: string
          ui_kind: text
        - name: remark
          path: $.to_customer.put_amount.standard_list.remark
          type: string
          ui_kind: text
        - name: discount_ratio
          path: $.to_customer.put_amount.standard_list.discount_ratio
          type: integer
          ui_kind: number
        - name: discount_amount
          path: $.to_customer.put_amount.standard_list.discount_amount
          type: string
          ui_kind: text
        - name: discount_status
          path: $.to_customer.put_amount.standard_list.discount_status
          type: string
          ui_kind: text
        - name: policy_sub_status_name
          path: $.to_customer.put_amount.standard_list.policy_sub_status_name
          type: string
          ui_kind: text
        - name: pay_sync_status
          path: $.to_customer.put_amount.standard_list.pay_sync_status
          type: integer
          ui_kind: number
        - name: unique_id
          path: $.to_customer.put_amount.standard_list.unique_id
          type: string
          ui_kind: text
        - name: init_main_name
          path: $.to_customer.put_amount.standard_list.init_main_name
          type: string
          ui_kind: text
        - name: main_name
          path: $.to_customer.put_amount.standard_list.main_name
          type: string
          ui_kind: text
        - name: rowIndex
          path: $.to_customer.put_amount.standard_list.rowIndex
          type: integer
          ui_kind: number
  - name: to_supplier
    path: $.to_supplier
    type: object
    children:
    - name: pay_amount
      path: $.to_supplier.pay_amount
      type: object
      children:
      - name: standard_list
        path: $.to_supplier.pay_amount.standard_list
        type: array
        children:
        - name: order_fee_real_id
          path: $.to_supplier.pay_amount.standard_list.order_fee_real_id
          type: string
          ui_kind: text
        - name: fee_type
          path: $.to_supplier.pay_amount.standard_list.fee_type
          type: integer
          ui_kind: number
        - name: policy_sub_id
          path: $.to_supplier.pay_amount.standard_list.policy_sub_id
          type: string
          ui_kind: text
        - name: service_project
          path: $.to_supplier.pay_amount.standard_list.service_project
          type: string
          ui_kind: text
        - name: cost_id
          path: $.to_supplier.pay_amount.standard_list.cost_id
          type: string
          ui_kind: text
          value_source:
            view: cost_list
            column: cost_id
            group: cost_list#to_supplier
        - name: settle_object_id
          path: $.to_supplier.pay_amount.standard_list.settle_object_id
          type: string
          ui_kind: text
        - name: subsidy_category
          path: $.to_supplier.pay_amount.standard_list.subsidy_category
          type: string
          ui_kind: text
        - name: currency
          path: $.to_supplier.pay_amount.standard_list.currency
          type: string
          ui_kind: text
        - name: unit_price
          path: $.to_supplier.pay_amount.standard_list.unit_price
          type: string
          ui_kind: text
        - name: unit
          path: $.to_supplier.pay_amount.standard_list.unit
          type: string
          ui_kind: text
        - name: specs
          path: $.to_supplier.pay_amount.standard_list.specs
          type: string
          ui_kind: text
        - name: num
          path: $.to_supplier.pay_amount.standard_list.num
          type: string
          ui_kind: text
        - name: remark
          path: $.to_supplier.pay_amount.standard_list.remark
          type: string
          ui_kind: text
        - name: discount_ratio
          path: $.to_supplier.pay_amount.standard_list.discount_ratio
          type: integer
          ui_kind: number
        - name: discount_amount
          path: $.to_supplier.pay_amount.standard_list.discount_amount
          type: string
          ui_kind: text
        - name: discount_status
          path: $.to_supplier.pay_amount.standard_list.discount_status
          type: string
          ui_kind: text
        - name: policy_sub_status_name
          path: $.to_supplier.pay_amount.standard_list.policy_sub_status_name
          type: string
          ui_kind: text
        - name: pay_sync_status
          path: $.to_supplier.pay_amount.standard_list.pay_sync_status
          type: integer
          ui_kind: number
        - name: unique_id
          path: $.to_supplier.pay_amount.standard_list.unique_id
          type: string
          ui_kind: text
        - name: init_main_name
          path: $.to_supplier.pay_amount.standard_list.init_main_name
          type: string
          ui_kind: text
        - name: main_name
          path: $.to_supplier.pay_amount.standard_list.main_name
          type: string
          ui_kind: text
        - name: rowIndex
          path: $.to_supplier.pay_amount.standard_list.rowIndex
          type: integer
          ui_kind: number
responses:
  '200':
    description: 成功
metadata:
  module: fin
  tags:
  - fin
  owner: fin-team
```
