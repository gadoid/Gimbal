---
id: platform.scenarios.delete_by_scenario_id_run_schemes_by_s_6a5300
type: endpoints
system: platform
service: platform-service
---

# Delete Run Scheme

```gimbal:endpoint
review: reviewed
id: platform.scenarios.delete_by_scenario_id_run_schemes_by_s_6a5300
system: platform
service: platform-service
name: Delete Run Scheme
binding:
  protocol: http
  method: DELETE
  path: /api/scenarios/{scenario_id}/run-schemes/{scheme_id}
  auth: bearer
  body_type: none
request: {}
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
