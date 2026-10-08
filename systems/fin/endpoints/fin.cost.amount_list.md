---
id: fin.cost.amount_list
type: endpoints
system: fin
service: fin-service
---

# 费用字典列表(amountCostList)

```gimbal:endpoint
review: reviewed
id: fin.cost.amount_list
system: fin
service: fin-service
name: 费用字典列表(amountCostList)
description: 费用名称/费用ID 字典;组合期取数源 cost_list 视图挂此
binding:
  protocol: http
  method: GET
  path: /api/home/cost/amountCostList
  auth: bearer
  body_type: none
request: {}
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
query_views:
- name: cost_list
  items: $.data[*]
  label: cost_name
metadata:
  module: fin
  tags:
  - fin
  owner: fin-team
```
