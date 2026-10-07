---
id: fin.customer.part
type: endpoints
system: fin
service: fin-service
---

# 客户详情(customerPart)

```gimbal:endpoint
review: reviewed
id: fin.customer.part
system: fin
service: fin-service
name: 客户详情(customerPart)
description: 客户单对象详情;组合期取数源 customer_part 视图挂此(级联链 ②,§13.1/§13.4)
binding:
  protocol: http
  method: POST
  path: /api/customer/customer/customerPart
  auth: bearer
request:
  declarations:
  - name: customer_id
    path: $.customer_id
    type: string
    required: true
    description: 客户ID(点击期参数面供给,§13.2)
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
- name: customer_part
  query_params:
  - customer_id
  items: $.data
  label: customer_service.user_name
metadata:
  module: fin
  tags:
  - fin
  owner: fin-team
  query_safe: true
```
