---
id: platform.integration.get_tasks
type: endpoints
system: platform
service: platform-service
---

# List Tasks

```gimbal:endpoint
review: draft
id: platform.integration.get_tasks
system: platform
service: platform-service
name: List Tasks
description: 可见模板:我的 + 公共(admin 全见);软删的不出。
binding:
  protocol: http
  method: GET
  path: /api/integration/tasks
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
