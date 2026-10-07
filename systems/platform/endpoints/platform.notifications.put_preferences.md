---
id: platform.notifications.put_preferences
type: endpoints
system: platform
service: platform-service
---

# Put Prefs

```gimbal:endpoint
review: reviewed
id: platform.notifications.put_preferences
system: platform
service: platform-service
name: Put Prefs
binding:
  protocol: http
  method: PUT
  path: /api/notifications/preferences
  auth: bearer
request:
  declarations:
  - name: 'off'
    path: $.off
    type: array
    ui_kind: json
responses:
  '200':
    description: Successful Response
    declarations:
    - name: 'off'
      path: $.off
      type: array
      required: true
      ui_kind: json
      assertable: true
metadata:
  module: notifications
  tags:
  - platform
  owner: gimbal-bootstrap
```
