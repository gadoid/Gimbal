---
id: platform.auths.post_root
type: endpoints
system: platform
service: platform-service
---

# Create Auth

```gimbal:endpoint
review: reviewed
id: platform.auths.post_root
system: platform
service: platform-service
name: Create Auth
binding:
  protocol: http
  method: POST
  path: /api/auths
  auth: bearer
request:
  declarations:
  - name: alias
    path: $.alias
    type: string
    required: true
    ui_kind: text
  - name: expires_in
    path: $.expires_in
    type: integer
    ui_kind: number
  - name: password
    path: $.password
    type: string
    required: true
    ui_kind: text
  - name: token_type
    path: $.token_type
    type: string
    ui_kind: text
  - name: url
    path: $.url
    type: string
    required: true
    ui_kind: text
  - name: username
    path: $.username
    type: string
    required: true
    ui_kind: text
responses:
  '200':
    description: 成功
    declarations:
    - name: alias
      path: $.alias
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: alias_ref_count
      path: $.alias_ref_count
      type: integer
      ui_kind: number
      assertable: true
    - name: created_at
      path: $.created_at
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: expires_in
      path: $.expires_in
      type: integer
      required: true
      ui_kind: number
      assertable: true
    - name: id
      path: $.id
      type: integer
      required: true
      ui_kind: number
      assertable: true
    - name: password_masked
      path: $.password_masked
      type: string
      ui_kind: text
      assertable: true
    - name: scenario_ref_count
      path: $.scenario_ref_count
      type: integer
      ui_kind: number
      assertable: true
    - name: token_type
      path: $.token_type
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: updated_at
      path: $.updated_at
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: url
      path: $.url
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: username
      path: $.username
      type: string
      required: true
      ui_kind: text
      assertable: true
  '201':
    description: Successful Response
    declarations:
    - name: alias
      path: $.alias
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: alias_ref_count
      path: $.alias_ref_count
      type: integer
      ui_kind: number
      assertable: true
    - name: created_at
      path: $.created_at
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: expires_in
      path: $.expires_in
      type: integer
      required: true
      ui_kind: number
      assertable: true
    - name: id
      path: $.id
      type: integer
      required: true
      ui_kind: number
      assertable: true
    - name: password_masked
      path: $.password_masked
      type: string
      ui_kind: text
      assertable: true
    - name: scenario_ref_count
      path: $.scenario_ref_count
      type: integer
      ui_kind: number
      assertable: true
    - name: token_type
      path: $.token_type
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: updated_at
      path: $.updated_at
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: url
      path: $.url
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: username
      path: $.username
      type: string
      required: true
      ui_kind: text
      assertable: true
metadata:
  module: auths
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
