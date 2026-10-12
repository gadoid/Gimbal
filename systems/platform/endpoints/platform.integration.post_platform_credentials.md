---
id: platform.integration.post_platform_credentials
type: endpoints
system: platform
service: platform-service
---

# Create Platform Credential

```gimbal:endpoint
review: draft
id: platform.integration.post_platform_credentials
system: platform
service: platform-service
name: Create Platform Credential
description: ''
binding:
  protocol: http
  method: POST
  path: /api/integration/platform-credentials
  timeout_seconds: 30.0
  auth: bearer
  body_type: json
request:
  declarations:
  - name: alias
    path: $.alias
    type: string
    ui_kind: text
    description: ''
    required: true
    assertable: false
  - name: expiresIn
    path: $.expiresIn
    type: integer
    ui_kind: number
    description: ''
    assertable: false
  - name: password
    path: $.password
    type: string
    ui_kind: text
    description: ''
    required: true
    assertable: false
  - name: tokenType
    path: $.tokenType
    type: string
    ui_kind: text
    description: ''
    assertable: false
  - name: url
    path: $.url
    type: string
    ui_kind: text
    description: ''
    assertable: false
  - name: username
    path: $.username
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
  module: integration
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
