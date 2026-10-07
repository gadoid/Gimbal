---
id: platform.users.patch_by_user_id
type: endpoints
system: platform
service: platform-service
---

# Patch User

```gimbal:endpoint
review: reviewed
id: platform.users.patch_by_user_id
system: platform
service: platform-service
name: Patch User
description: "Update ``display_name`` / ``is_admin`` / ``is_active`` / ``new_password``.\n\nAuthorization:\n* admin caller — may patch any user, any field.\n* member caller — may only patch **themselves** (403/4032 on other\n  targets) and may never touch ``role`` (privilege-escalation fix).\n\nConstraint: demoting the last admin(``role`` 从 admin 降下)被 409 拒。"
binding:
  protocol: http
  method: PATCH
  path: /api/users/{user_id}
  auth: bearer
request:
  declarations:
  - name: display_name
    path: $.display_name
    type: string
    ui_kind: text
  - name: is_active
    path: $.is_active
    type: boolean
    ui_kind: boolean
  - name: new_password
    path: $.new_password
    type: string
    ui_kind: text
  - name: role
    path: $.role
    type: string
    ui_kind: text
responses:
  '200':
    description: Successful Response
    declarations:
    - name: created_at
      path: $.created_at
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: display_name
      path: $.display_name
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
    - name: is_active
      path: $.is_active
      type: boolean
      required: true
      ui_kind: boolean
      assertable: true
    - name: is_admin
      path: $.is_admin
      type: boolean
      ui_kind: boolean
      assertable: true
    - name: role
      path: $.role
      type: string
      ui_kind: text
      assertable: true
    - name: updated_at
      path: $.updated_at
      type: string
      ui_kind: text
      assertable: true
    - name: username
      path: $.username
      type: string
      required: true
      ui_kind: text
      assertable: true
metadata:
  module: users
  tags:
  - platform
  owner: gimbal-bootstrap
```
