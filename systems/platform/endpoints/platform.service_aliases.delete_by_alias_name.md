---
id: platform.service_aliases.delete_by_alias_name
type: endpoints
system: platform
service: platform-service
---

# Delete Alias

```gimbal:endpoint
review: reviewed
id: platform.service_aliases.delete_by_alias_name
system: platform
service: platform-service
name: Delete Alias
binding:
  protocol: http
  method: DELETE
  path: /api/service-aliases/{alias_name}
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: 成功
  "204":
    description: Successful Response
metadata:
  module: service-aliases
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
