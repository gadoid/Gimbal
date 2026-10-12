---
id: platform.environments.post_root
type: endpoints
system: platform
service: platform-service
---

# Create Environment

```gimbal:endpoint
id: platform.environments.post_root
system: platform
service: platform-service
name: Create Environment
binding:
  protocol: http
  method: POST
  path: /api/environments
  auth: bearer
request:
  declarations:
  - name: description
    path: $.description
    type: string
    ui_kind: text
  - name: lines
    path: $.lines
    type: object
    description: "{系统名: 版本线}"
    ui_kind: json
  - name: name
    path: $.name
    type: string
    required: true
    ui_kind: text
responses:
  "201":
    description: Successful Response
    declarations:
    - name: description
      path: $.description
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
    - name: lines
      path: $.lines
      type: object
      required: true
      ui_kind: json
      assertable: true
    - name: name
      path: $.name
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: owner_id
      path: $.owner_id
      type: integer
      ui_kind: number
      assertable: true
    - name: visibility
      path: $.visibility
      type: string
      required: true
      ui_kind: text
      assertable: true
  "200":
    description: 成功
    declarations:
    - name: description
      path: $.description
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
    - name: lines
      path: $.lines
      type: object
      required: true
      ui_kind: json
      assertable: true
    - name: name
      path: $.name
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: owner_id
      path: $.owner_id
      type: integer
      ui_kind: number
      assertable: true
    - name: visibility
      path: $.visibility
      type: string
      required: true
      ui_kind: text
      assertable: true
metadata:
  module: environments
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
