---
id: platform.report_definitions.get_root
type: endpoints
system: platform
service: platform-service
---

# List Definitions

```gimbal:endpoint
review: reviewed
id: platform.report_definitions.get_root
system: platform
service: platform-service
name: List Definitions
binding:
  protocol: http
  method: GET
  path: /api/report-definitions
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
