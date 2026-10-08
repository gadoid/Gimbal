---
id: platform.users.get_root
type: endpoints
system: platform
service: platform-service
---

# List Users

```gimbal:endpoint
review: reviewed
id: platform.users.get_root
system: platform
service: platform-service
name: List Users
description: "List every user(M2.5 收紧:member+ 可见〔0011 更名:原 operator+〕;\n原「任何登录用户全量可见」的 spec-1 遗留闭合 —— 权限方案 §5.3)。\nM4(§6.3):q(username/display_name 子串)+ role 精确 + Page 信封。"
binding:
  protocol: http
  method: GET
  path: /api/users
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
    declarations:
    - name: items
      path: $.items
      type: array
      required: true
      ui_kind: json
      assertable: true
      children:
      - name: created_at
        path: $.items.created_at
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: display_name
        path: $.items.display_name
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: id
        path: $.items.id
        type: integer
        required: true
        ui_kind: number
        assertable: true
      - name: is_active
        path: $.items.is_active
        type: boolean
        required: true
        ui_kind: boolean
        assertable: true
      - name: is_admin
        path: $.items.is_admin
        type: boolean
        ui_kind: boolean
        assertable: true
      - name: role
        path: $.items.role
        type: string
        ui_kind: text
        assertable: true
      - name: updated_at
        path: $.items.updated_at
        type: string
        ui_kind: text
        assertable: true
      - name: username
        path: $.items.username
        type: string
        required: true
        ui_kind: text
        assertable: true
    - name: page
      path: $.page
      type: integer
      ui_kind: number
      assertable: true
    - name: pageSize
      path: $.pageSize
      type: integer
      ui_kind: number
      assertable: true
    - name: total
      path: $.total
      type: integer
      ui_kind: number
      assertable: true
metadata:
  module: users
  tags:
  - platform
  owner: gimbal-bootstrap
```
