---
id: platform.integration.get_platform_credentials
type: endpoints
system: platform
service: platform-service
---

# List Platform Credentials

```gimbal:endpoint
id: platform.integration.get_platform_credentials
system: platform
service: platform-service
name: List Platform Credentials
binding:
  protocol: http
  method: GET
  path: /api/integration/platform-credentials
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
metadata:
  module: integration
  tags:
  - platform
  owner: gimbal-bootstrap
```
