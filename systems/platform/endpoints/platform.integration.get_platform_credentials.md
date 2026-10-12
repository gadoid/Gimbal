---
id: platform.integration.get_platform_credentials
type: endpoints
system: platform
service: platform-service
---

# List Platform Credentials

```gimbal:endpoint
review: draft
id: platform.integration.get_platform_credentials
system: platform
service: platform-service
name: List Platform Credentials
description: ''
binding:
  protocol: http
  method: GET
  path: /api/integration/platform-credentials
  timeout_seconds: 30.0
  auth: bearer
  body_type: none
request:
  declarations: []
responses:
  '200':
    description: Successful Response
    declarations: []
metadata:
  module: integration
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: ''
```
