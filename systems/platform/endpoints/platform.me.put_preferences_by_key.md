---
id: platform.me.put_preferences_by_key
type: endpoints
system: platform
service: platform-service
---

# Put Preference

```gimbal:endpoint
review: reviewed
id: platform.me.put_preferences_by_key
system: platform
service: platform-service
name: Put Preference
binding:
  protocol: http
  method: PUT
  path: /api/me/preferences/{key}
  auth: bearer
request:
  declarations:
  - name: value
    path: $.value
    type: string
    required: true
    ui_kind: text
responses:
  "200":
    description: Successful Response
    declarations:
    - name: key
      path: $.key
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: value
      path: $.value
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
