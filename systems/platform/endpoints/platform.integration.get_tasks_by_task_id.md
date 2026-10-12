---
id: platform.integration.get_tasks_by_task_id
type: endpoints
system: platform
service: platform-service
---

# Get Task

```gimbal:endpoint
review: reviewed
id: platform.integration.get_tasks_by_task_id
system: platform
service: platform-service
name: Get Task
binding:
  protocol: http
  method: GET
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
