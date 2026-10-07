---
id: fin.order.order_notice
type: endpoints
system: fin
service: fin-service
---

# 应收核销通知

```gimbal:endpoint
review: reviewed
id: fin.order.order_notice
system: fin
service: fin-service
name: 应收核销通知
description: '由 Scenario_Test_14 提取: 应收核销通知'
binding:
  protocol: http
  method: POST
  path: /api/order/order/orderNotice
  auth: bearer
request:
  declarations:
  - name: order_id
    path: $.order_id
    type: string
    required: true
    example: ''
    ui_kind: text
  - name: action
    path: $.action
    type: string
    required: true
    example: check
    enum:
    - check
    - submit
    ui_kind: text
  - name: finance_ids
    path: $.finance_ids
    type: array
    required: true
    example:
    - ${var.finance_id_0}
    - ${var.finance_id_1}
    ui_kind: json
  - name: bank_ids
    path: $.bank_ids
    type: array
    required: true
    example:
    - ${var.bank_id_0}
    - ${var.bank_id_1}
    ui_kind: json
responses:
  '200':
    description: 成功
metadata:
  module: fin
  tags:
  - fin
  owner: fin-team
```
