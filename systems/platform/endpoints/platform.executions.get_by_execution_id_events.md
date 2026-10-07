---
id: platform.executions.get_by_execution_id_events
type: endpoints
system: platform
service: platform-service
---

# Get Execution Events

```gimbal:endpoint
review: reviewed
id: platform.executions.get_by_execution_id_events
system: platform
service: platform-service
name: Get Execution Events
description: 事件/日志组合筛选查询(P2-07/C10 日志分析页的读面)。
binding:
  protocol: http
  method: GET
  path: /api/executions/{execution_id}/events
  auth: bearer
  body_type: none
request: {}
responses:
  '200':
    description: Successful Response
metadata:
  module: executions
  tags:
  - platform
  owner: gimbal-bootstrap
```
