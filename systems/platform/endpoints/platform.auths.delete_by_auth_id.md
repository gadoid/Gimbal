---
id: platform.auths.delete_by_auth_id
type: endpoints
system: platform
service: platform-service
---

# Delete Auth

```gimbal:endpoint
review: reviewed
id: platform.auths.delete_by_auth_id
system: platform
service: platform-service
name: Delete Auth
binding:
  protocol: http
  method: DELETE
  path: /api/auths/{auth_id}
  auth: bearer
  body_type: none
request: {}
responses:
  '200':
    description: 成功
  '204':
    description: Successful Response
metadata:
  module: auths
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
