---
id: fin.order.order_page
type: endpoints
system: fin
service: fin-service
---

# 分页查询委托订单

```gimbal:endpoint
review: reviewed
id: fin.order.order_page
system: fin
service: fin-service
name: 分页查询委托订单
description: "由 Scenario_test_14 提取: 分页查询委托订单"
binding:
  protocol: http
  method: POST
  path: /api/order/order/orderPage
  auth: bearer
request:
  declarations:
  - name: bl_no
    path: $.bl_no
    type: string
    required: true
    example: ''
    ui_kind: text
  - name: order_no
    path: $.order_no
    type: string
    required: true
    example: ''
    ui_kind: text
  - name: page_no
    path: $.page_no
    type: integer
    required: true
    example: 1
    ui_kind: number
  - name: page_size
    path: $.page_size
    type: integer
    required: true
    example: 20
    ui_kind: number
  - name: sort_field
    path: $.sort_field
    type: string
    required: true
    example: update_time
    ui_kind: text
  - name: sort_order
    path: $.sort_order
    type: string
    required: true
    example: desc
    enum:
    - asc
    - desc
    ui_kind: text
  - name: params
    path: $.params
    type: object
    required: true
    example: {}
    ui_kind: json
responses:
  "200":
    description: 成功
    declarations:
    - name: code
      path: $.code
      type: number
      description: 业务状态码(200=成功)
      ui_kind: number
      assertable: true
    - name: msg
      path: $.msg
      type: string
      description: 业务提示信息
      ui_kind: text
      assertable: true
    - name: request_id
      path: $.request_id
      type: string
      description: 请求追踪ID
      ui_kind: text
      assertable: true
    - name: total
      path: $.data.total
      type: number
      description: 命中总条数(分页)
      ui_kind: number
      assertable: true
    - name: order_id
      path: $.data.data[0].order_id
      type: string
      description: 订单ID
      ui_kind: text
      assertable: true
    - name: order_no
      path: $.data.data[0].order_no
      type: string
      description: 业务订单号(如 YWDD20260901110701)
      ui_kind: text
      assertable: true
    - name: order_sub_no
      path: $.data.data[0].order_sub_no
      type: string
      description: 子订单号
      ui_kind: text
      assertable: true
    - name: business_no
      path: $.data.data[0].business_no
      type: string
      description: 业务编号
      ui_kind: text
      assertable: true
    - name: copy_order_id
      path: $.data.data[0].copy_order_id
      type: string
      description: 复制来源订单ID(0=非复制)
      ui_kind: text
      assertable: true
    - name: change_type
      path: $.data.data[0].change_type
      type: string
      description: 变更类型(0=无)
      ui_kind: text
      assertable: true
    - name: business_main_id
      path: $.data.data[0].business_main_id
      type: string
      description: 业务主体ID
      ui_kind: text
      assertable: true
    - name: business_main_name
      path: $.data.data[0].business_main_name
      type: string
      description: 业务主体名称
      ui_kind: text
      assertable: true
    - name: main_ids
      path: $.data.data[0].main_ids
      type: string
      description: 主体ID列表(逗号分隔)
      ui_kind: text
      assertable: true
    - name: main_sort
      path: $.data.data[0].main_sort
      type: string
      description: 主体简称拼接(如 易航道,易汇联)
      ui_kind: text
      assertable: true
    - name: customer_order_sn
      path: $.data.data[0].customer_order_sn
      type: string
      description: 客户单号
      ui_kind: text
      assertable: true
    - name: etd
      path: $.data.data[0].etd
      type: string
      description: 预计离港时间(秒级时间戳字符串)
      ui_kind: text
      assertable: true
    - name: atd
      path: $.data.data[0].atd
      type: string
      description: 实际离港时间(秒级时间戳字符串)
      ui_kind: text
      assertable: true
    - name: bl_no
      path: $.data.data[0].bl_no
      type: string
      description: 提单号
      ui_kind: text
      assertable: true
    - name: track_bl_no
      path: $.data.data[0].track_bl_no
      type: string
      description: 跟踪提单号
      ui_kind: text
      assertable: true
    - name: service_items
      path: $.data.data[0].service_items
      type: string
      description: 服务项
      ui_kind: text
      assertable: true
    - name: track_atd
      path: $.data.data[0].track_atd
      type: string
      ui_kind: text
      assertable: true
    - name: track_eta
      path: $.data.data[0].track_eta
      type: string
      ui_kind: text
      assertable: true
    - name: track_ata
      path: $.data.data[0].track_ata
      type: string
      ui_kind: text
      assertable: true
metadata:
  module: fin
  tags:
  - fin
  owner: fin-team
```
