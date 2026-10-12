---
id: platform.integration.get_tasks
type: endpoints
system: platform
service: platform-service
---

# List Tasks

```gimbal:endpoint
review: reviewed
id: platform.integration.get_tasks
system: platform
service: platform-service
name: List Tasks
description: 可见模板:我的 + 公共(admin 全见);软删的不出。
binding:
  protocol: http
  method: GET
  path: /api/integration/tasks
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
