---
id: platform.shares.post_root
type: endpoints
system: platform
service: platform-service
---

# Create Share

```gimbal:endpoint
review: draft
id: platform.shares.post_root
system: platform
service: platform-service
name: Create Share
description: ''
binding:
  protocol: http
  method: POST
  path: /api/shares
  timeout_seconds: 30.0
  auth: bearer
  body_type: json
request:
  declarations:
  - name: granteeUserId
    path: $.granteeUserId
    type: integer
    ui_kind: number
    description: ''
    required: true
    assertable: false
  - name: mode
    path: $.mode
    type: string
    ui_kind: text
    description: ''
    assertable: false
  - name: resourceId
    path: $.resourceId
    type: string
    ui_kind: text
    description: ''
    required: true
    assertable: false
  - name: resourceType
    path: $.resourceType
    type: string
    ui_kind: text
    description: ''
    required: true
    assertable: false
responses:
  '201':
    description: Successful Response
    declarations: []
  '200':
    description: 成功
    declarations: []
metadata:
  module: shares
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
