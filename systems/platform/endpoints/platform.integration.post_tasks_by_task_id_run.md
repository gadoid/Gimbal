---
id: platform.integration.post_tasks_by_task_id_run
type: endpoints
system: platform
service: platform-service
---

# Run Task

```gimbal:endpoint
id: platform.integration.post_tasks_by_task_id_run
system: platform
service: platform-service
name: Run Task
description: 立即执行(任意可见者;平台模式冷却 60s —— 方案 §3 操作表)。
binding:
  protocol: http
  method: POST
  path: /api/integration/tasks/{task_id}/run
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
