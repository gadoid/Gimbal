---
id: platform.environments.get_root
type: endpoints
system: platform
service: platform-service
---

# List Environments

```gimbal:endpoint
review: draft
id: platform.environments.get_root
system: platform
service: platform-service
name: List Environments
description: ''
binding:
  protocol: http
  method: GET
  path: /api/environments
  timeout_seconds: 30.0
  auth: bearer
  body_type: none
request:
  declarations: []
responses:
  '200':
    description: Successful Response
    declarations:
    - name: description
      path: $.description
      type: string
      ui_kind: text
      description: ''
      required: true
      assertable: true
    - name: id
      path: $.id
      type: integer
      ui_kind: number
      description: ''
      required: true
      assertable: true
    - name: lines
      path: $.lines
      type: object
      ui_kind: json
      description: ''
      required: true
      assertable: true
    - name: name
      path: $.name
      type: string
      ui_kind: text
      description: ''
      required: true
      assertable: true
    - name: owner_id
      path: $.owner_id
      type: integer
      ui_kind: number
      description: ''
      assertable: true
    - name: visibility
      path: $.visibility
      type: string
      ui_kind: text
      description: ''
      required: true
      assertable: true
metadata:
  module: environments
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: ''
```
