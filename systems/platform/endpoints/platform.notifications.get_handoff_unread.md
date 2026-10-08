---
id: platform.notifications.get_handoff_unread
type: endpoints
system: platform
service: platform-service
---

# Handoff Unread

```gimbal:endpoint
review: reviewed
id: platform.notifications.get_handoff_unread
system: platform
service: platform-service
name: Handoff Unread
description: "未读分享列表(F1 悬浮标签数据源):场景行渲染 O(1) 查 Set 用。\n\n查询走 0005 已建的 (user_id, id) 索引,量级足够(方案 §1.4)。"
binding:
  protocol: http
  method: GET
  path: /api/notifications/handoff-unread
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
      ui_kind: json
      assertable: true
      children:
      - name: id
        path: $.items.id
        type: integer
        required: true
        ui_kind: number
        assertable: true
      - name: resourceId
        path: $.items.resourceId
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: senderName
        path: $.items.senderName
        type: string
        ui_kind: text
        assertable: true
metadata:
  module: notifications
  tags:
  - platform
  owner: gimbal-bootstrap
```
