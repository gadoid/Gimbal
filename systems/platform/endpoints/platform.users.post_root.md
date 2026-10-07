---
id: platform.users.post_root
type: endpoints
system: platform
service: platform-service
---

# Create User

```gimbal:endpoint
review: reviewed
id: platform.users.post_root
system: platform
service: platform-service
name: Create User
description: 'Create a new user(M2.5 收紧:admin 开号 —— 创建账号是人事权,

  spec-1「任何登录用户可开号」的遗留闭合,权限方案 §5.3)。'
binding:
  protocol: http
  method: POST
  path: /api/users
  auth: bearer
request:
  declarations:
  - name: display_name
    path: $.display_name
    type: string
    ui_kind: text
  - name: password
    path: $.password
    type: string
    required: true
    ui_kind: text
  - name: role
    path: $.role
    type: string
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
  '201':
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
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
