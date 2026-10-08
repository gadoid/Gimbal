---
id: fin.order.order_detail
type: endpoints
system: fin
service: fin-service
---

# 订单-查询订单详情

```gimbal:endpoint
review: reviewed
id: fin.order.order_detail
system: fin
service: fin-service
name: 订单-查询订单详情
binding:
  protocol: http
  method: POST
  path: /api/order/order/orderDetail
request:
  declarations:
  - name: order_id
    path: $.order_id
    type: string
    example: "353724757260108800"
    description: 订单id
    ui_kind: text
responses:
  "200":
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
    - name: order_id
      path: $.data.order_id
      type: string
      example: "353724757260108800"
      ui_kind: text
      assertable: true
    - name: order_no
      path: $.data.order_no
      type: string
      example: YWDD20260903110794
      ui_kind: text
      assertable: true
    - name: customer_id
      path: $.data.customer_id
      type: string
      example: "335247043402399744"
      ui_kind: text
      assertable: true
    - name: supplier
      path: $.data.supplier
      type: array
      assertable: true
      children:
      - name: order_supplier_id
        path: $.data.supplier.order_supplier_id
        type: string
        example: "354632242825266176"
        ui_kind: text
        assertable: true
      - name: order_id
        path: $.data.supplier.order_id
        type: string
        example: "354632241306928128"
        ui_kind: text
        assertable: true
      - name: isset_supplier
        path: $.data.supplier.isset_supplier
        type: string
        example: "1"
        ui_kind: text
        assertable: true
      - name: is_primary
        path: $.data.supplier.is_primary
        type: string
        example: "1"
        ui_kind: text
        assertable: true
      - name: supplier_id
        path: $.data.supplier.supplier_id
        type: string
        example: "1"
        ui_kind: text
        assertable: true
      - name: supplier_name
        path: $.data.supplier.supplier_name
        type: string
        example: 山东旭禾国际贸易有限公司
        ui_kind: text
        assertable: true
      - name: settle_object_id
        path: $.data.supplier.settle_object_id
        type: string
        example: "15"
        ui_kind: text
        assertable: true
      - name: user_id
        path: $.data.supplier.user_id
        type: string
        example: "41"
        ui_kind: text
        assertable: true
      - name: user_name
        path: $.data.supplier.user_name
        type: string
        example: 孙奉盛
        ui_kind: text
        assertable: true
      - name: service_item
        path: $.data.supplier.service_item
        type: string
        example: booking_space
        ui_kind: text
        assertable: true
      - name: supplier_period
        path: $.data.supplier.supplier_period
        type: string
        example: "30"
        ui_kind: text
        assertable: true
      - name: settlement_date
        path: $.data.supplier.settlement_date
        type: string
        example: "20"
        ui_kind: text
        assertable: true
      - name: supplier_pay_date
        path: $.data.supplier.supplier_pay_date
        type: string
        example: "1789833600"
        ui_kind: text
        assertable: true
      - name: is_manual
        path: $.data.supplier.is_manual
        type: string
        example: "0"
        ui_kind: text
        assertable: true
      - name: sys_upttime
        path: $.data.supplier.sys_upttime
        type: string
        example: "2026-09-05 22:22:00"
        ui_kind: text
        assertable: true
      - name: pay_time_limit
        path: $.data.supplier.pay_time_limit
        type: string
        example: "10"
        ui_kind: text
        assertable: true
      - name: supplier_pay_date_desc
        path: $.data.supplier.supplier_pay_date_desc
        type: string
        example: 月结规则
        ui_kind: text
        assertable: true
      - name: settle_type
        path: $.data.supplier.settle_type
        type: string
        example: "1"
        ui_kind: text
        assertable: true
      - name: supplier_label
        path: $.data.supplier.supplier_label
        type: string
        example: 山东旭禾国际贸易有限公司-订舱
        ui_kind: text
        assertable: true
      - name: settle_type_name
        path: $.data.supplier.settle_type_name
        type: string
        example: 月结
        ui_kind: text
        assertable: true
      - name: service_item_name
        path: $.data.supplier.service_item_name
        type: string
        example: 订舱
        ui_kind: text
        assertable: true
      - name: isset_fee
        path: $.data.supplier.isset_fee
        type: boolean
        example: false
        ui_kind: boolean
        assertable: true
    - name: order_container_id
      path: $.data.container[0].order_container_id
      type: string
      example: "354178949166662656"
      ui_kind: text
      assertable: true
metadata:
  module: fin
  tags:
  - fin
  owner: fin-team
```
