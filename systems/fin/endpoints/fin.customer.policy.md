---
id: fin.customer.policy
type: endpoints
system: fin
service: fin-service
---

# 客户策略列表(getCustomerPolicy)

```gimbal:endpoint
review: reviewed
id: fin.customer.policy
system: fin
service: fin-service
name: 客户策略列表(getCustomerPolicy)
description: 客户策略列表;组合期取数源 customer_policy 视图挂此(级联链 ③,§13.1)
binding:
  protocol: http
  method: POST
  path: /api/Customer/Policy/getCustomerPolicy
  auth: bearer
request:
  declarations:
  - name: customer_id
    path: $.customer_id
    type: string
    required: true
    description: 客户ID(点击期参数面供给,§13.2)
    ui_kind: text
  - name: status
    path: $.status
    type: string
    required: true
    description: 策略状态(视图静态预设 status=2,§13.1)
    ui_kind: text
responses:
  '200':
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
- name: customer_policy
  params:
    status: '2'
  query_params:
  - customer_id
  items: $.data[*]
  label: policy_name
metadata:
  module: fin
  tags:
  - fin
  owner: fin-team
  query_safe: true
```
