---
id: platform.adaptations.post_save_check
type: endpoints
system: platform
service: platform-service
---

# Save Check

```gimbal:endpoint
review: draft
id: platform.adaptations.post_save_check
system: platform
service: platform-service
name: Save Check
description: |-
  RS4a 保存检查:①目标修订试算（阻断）②引用检查 ③保存方式推荐。

  R14:review_items 非空时提示确认,未确认提交被拒。
binding:
  protocol: http
  method: POST
  path: /api/adaptations/save-check
  timeout_seconds: 30.0
  auth: bearer
  body_type: json
request:
  declarations:
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
