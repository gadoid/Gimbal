---
id: platform.shares.post_by_share_id_fork
type: endpoints
system: platform
service: platform-service
---

# Fork Share

```gimbal:endpoint
review: reviewed
id: platform.shares.post_by_share_id_fork
system: platform
service: platform-service
name: Fork Share
description: 转为副本(§7.7):被分享人把引用转成自己的副本,原引用保留。
binding:
  protocol: http
  method: POST
  path: /api/shares/{share_id}/fork
  auth: bearer
  body_type: none
request: {}
responses:
  "201":
    description: Successful Response
    declarations:
    - name: memberCount
      path: $.memberCount
      type: integer
      ui_kind: number
      assertable: true
    - name: mode
      path: $.mode
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: scenarioId
      path: $.scenarioId
      type: string
      ui_kind: text
      assertable: true
    - name: suiteId
      path: $.suiteId
      type: integer
      ui_kind: number
      assertable: true
    - name: suiteName
      path: $.suiteName
      type: string
      ui_kind: text
      assertable: true
  "200":
    description: 成功
    declarations:
    - name: memberCount
      path: $.memberCount
      type: integer
      ui_kind: number
      assertable: true
    - name: mode
      path: $.mode
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: scenarioId
      path: $.scenarioId
      type: string
      ui_kind: text
      assertable: true
    - name: suiteId
      path: $.suiteId
      type: integer
      ui_kind: number
      assertable: true
    - name: suiteName
      path: $.suiteName
      type: string
      ui_kind: text
      assertable: true
metadata:
  module: shares
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
