---
id: platform.integration.patch_tasks_by_task_id
type: endpoints
system: platform
service: platform-service
---

# Patch Task

```gimbal:endpoint
id: platform.integration.patch_tasks_by_task_id
system: platform
service: platform-service
name: Patch Task
binding:
  protocol: http
  method: PATCH
  path: /api/integration/tasks/{task_id}
  auth: bearer
request:
  declarations:
  - name: name
    path: $.name
    type: string
    ui_kind: text
  - name: resultPolicy
    path: $.resultPolicy
    type: string
    ui_kind: text
  - name: schemeId
    path: $.schemeId
    type: string
    ui_kind: text
  - name: targetSystem
    path: $.targetSystem
    type: string
    ui_kind: text
  - name: triggerCron
    path: $.triggerCron
    type: string
    ui_kind: text
  - name: visibility
    path: $.visibility
    type: string
    ui_kind: text
responses:
  "200":
    description: Successful Response
metadata:
  module: integration
  tags:
  - platform
  owner: gimbal-bootstrap
```
