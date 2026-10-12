---
id: platform.environments.delete_by_env_id
type: endpoints
system: platform
service: platform-service
---

# Delete Environment

```gimbal:endpoint
review: draft
id: platform.environments.delete_by_env_id
system: platform
service: platform-service
name: Delete Environment
description: ''
binding:
  protocol: http
  method: DELETE
  path: /api/environments/{env_id}
  timeout_seconds: 30.0
  auth: bearer
  body_type: none
request:
  declarations: []
responses:
  '204':
    description: Successful Response
    declarations: []
  '200':
    description: 成功
    declarations: []
metadata:
  module: environments
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
