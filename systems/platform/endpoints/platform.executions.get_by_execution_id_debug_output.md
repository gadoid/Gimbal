---
id: platform.executions.get_by_execution_id_debug_output
type: endpoints
system: platform
service: platform-service
---

# Debug Session Output

```gimbal:endpoint
review: reviewed
id: platform.executions.get_by_execution_id_debug_output
system: platform
service: platform-service
name: Debug Session Output
description: 取回（并清空）调试会话输出（暂停提示等）；前端轮询。
binding:
  protocol: http
  method: GET
  path: /api/executions/{execution_id}/debug/output
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
