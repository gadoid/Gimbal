---
id: platform.adaptations.post_save_check
type: endpoints
system: platform
service: platform-service
---

# Save Check

```gimbal:endpoint
review: reviewed
id: platform.adaptations.post_save_check
system: platform
service: platform-service
name: Save Check
description: "RS4a 保存检查:①目标修订试算（阻断）②引用检查 ③保存方式推荐。\n\nR14:review_items 非空时提示确认,未确认提交被拒。"
binding:
  protocol: http
  method: POST
  path: /api/adaptations/save-check
  auth: bearer
request:
  declarations:
  - name: scenarioId
    path: $.scenarioId
    type: string
    required: true
    ui_kind: text
  - name: system
    path: $.system
    type: string
    ui_kind: text
  - name: targetRevision
    path: $.targetRevision
    type: string
    required: true
    ui_kind: text
responses:
  "200":
    description: Successful Response
metadata:
  module: adaptations
  tags:
  - platform
  owner: gimbal-bootstrap
```
