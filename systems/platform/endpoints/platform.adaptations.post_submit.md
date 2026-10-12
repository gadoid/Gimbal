---
id: platform.adaptations.post_submit
type: endpoints
system: platform
service: platform-service
---

# Submit Adaptation

```gimbal:endpoint
id: platform.adaptations.post_submit
system: platform
service: platform-service
name: Submit Adaptation
description: "RS4a 提交:按场景单事务(快照 → 应用 op → meta.plate → 审计/通知)。\n\nR22:编辑权随场景(_ensure_edit_rights,admin 或 owner)。"
binding:
  protocol: http
  method: POST
  path: /api/adaptations/submit
  auth: bearer
request:
  declarations:
  - name: ops
    path: $.ops
    type: array
    ui_kind: json
  - name: reviewConfirmed
    path: $.reviewConfirmed
    type: boolean
    ui_kind: boolean
  - name: saveMode
    path: $.saveMode
    type: string
    required: true
    ui_kind: text
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
