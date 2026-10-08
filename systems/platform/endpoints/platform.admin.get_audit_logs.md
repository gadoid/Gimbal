---
id: platform.admin.get_audit_logs
type: endpoints
system: platform
service: platform-service
---

# List Audit Logs

```gimbal:endpoint
review: reviewed
id: platform.admin.get_audit_logs
system: platform
service: platform-service
name: List Audit Logs
description: "特权写审计(权限方案 §6):新→旧分页;``action`` 精确过滤;\n``actions`` 带回词表供前端过滤 chip。"
binding:
  protocol: http
  method: GET
  path: /api/admin/audit-logs
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
    declarations:
    - name: actions
      path: $.actions
      type: array
      ui_kind: json
      assertable: true
    - name: items
      path: $.items
      type: array
      required: true
      ui_kind: json
      assertable: true
      children:
      - name: action
        path: $.items.action
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: actorId
        path: $.items.actorId
        type: integer
        ui_kind: number
        assertable: true
      - name: actorName
        path: $.items.actorName
        type: string
        ui_kind: text
        assertable: true
      - name: createdAt
        path: $.items.createdAt
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: detail
        path: $.items.detail
        type: object
        ui_kind: json
        assertable: true
      - name: id
        path: $.items.id
        type: integer
        required: true
        ui_kind: number
        assertable: true
      - name: resourceId
        path: $.items.resourceId
        type: string
        ui_kind: text
        assertable: true
      - name: resourceType
        path: $.items.resourceType
        type: string
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
  module: admin
  tags:
  - platform
  owner: gimbal-bootstrap
```
