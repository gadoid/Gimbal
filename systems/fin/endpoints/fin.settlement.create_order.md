---
id: fin.settlement.create_order
type: endpoints
system: fin
service: fin-service
---

# 创建结算单

```gimbal:endpoint
review: reviewed
id: fin.settlement.create_order
system: fin
service: fin-service
name: 创建结算单
description: fin 结算服务创建结算订单的核心接口
binding:
  protocol: http
  method: POST
  path: /api/v1/fin/settlement/orders
  timeout_seconds: 10.0
  auth: bearer
request:
  declarations:
  - name: order_id
    path: $.order_id
    type: string
    required: true
    description: 业务订单号
    ui_kind: text
  - name: amount
    path: $.amount
    type: integer
    required: true
    description: 结算金额,单位分
    ui_kind: number
  - name: currency
    path: $.currency
    type: string
    default: CNY
    description: 币种
    ui_kind: text
  - name: remark
    path: $.remark
    type: string
    state: carry
    description: 订单备注(carry 传递字段)
    ui_kind: text
responses:
  "200":
    description: 成功
    declarations:
    - name: order_id
      path: $.order_id
      type: string
      required: true
      ui_kind: text
    - name: status
      path: $.status
      type: string
      required: true
      ui_kind: text
    - name: created_at
      path: $.created_at
      type: string
      required: true
      ui_kind: text
metadata:
  module: fin
  tags:
  - fin
  owner: fin-team
```
