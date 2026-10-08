---
id: platform.notifications.get_root
type: endpoints
system: platform
service: platform-service
---

# List Notifications

```gimbal:endpoint
review: reviewed
id: platform.notifications.get_root
system: platform
service: platform-service
name: List Notifications
binding:
  protocol: http
  method: GET
  path: /api/notifications
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
      - name: batchId
        path: $.items.batchId
        type: string
        ui_kind: text
        assertable: true
      - name: body
        path: $.items.body
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: created_at
        path: $.items.created_at
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
      - name: link
        path: $.items.link
        type: string
        ui_kind: text
        assertable: true
      - name: readAt
        path: $.items.readAt
        type: string
        ui_kind: text
        assertable: true
      - name: title
        path: $.items.title
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: type
        path: $.items.type
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
    - name: unread
      path: $.unread
      type: integer
      required: true
      ui_kind: number
      assertable: true
metadata:
  module: notifications
  tags:
  - platform
  owner: gimbal-bootstrap
```
