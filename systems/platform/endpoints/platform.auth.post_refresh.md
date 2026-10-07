---
id: platform.auth.post_refresh
type: endpoints
system: platform
service: platform-service
---

# Refresh

```gimbal:endpoint
review: reviewed
id: platform.auth.post_refresh
system: platform
service: platform-service
name: Refresh
binding:
  protocol: http
  method: POST
  path: /api/auth/refresh
  auth: bearer
request:
  declarations:
  - name: refresh_token
    path: $.refresh_token
    type: string
    required: true
    ui_kind: text
responses:
  '200':
    description: Successful Response
    declarations:
    - name: access_token
      path: $.access_token
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: refresh_token
      path: $.refresh_token
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: token_type
      path: $.token_type
      type: string
      ui_kind: text
      assertable: true
    - name: user
      path: $.user
      type: object
      required: true
      description: Public-facing user view. ``created_at`` is serialized to ISO 8601 string.
      ui_kind: json
      assertable: true
      children:
      - name: created_at
        path: $.user.created_at
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: display_name
        path: $.user.display_name
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: id
        path: $.user.id
        type: integer
        required: true
        ui_kind: number
        assertable: true
      - name: is_active
        path: $.user.is_active
        type: boolean
        required: true
        ui_kind: boolean
        assertable: true
      - name: is_admin
        path: $.user.is_admin
        type: boolean
        ui_kind: boolean
        assertable: true
      - name: role
        path: $.user.role
        type: string
        ui_kind: text
        assertable: true
      - name: updated_at
        path: $.user.updated_at
        type: string
        ui_kind: text
        assertable: true
      - name: username
        path: $.user.username
        type: string
        required: true
        ui_kind: text
        assertable: true
metadata:
  module: auth
  tags:
  - platform
  owner: gimbal-bootstrap
```
