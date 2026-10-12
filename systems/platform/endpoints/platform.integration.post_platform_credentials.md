---
id: platform.integration.post_platform_credentials
type: endpoints
system: platform
service: platform-service
---

# Create Platform Credential

```gimbal:endpoint
id: platform.integration.post_platform_credentials
system: platform
service: platform-service
name: Create Platform Credential
binding:
  protocol: http
  method: POST
  path: /api/integration/platform-credentials
  auth: bearer
request:
  declarations:
  - name: alias
    path: $.alias
    type: string
    required: true
    ui_kind: text
  - name: expiresIn
    path: $.expiresIn
    type: integer
    ui_kind: number
  - name: password
    path: $.password
    type: string
    required: true
    ui_kind: text
  - name: tokenType
    path: $.tokenType
    type: string
    ui_kind: text
  - name: url
    path: $.url
    type: string
    ui_kind: text
  - name: username
    path: $.username
    type: string
    required: true
    ui_kind: text
responses:
  "201":
    description: Successful Response
  "200":
    description: 成功
metadata:
  module: integration
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
