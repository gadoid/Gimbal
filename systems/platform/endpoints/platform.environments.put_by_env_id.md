---
id: platform.environments.put_by_env_id
type: endpoints
system: platform
service: platform-service
---

# Update Environment

```gimbal:endpoint
id: platform.environments.put_by_env_id
system: platform
service: platform-service
name: Update Environment
binding:
  protocol: http
  method: PUT
  path: /api/environments/{env_id}
  auth: bearer
request:
  declarations:
  - name: description
    path: $.description
    type: string
    ui_kind: text
  - name: lines
    path: $.lines
    type: object
    ui_kind: json
responses:
  "200":
    description: Successful Response
    declarations:
    - name: description
      path: $.description
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: id
      path: $.id
      type: integer
      required: true
      ui_kind: number
      assertable: true
    - name: lines
      path: $.lines
      type: object
      required: true
      ui_kind: json
      assertable: true
    - name: name
      path: $.name
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: owner_id
      path: $.owner_id
      type: integer
      ui_kind: number
      assertable: true
    - name: visibility
      path: $.visibility
      type: string
      required: true
      ui_kind: text
      assertable: true
metadata:
  module: environments
  tags:
  - platform
  owner: gimbal-bootstrap
```
