---
id: platform.constants.delete_by_entry_id
type: endpoints
system: platform
service: platform-service
---

# Delete Constant

```gimbal:endpoint
review: reviewed
id: platform.constants.delete_by_entry_id
system: platform
service: platform-service
name: Delete Constant
binding:
  protocol: http
  method: DELETE
  path: /api/constants/{entry_id}
  auth: bearer
  body_type: none
request: {}
responses:
  '200':
    description: 成功
  '204':
    description: Successful Response
metadata:
  module: constants
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
