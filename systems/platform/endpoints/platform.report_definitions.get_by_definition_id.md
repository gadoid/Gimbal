---
id: platform.report_definitions.get_by_definition_id
type: endpoints
system: platform
service: platform-service
---

# Get Definition

```gimbal:endpoint
review: reviewed
id: platform.report_definitions.get_by_definition_id
system: platform
service: platform-service
name: Get Definition
binding:
  protocol: http
  method: GET
  path: /api/report-definitions/{definition_id}
  auth: bearer
  body_type: none
request: {}
responses:
  '200':
    description: Successful Response
metadata:
  module: report-definitions
  tags:
  - platform
  owner: gimbal-bootstrap
```
