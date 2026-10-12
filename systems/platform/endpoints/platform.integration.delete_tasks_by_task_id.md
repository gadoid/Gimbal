---
id: platform.integration.delete_tasks_by_task_id
type: endpoints
system: platform
service: platform-service
---

# Delete Task

```gimbal:endpoint
id: platform.integration.delete_tasks_by_task_id
system: platform
service: platform-service
name: Delete Task
description: 软删(评审 E7):卡片走「已移除」态,订阅者可见可自行删卡。
binding:
  protocol: http
  method: DELETE
  path: /api/integration/tasks/{task_id}
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
metadata:
  module: integration
  tags:
  - platform
  owner: gimbal-bootstrap
```
