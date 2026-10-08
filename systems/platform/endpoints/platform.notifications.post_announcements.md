---
id: platform.notifications.post_announcements
type: endpoints
system: platform
service: platform-service
---

# Post Announcement

```gimbal:endpoint
review: reviewed
id: platform.notifications.post_announcements
system: platform
service: platform-service
name: Post Announcement
binding:
  protocol: http
  method: POST
  path: /api/notifications/announcements
  auth: bearer
request:
  declarations:
  - name: body
    path: $.body
    type: string
    ui_kind: text
  - name: hours
    path: $.hours
    type: integer
    description: 有效小时数;0 = 永不过期
    ui_kind: number
  - name: title
    path: $.title
    type: string
    required: true
    ui_kind: text
responses:
  "200":
    description: 成功
  "201":
    description: Successful Response
metadata:
  module: notifications
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
