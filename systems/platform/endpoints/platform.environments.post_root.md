---
id: platform.environments.post_root
type: endpoints
system: platform
service: platform-service
---

# Create Environment

```gimbal:endpoint
review: draft
id: platform.environments.post_root
system: platform
service: platform-service
name: Create Environment
description: ''
binding:
  protocol: http
  method: POST
  path: /api/environments
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
    description: '{系统名: 版本线}'
    assertable: false
  - name: name
    path: $.name
    type: string
    ui_kind: text
    description: ''
    required: true
    assertable: false
responses:
  '201':
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
  '200':
    description: 成功
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
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
