---
id: platform.adaptations.post_submit
type: endpoints
system: platform
service: platform-service
---

# Submit Adaptation

```gimbal:endpoint
review: draft
id: platform.adaptations.post_submit
system: platform
service: platform-service
name: Submit Adaptation
description: |-
  RS4a 提交:按场景单事务(快照 → 应用 op → meta.plate → 审计/通知)。

  R22:编辑权随场景(_ensure_edit_rights,admin 或 owner)。
binding:
  protocol: http
  method: POST
  path: /api/adaptations/submit
  timeout_seconds: 30.0
  auth: bearer
  body_type: json
request:
  declarations:
  - name: ops
    path: $.ops
    type: array
    ui_kind: json
    description: ''
    assertable: false
  - name: reviewConfirmed
    path: $.reviewConfirmed
    type: boolean
    ui_kind: boolean
    description: ''
    assertable: false
  - name: saveMode
    path: $.saveMode
    type: string
    ui_kind: text
    description: ''
    required: true
    assertable: false
  - name: scenarioId
    path: $.scenarioId
    type: string
    ui_kind: text
    description: ''
    required: true
    assertable: false
  - name: system
    path: $.system
    type: string
    ui_kind: text
    description: ''
    assertable: false
  - name: targetRevision
    path: $.targetRevision
    type: string
    ui_kind: text
    description: ''
    required: true
    assertable: false
responses:
  '200':
    description: Successful Response
    declarations: []
metadata:
  module: adaptations
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: ''
```
