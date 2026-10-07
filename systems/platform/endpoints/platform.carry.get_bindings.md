---
id: platform.carry.get_bindings
type: endpoints
system: platform
service: platform-service
---

# List Bindings

```gimbal:endpoint
review: reviewed
id: platform.carry.get_bindings
system: platform
service: platform-service
name: List Bindings
binding:
  protocol: http
  method: GET
  path: /api/carry/bindings
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
