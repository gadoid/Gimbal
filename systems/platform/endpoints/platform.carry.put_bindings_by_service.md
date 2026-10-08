---
id: platform.carry.put_bindings_by_service
type: endpoints
system: platform
service: platform-service
---

# Put Bindings

```gimbal:endpoint
review: reviewed
id: platform.carry.put_bindings_by_service
system: platform
service: platform-service
name: Put Bindings
binding:
  protocol: http
  method: PUT
  path: /api/carry/bindings/{service}
  auth: bearer
request:
  declarations:
  - name: bindings
    path: $.bindings
    type: object
    ui_kind: json
responses:
  "200":
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
