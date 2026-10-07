---
id: platform.report_definitions.post_root
type: endpoints
system: platform
service: platform-service
---

# Create Definition

```gimbal:endpoint
review: reviewed
id: platform.report_definitions.post_root
system: platform
service: platform-service
name: Create Definition
binding:
  protocol: http
  method: POST
  path: /api/report-definitions
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
    required: true
    ui_kind: text
  - name: presentation
    path: $.presentation
    type: object
    ui_kind: json
  - name: projection
    path: $.projection
    type: object
    ui_kind: json
  - name: public
    path: $.public
    type: boolean
    ui_kind: boolean
  - name: selection
    path: $.selection
    type: object
    ui_kind: json
responses:
  '200':
    description: 成功
  '201':
    description: Successful Response
metadata:
  module: report-definitions
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
