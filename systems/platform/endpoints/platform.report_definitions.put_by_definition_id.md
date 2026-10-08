---
id: platform.report_definitions.put_by_definition_id
type: endpoints
system: platform
service: platform-service
---

# Update Definition

```gimbal:endpoint
review: reviewed
id: platform.report_definitions.put_by_definition_id
system: platform
service: platform-service
name: Update Definition
binding:
  protocol: http
  method: PUT
  path: /api/report-definitions/{definition_id}
  auth: bearer
request:
  declarations:
  - name: definition
    path: $.definition
    type: object
    ui_kind: json
  - name: description
    path: $.description
    type: string
    ui_kind: text
  - name: name
    path: $.name
    type: string
    ui_kind: text
  - name: public
    path: $.public
    type: boolean
    ui_kind: boolean
responses:
  "200":
    description: Successful Response
metadata:
  module: report-definitions
  tags:
  - platform
  owner: gimbal-bootstrap
```
