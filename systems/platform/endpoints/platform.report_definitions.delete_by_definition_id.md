---
id: platform.report_definitions.delete_by_definition_id
type: endpoints
system: platform
service: platform-service
---

# Delete Definition

```gimbal:endpoint
review: reviewed
id: platform.report_definitions.delete_by_definition_id
system: platform
service: platform-service
name: Delete Definition
binding:
  protocol: http
  method: DELETE
  path: /api/report-definitions/{definition_id}
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: 成功
  "204":
    description: Successful Response
metadata:
  module: report-definitions
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
