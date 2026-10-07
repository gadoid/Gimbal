---
id: platform.auths.post_by_auth_id_test
type: endpoints
system: platform
service: platform-service
---

# Test Auth

```gimbal:endpoint
review: reviewed
id: platform.auths.post_by_auth_id_test
system: platform
service: platform-service
name: Test Auth
description: Dial the stored credential against ``url`` (probe service).
binding:
  protocol: http
  method: POST
  path: /api/auths/{auth_id}/test
  auth: bearer
  body_type: none
request: {}
responses:
  '200':
    description: Successful Response
    declarations:
    - name: message
      path: $.message
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: ok
      path: $.ok
      type: boolean
      required: true
      ui_kind: boolean
      assertable: true
    - name: status_code
      path: $.status_code
      type: integer
      ui_kind: number
      assertable: true
metadata:
  module: auths
  tags:
  - platform
  owner: gimbal-bootstrap
```
