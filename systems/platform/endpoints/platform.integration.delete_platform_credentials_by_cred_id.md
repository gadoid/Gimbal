---
id: platform.integration.delete_platform_credentials_by_cred_id
type: endpoints
system: platform
service: platform-service
---

# Delete Platform Credential

```gimbal:endpoint
review: reviewed
id: platform.integration.delete_platform_credentials_by_cred_id
system: platform
service: platform-service
name: Delete Platform Credential
binding:
  protocol: http
  method: DELETE
  path: /api/integration/platform-credentials/{cred_id}
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
