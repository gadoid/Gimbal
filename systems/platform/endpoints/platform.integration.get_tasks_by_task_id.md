---
id: platform.integration.get_tasks_by_task_id
type: endpoints
system: platform
service: platform-service
---

# Get Task

```gimbal:endpoint
review: draft
id: platform.integration.get_tasks_by_task_id
system: platform
service: platform-service
name: Get Task
description: ''
binding:
  protocol: http
  method: GET
  path: /api/integration/tasks/{task_id}
  timeout_seconds: 30.0
  auth: bearer
  body_type: none
request:
  declarations: []
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
