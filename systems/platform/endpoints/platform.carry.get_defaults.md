---
id: platform.carry.get_defaults
type: endpoints
system: platform
service: platform-service
---

# Get Defaults

```gimbal:endpoint
review: reviewed
id: platform.carry.get_defaults
system: platform
service: platform-service
name: Get Defaults
binding:
  protocol: http
  method: GET
  path: /api/carry/defaults
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
    declarations:
    - name: defaults
      path: $.defaults
      type: object
      ui_kind: json
      assertable: true
metadata:
  module: carry
  tags:
  - platform
  owner: gimbal-bootstrap
```
