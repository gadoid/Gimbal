---
id: platform.executions.get_by_execution_id_events_counts
type: endpoints
system: platform
service: platform-service
---

# Get Execution Event Counts

```gimbal:endpoint
review: reviewed
id: platform.executions.get_by_execution_id_events_counts
system: platform
service: platform-service
name: Get Execution Event Counts
description: 按 category 聚合计数(P2-07 验收:能展示按 category 聚合的计数)。
binding:
  protocol: http
  method: GET
  path: /api/executions/{execution_id}/events/counts
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
