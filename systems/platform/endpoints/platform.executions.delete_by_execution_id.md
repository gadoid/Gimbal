---
id: platform.executions.delete_by_execution_id
type: endpoints
system: platform
service: platform-service
---

# Delete Execution

```gimbal:endpoint
review: reviewed
id: platform.executions.delete_by_execution_id
system: platform
service: platform-service
name: Delete Execution
binding:
  protocol: http
  method: DELETE
  path: /api/executions/{execution_id}
  auth: bearer
  body_type: none
request: {}
responses:
  '200':
    description: 成功
  '204':
    description: Successful Response
metadata:
  module: executions
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
