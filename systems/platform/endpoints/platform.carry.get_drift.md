---
id: platform.carry.get_drift
type: endpoints
system: platform
service: platform-service
---

# Drift

```gimbal:endpoint
review: reviewed
id: platform.carry.get_drift
system: platform
service: platform-service
name: Drift
binding:
  protocol: http
  method: GET
  path: /api/carry/drift
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
    declarations:
    - name: plateReachable
      path: $.plateReachable
      type: boolean
      ui_kind: boolean
      assertable: true
    - name: services
      path: $.services
      type: array
      ui_kind: json
      assertable: true
      children:
      - name: baseService
        path: $.services.baseService
        type: string
        ui_kind: text
        assertable: true
      - name: orphaned
        path: $.services.orphaned
        type: array
        ui_kind: json
        assertable: true
      - name: renamedSuggestions
        path: $.services.renamedSuggestions
        type: array
        ui_kind: json
        assertable: true
      - name: service
        path: $.services.service
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: uncovered
        path: $.services.uncovered
        type: array
        ui_kind: json
        assertable: true
metadata:
  module: carry
  tags:
  - platform
  owner: gimbal-bootstrap
```
