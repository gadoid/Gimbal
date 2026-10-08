---
id: platform.notifications.get_unread_count
type: endpoints
system: platform
service: platform-service
---

# Unread Count

```gimbal:endpoint
review: reviewed
id: platform.notifications.get_unread_count
system: platform
service: platform-service
name: Unread Count
binding:
  protocol: http
  method: GET
  path: /api/notifications/unread-count
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
    declarations:
    - name: count
      path: $.count
      type: integer
      required: true
      ui_kind: number
      assertable: true
    - name: roleVersion
      path: $.roleVersion
      type: string
      ui_kind: text
      assertable: true
metadata:
  module: notifications
  tags:
  - platform
  owner: gimbal-bootstrap
```
