---
id: platform.carry.put_defaults
type: endpoints
system: platform
service: platform-service
---

# Put Defaults

```gimbal:endpoint
review: reviewed
id: platform.carry.put_defaults
system: platform
service: platform-service
name: Put Defaults
binding:
  protocol: http
  method: PUT
  path: /api/carry/defaults
  auth: bearer
request:
  declarations:
  - name: defaults
    path: $.defaults
    type: object
    ui_kind: json
responses:
  '200':
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
