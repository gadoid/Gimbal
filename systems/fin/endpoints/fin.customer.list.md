---
id: fin.customer.list
type: endpoints
system: fin
service: fin-service
---

# 客户列表(customerList)

```gimbal:endpoint
review: reviewed
id: fin.customer.list
system: fin
service: fin-service
name: 客户列表(customerList)
description: 客户公司列表;组合期取数源 customer_list 视图挂此(级联链 ①,§13.1)
binding:
  protocol: http
  method: POST
  path: /api/customer/customer/customerList
  auth: bearer
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
- name: customer_list
  items: $.data[*]
  label: customer_name
metadata:
  module: fin
  tags:
  - fin
  owner: fin-team
  query_safe: true
```
