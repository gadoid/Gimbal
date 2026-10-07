---
id: platform.handoff.post_root
type: endpoints
system: platform
service: platform-service
---

# Handoff Resource

```gimbal:endpoint
review: reviewed
id: platform.handoff.post_root
system: platform
service: platform-service
name: Handoff Resource
binding:
  protocol: http
  method: POST
  path: /api/handoff
  auth: bearer
request:
  declarations:
  - name: resource_id
    path: $.resource_id
    type: string
    required: true
    ui_kind: text
  - name: resource_type
    path: $.resource_type
    type: string
    ui_kind: text
  - name: target_user_id
    path: $.target_user_id
    type: integer
    required: true
    ui_kind: number
responses:
  '200':
    description: Successful Response
    declarations:
    - name: new_name
      path: $.new_name
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: new_resource_id
      path: $.new_resource_id
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: renamed
      path: $.renamed
      type: boolean
      required: true
      ui_kind: boolean
      assertable: true
    - name: status
      path: $.status
      type: string
      ui_kind: text
      assertable: true
metadata:
  module: handoff
  tags:
  - platform
  owner: gimbal-bootstrap
```
