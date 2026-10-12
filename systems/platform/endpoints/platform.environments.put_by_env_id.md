---
id: platform.environments.put_by_env_id
type: endpoints
system: platform
service: platform-service
---

# Update Environment

```gimbal:endpoint
review: draft
id: platform.environments.put_by_env_id
system: platform
service: platform-service
name: Update Environment
description: ''
binding:
  protocol: http
  method: PUT
  path: /api/environments/{env_id}
  timeout_seconds: 30.0
  auth: bearer
  body_type: json
request:
  declarations:
  - name: description
    path: $.description
    type: string
    ui_kind: text
    description: ''
    assertable: false
  - name: lines
    path: $.lines
    type: object
    ui_kind: json
    description: ''
    assertable: false
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
