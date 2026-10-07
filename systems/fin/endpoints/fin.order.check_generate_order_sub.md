---
id: fin.order.check_generate_order_sub
type: endpoints
system: fin
service: fin-service
---

# 校验主订单拆分子订单

```gimbal:endpoint
review: reviewed
id: fin.order.check_generate_order_sub
system: fin
service: fin-service
name: 校验主订单拆分子订单
description: 校验主订单拆分子订单
binding:
  protocol: http
  method: POST
  path: /api/order/order/checkGenerateOrderSub
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
