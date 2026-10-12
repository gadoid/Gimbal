---
id: platform.integration.delete_platform_credentials_by_cred_id
type: endpoints
system: platform
service: platform-service
---

# Delete Platform Credential

```gimbal:endpoint
review: draft
id: platform.integration.delete_platform_credentials_by_cred_id
system: platform
service: platform-service
name: Delete Platform Credential
description: ''
binding:
  protocol: http
  method: DELETE
  path: /api/integration/platform-credentials/{cred_id}
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
