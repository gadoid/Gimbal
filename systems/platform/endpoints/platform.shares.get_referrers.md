---
id: platform.shares.get_referrers
type: endpoints
system: platform
service: platform-service
---

# Scenario Referrers

```gimbal:endpoint
review: draft
id: platform.shares.get_referrers
system: platform
service: platform-service
name: Scenario Referrers
description: |-
  场景的全部引用人(§7.11 防误伤名单,属主治理面):直接引用 +
  经由所属 Suite 的间接引用(§7.6 判定式,同一引用人合并成一行)。

  保存提示与「已引用分享」徽标的数据源 —— 此前两者只查直接引用,
  场景仅因所在 Suite 被分享而间接被引用时名单落空(重构方案补遗)。
binding:
  protocol: http
  method: GET
  path: /api/shares/referrers
  timeout_seconds: 30.0
  auth: bearer
  body_type: none
request:
  declarations: []
responses:
  '200':
    description: Successful Response
    declarations:
    - name: items
      path: $.items
      type: array
      ui_kind: json
      description: ''
      required: true
      assertable: true
      children:
      - name: direct
        path: $.items.direct
        type: boolean
        ui_kind: boolean
        description: ''
        required: true
        assertable: true
      - name: granteeName
        path: $.items.granteeName
        type: string
        ui_kind: text
        description: ''
        required: true
        assertable: true
      - name: granteeUserId
        path: $.items.granteeUserId
        type: integer
        ui_kind: number
        description: ''
        required: true
        assertable: true
      - name: viaSuites
        path: $.items.viaSuites
        type: array
        ui_kind: json
        description: ''
        assertable: true
        children:
        - name: suiteId
          path: $.items.viaSuites.suiteId
          type: integer
          ui_kind: number
          description: ''
          required: true
          assertable: true
        - name: suiteName
          path: $.items.viaSuites.suiteName
          type: string
          ui_kind: text
          description: ''
          required: true
          assertable: true
metadata:
  module: shares
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: ''
```
