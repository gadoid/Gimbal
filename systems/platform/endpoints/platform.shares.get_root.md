---
id: platform.shares.get_root
type: endpoints
system: platform
service: platform-service
---

# List Shares

```gimbal:endpoint
review: draft
id: platform.shares.get_root
system: platform
service: platform-service
name: List Shares
description: |-
  引用清单(只返回 ref;副本历史见 activity_events,§9)。
  direction=out = 我分享出去的(属主治理面);in = 共享给我的。
binding:
  protocol: http
  method: GET
  path: /api/shares
  timeout_seconds: 30.0
  auth: bearer
  body_type: none
request:
  declarations: []
responses:
  '200':
    description: Successful Response
    declarations:
    - name: grantedAt
      path: $.grantedAt
      type: string
      ui_kind: text
      description: ''
      assertable: true
    - name: grantedByName
      path: $.grantedByName
      type: string
      ui_kind: text
      description: ''
      required: true
      assertable: true
    - name: granteeName
      path: $.granteeName
      type: string
      ui_kind: text
      description: ''
      required: true
      assertable: true
    - name: granteeUserId
      path: $.granteeUserId
      type: integer
      ui_kind: number
      description: ''
      required: true
      assertable: true
    - name: id
      path: $.id
      type: integer
      ui_kind: number
      description: ''
      required: true
      assertable: true
    - name: memberCount
      path: $.memberCount
      type: integer
      ui_kind: number
      description: ''
      assertable: true
    - name: resourceType
      path: $.resourceType
      type: string
      ui_kind: text
      description: ''
      required: true
      assertable: true
    - name: scenarioId
      path: $.scenarioId
      type: string
      ui_kind: text
      description: ''
      assertable: true
    - name: scenarioName
      path: $.scenarioName
      type: string
      ui_kind: text
      description: ''
      assertable: true
    - name: suiteId
      path: $.suiteId
      type: integer
      ui_kind: number
      description: ''
      assertable: true
    - name: suiteName
      path: $.suiteName
      type: string
      ui_kind: text
      description: ''
      assertable: true
metadata:
  module: shares
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: ''
```
