---
id: fin.order.generate_order_sub
type: endpoints
system: fin
service: fin-service
---

# 生成子订单

```gimbal:endpoint
review: reviewed
id: fin.order.generate_order_sub
system: fin
service: fin-service
name: 生成子订单
description: 生成子订单
binding:
  protocol: http
  method: POST
  path: /api/order/order/generateOrderSub
  auth: bearer
request:
  declarations:
  - name: order_id
    path: $.order_id
    type: string
    required: true
    example: ''
    ui_kind: text
responses:
  '200':
    description: 成功
metadata:
  module: fin
  tags:
  - fin
  owner: fin-team
```
