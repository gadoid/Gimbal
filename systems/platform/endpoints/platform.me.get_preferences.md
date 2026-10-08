---
id: platform.me.get_preferences
type: endpoints
system: platform
service: platform-service
---

# Get Preferences

```gimbal:endpoint
review: reviewed
id: platform.me.get_preferences
system: platform
service: platform-service
name: Get Preferences
binding:
  protocol: http
  method: GET
  path: /api/me/preferences
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
    declarations:
    - name: items
      path: $.items
      type: object
      required: true
      ui_kind: json
      assertable: true
metadata:
  module: me
  tags:
  - platform
  owner: gimbal-bootstrap
```
