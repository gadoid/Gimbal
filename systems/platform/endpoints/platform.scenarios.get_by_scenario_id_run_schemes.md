---
id: platform.scenarios.get_by_scenario_id_run_schemes
type: endpoints
system: platform
service: platform-service
---

# List Run Schemes

```gimbal:endpoint
review: reviewed
id: platform.scenarios.get_by_scenario_id_run_schemes
system: platform
service: platform-service
name: List Run Schemes
binding:
  protocol: http
  method: GET
  path: /api/scenarios/{scenario_id}/run-schemes
  auth: bearer
  body_type: none
request: {}
responses:
  '200':
    description: Successful Response
metadata:
  module: scenarios
  tags:
  - platform
  owner: gimbal-bootstrap
```
