---
id: platform.scenarios.post_by_scenario_id_star
type: endpoints
system: platform
service: platform-service
---

# Star Scenario

```gimbal:endpoint
review: reviewed
id: platform.scenarios.post_by_scenario_id_star
system: platform
service: platform-service
name: Star Scenario
binding:
  protocol: http
  method: POST
  path: /api/scenarios/{scenario_id}/star
  auth: bearer
request:
  declarations:
  - name: starred
    path: $.starred
    type: boolean
    required: true
    ui_kind: boolean
responses:
  "200":
    description: 成功
  "204":
    description: Successful Response
metadata:
  module: scenarios
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
