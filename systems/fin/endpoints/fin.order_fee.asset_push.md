---
id: fin.order_fee.asset_push
type: endpoints
system: fin
service: fin-service
---

# 费用资产推送

```gimbal:endpoint
review: reviewed
id: fin.order_fee.asset_push
system: fin
service: fin-service
name: 费用资产推送
description: "由 Scenario_Test_14 提取: 费用资产推送"
binding:
  protocol: http
  method: POST
  path: /api/order/orderFee/assetPush
  auth: bearer
request:
  declarations:
  - name: action
    path: $.action
    type: string
    required: true
    example: check
    enum:
    - check
    - submit
    ui_kind: text
  - name: order_id
    path: $.order_id
    type: string
    required: true
    example: ''
    ui_kind: text
  - name: audit_msg
    path: $.audit_msg
    type: object
    required: true
    example:
      title: 资产推送申请
      code: ''
      msgs:
      - 资产推送申请
    ui_kind: json
  - name: select_node_user
    path: $.select_node_user
    type: array
    required: true
    example:
    - node_sort: "0"
      user_id: "828"
    ui_kind: json
responses:
  "200":
    description: 成功
metadata:
  module: fin
  tags:
  - fin
  owner: fin-team
```
