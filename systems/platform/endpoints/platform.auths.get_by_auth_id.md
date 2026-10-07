---
id: platform.auths.get_by_auth_id
type: endpoints
system: platform
service: platform-service
---

# Get Auth

```gimbal:endpoint
review: reviewed
id: platform.auths.get_by_auth_id
system: platform
service: platform-service
name: Get Auth
binding:
  protocol: http
  method: GET
  path: /api/auths/{auth_id}
  auth: bearer
  body_type: none
request: {}
responses:
  '200':
    description: Successful Response
    declarations:
    - name: alias
      path: $.alias
      type: string
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
      ui_kind: text
      assertable: true
    - name: expires_in
      path: $.expires_in
      type: integer
      ui_kind: number
      assertable: true
    - name: id
      path: $.id
      type: integer
      ui_kind: number
      assertable: true
    - name: password
      path: $.password
      type: string
      ui_kind: text
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
      ui_kind: text
      assertable: true
    - name: updated_at
      path: $.updated_at
      type: string
      ui_kind: text
      assertable: true
    - name: url
      path: $.url
      type: string
      ui_kind: text
      assertable: true
    - name: username
      path: $.username
      type: string
      ui_kind: text
      assertable: true
metadata:
  module: auths
  tags:
  - platform
  owner: gimbal-bootstrap
```
