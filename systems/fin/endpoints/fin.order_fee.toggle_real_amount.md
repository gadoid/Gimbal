---
id: fin.order_fee.toggle_real_amount
type: endpoints
system: fin
service: fin-service
---

# 切换订单实收实付金额模式

```gimbal:endpoint
review: reviewed
id: fin.order_fee.toggle_real_amount
system: fin
service: fin-service
name: 切换订单实收实付金额模式
description: "由 Scenario_Test_14 提取: 切换订单实收实付金额模式"
binding:
  protocol: http
  method: POST
  path: /api/order/orderFee/toggleRealAmount
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
  "200":
    description: 成功
    declarations:
    - name: order_id
      path: $.data.amount_summary.order_id
      type: string
      assertable: true
    - name: order_fee_real_id
      path: $.data.to_customer[0].put_amount.standard_list[0].order_fee_real_id
      type: string
      assertable: true
    - name: order_sub_no
      path: $.data.to_customer[0].order_sub_no
      type: string
      assertable: true
metadata:
  module: fin
  tags:
  - fin
  owner: fin-team
```
