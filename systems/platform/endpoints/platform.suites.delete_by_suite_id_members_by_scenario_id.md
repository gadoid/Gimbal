---
id: platform.suites.delete_by_suite_id_members_by_scenario_id
type: endpoints
system: platform
service: platform-service
---

# Remove Member

```gimbal:endpoint
review: draft
id: platform.suites.delete_by_suite_id_members_by_scenario_id
system: platform
service: platform-service
name: Remove Member
description: ''
binding:
  protocol: http
  method: DELETE
  path: /api/suites/{suite_id}/members/{scenario_id}
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
  module: suites
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
