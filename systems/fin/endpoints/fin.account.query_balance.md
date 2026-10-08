---
id: fin.account.query_balance
type: endpoints
system: fin
service: fin-service
---

# 查询账户余额

```gimbal:endpoint
review: reviewed
id: fin.account.query_balance
system: fin
service: fin-service
name: 查询账户余额
description: fin 账户服务查询指定账户的当前余额
binding:
  protocol: http
  method: GET
  path: /api/v1/fin/account/balance
  timeout_seconds: 5.0
  auth: bearer
responses:
  "200":
    description: 成功
    declarations:
    - name: account_id
      path: $.account_id
      type: string
      required: true
      ui_kind: text
    - name: balance
      path: $.balance
      type: integer
      required: true
      description: 账户余额,单位分
      ui_kind: number
    - name: currency
      path: $.currency
      type: string
      default: CNY
      ui_kind: text
    - name: as_of
      path: $.as_of
      type: string
      required: true
      ui_kind: text
metadata:
  module: fin
  tags:
  - fin
  owner: fin-team
```
