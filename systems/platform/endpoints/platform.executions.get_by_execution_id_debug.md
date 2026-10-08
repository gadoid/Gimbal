---
id: platform.executions.get_by_execution_id_debug
type: endpoints
system: platform
service: platform-service
---

# Debug Session Info

```gimbal:endpoint
review: reviewed
id: platform.executions.get_by_execution_id_debug
system: platform
service: platform-service
name: Debug Session Info
description: 调试会话元信息（前端据此渲染调试台入口与命令可用态）。
binding:
  protocol: http
  method: GET
  path: /api/executions/{execution_id}/debug
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
metadata:
  module: executions
  tags:
  - platform
  owner: gimbal-bootstrap
```
