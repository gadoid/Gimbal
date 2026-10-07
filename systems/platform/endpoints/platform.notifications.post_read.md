---
id: platform.notifications.post_read
type: endpoints
system: platform
service: platform-service
---

# Mark Read

```gimbal:endpoint
review: reviewed
id: platform.notifications.post_read
system: platform
service: platform-service
name: Mark Read
binding:
  protocol: http
  method: POST
  path: /api/notifications/read
  auth: bearer
request:
  declarations:
  - name: ids
    path: $.ids
    type: array
    description: 要标读的通知 id;缺省 = 全部已读
    ui_kind: json
responses:
  '200':
    description: Successful Response
metadata:
  module: notifications
  tags:
  - platform
  owner: gimbal-bootstrap
```
