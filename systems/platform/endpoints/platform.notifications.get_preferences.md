---
id: platform.notifications.get_preferences
type: endpoints
system: platform
service: platform-service
---

# Get Prefs

```gimbal:endpoint
review: reviewed
id: platform.notifications.get_preferences
system: platform
service: platform-service
name: Get Prefs
binding:
  protocol: http
  method: GET
  path: /api/notifications/preferences
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
    declarations:
    - name: "off"
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
