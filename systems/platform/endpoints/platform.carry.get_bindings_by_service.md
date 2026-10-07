---
id: platform.carry.get_bindings_by_service
type: endpoints
system: platform
service: platform-service
---

# Get Bindings

```gimbal:endpoint
review: reviewed
id: platform.carry.get_bindings_by_service
system: platform
service: platform-service
name: Get Bindings
binding:
  protocol: http
  method: GET
  path: /api/carry/bindings/{service}
  auth: bearer
  body_type: none
request: {}
responses:
  '200':
    description: Successful Response
    declarations:
    - name: bindings
      path: $.bindings
      type: object
      ui_kind: json
      assertable: true
metadata:
  module: carry
  tags:
  - platform
  owner: gimbal-bootstrap
```
