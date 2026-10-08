---
id: platform.scenario_filter_groups.get_root
type: endpoints
system: platform
service: platform-service
---

# List Groups

```gimbal:endpoint
review: reviewed
id: platform.scenario_filter_groups.get_root
system: platform
service: platform-service
name: List Groups
binding:
  protocol: http
  method: GET
  path: /api/scenario-filter-groups
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
    declarations:
    - name: items
      path: $.items
      type: array
      required: true
      ui_kind: json
      assertable: true
      children:
      - name: createdAt
        path: $.items.createdAt
        type: string
        ui_kind: text
        assertable: true
      - name: filters
        path: $.items.filters
        type: object
        ui_kind: json
        assertable: true
      - name: id
        path: $.items.id
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: name
        path: $.items.name
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: q
        path: $.items.q
        type: string
        ui_kind: text
        assertable: true
metadata:
  module: scenario-filter-groups
  tags:
  - platform
  owner: gimbal-bootstrap
```
