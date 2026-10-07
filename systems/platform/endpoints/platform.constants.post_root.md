---
id: platform.constants.post_root
type: endpoints
system: platform
service: platform-service
---

# Create Constant

```gimbal:endpoint
review: reviewed
id: platform.constants.post_root
system: platform
service: platform-service
name: Create Constant
binding:
  protocol: http
  method: POST
  path: /api/constants
  auth: bearer
request:
  declarations:
  - name: description
    path: $.description
    type: string
    ui_kind: text
  - name: entry_kind
    path: $.entry_kind
    type: string
    required: true
    ui_kind: text
  - name: name
    path: $.name
    type: string
    required: true
    ui_kind: text
  - name: spec
    path: $.spec
    type: object
    ui_kind: json
  - name: value
    path: $.value
    type: string
    ui_kind: text
responses:
  '200':
    description: 成功
    declarations:
    - name: created_at
      path: $.created_at
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: description
      path: $.description
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: entry_kind
      path: $.entry_kind
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: id
      path: $.id
      type: integer
      required: true
      ui_kind: number
      assertable: true
    - name: name
      path: $.name
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: spec
      path: $.spec
      type: object
      ui_kind: json
      assertable: true
    - name: updated_at
      path: $.updated_at
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: value
      path: $.value
      type: string
      ui_kind: text
      assertable: true
  '201':
    description: Successful Response
    declarations:
    - name: created_at
      path: $.created_at
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: description
      path: $.description
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: entry_kind
      path: $.entry_kind
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: id
      path: $.id
      type: integer
      required: true
      ui_kind: number
      assertable: true
    - name: name
      path: $.name
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: spec
      path: $.spec
      type: object
      ui_kind: json
      assertable: true
    - name: updated_at
      path: $.updated_at
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: value
      path: $.value
      type: string
      ui_kind: text
      assertable: true
metadata:
  module: constants
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
