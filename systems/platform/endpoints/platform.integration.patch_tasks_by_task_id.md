---
id: platform.integration.patch_tasks_by_task_id
type: endpoints
system: platform
service: platform-service
---

# Patch Task

```gimbal:endpoint
review: draft
id: platform.integration.patch_tasks_by_task_id
system: platform
service: platform-service
name: Patch Task
description: ''
binding:
  protocol: http
  method: PATCH
  path: /api/integration/tasks/{task_id}
  timeout_seconds: 30.0
  auth: bearer
  body_type: json
request:
  declarations:
  - name: name
    path: $.name
    type: string
    ui_kind: text
    description: ''
    assertable: false
  - name: resultPolicy
    path: $.resultPolicy
    type: string
    ui_kind: text
    description: ''
    assertable: false
  - name: schemeId
    path: $.schemeId
    type: string
    ui_kind: text
    description: ''
    assertable: false
  - name: targetSystem
    path: $.targetSystem
    type: string
    ui_kind: text
    description: ''
    assertable: false
  - name: triggerCron
    path: $.triggerCron
    type: string
    ui_kind: text
    description: ''
    assertable: false
  - name: visibility
    path: $.visibility
    type: string
    ui_kind: text
    description: ''
    assertable: false
responses:
  '200':
    description: Successful Response
    declarations: []
metadata:
  module: integration
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: ''
```
