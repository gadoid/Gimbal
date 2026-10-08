---
id: platform.scenario_filter_groups.post_root
type: endpoints
system: platform
service: platform-service
---

# Create Group

```gimbal:endpoint
review: reviewed
id: platform.scenario_filter_groups.post_root
system: platform
service: platform-service
name: Create Group
binding:
  protocol: http
  method: POST
  path: /api/scenario-filter-groups
  auth: bearer
request:
  declarations:
  - name: bucket
    path: $.bucket
    type: string
    required: true
    ui_kind: text
  - name: filters
    path: $.filters
    type: object
    ui_kind: json
  - name: name
    path: $.name
    type: string
    required: true
    ui_kind: text
  - name: q
    path: $.q
    type: string
    ui_kind: text
responses:
  "200":
    description: Successful Response
    declarations:
    - name: createdAt
      path: $.createdAt
      type: string
      ui_kind: text
      assertable: true
    - name: filters
      path: $.filters
      type: object
      ui_kind: json
      assertable: true
    - name: id
      path: $.id
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: name
      path: $.name
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: q
      path: $.q
      type: string
      ui_kind: text
      assertable: true
metadata:
  module: scenario-filter-groups
  tags:
  - platform
  owner: gimbal-bootstrap
```
