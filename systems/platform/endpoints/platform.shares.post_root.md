---
id: platform.shares.post_root
type: endpoints
system: platform
service: platform-service
---

# Create Share

```gimbal:endpoint
review: reviewed
id: platform.shares.post_root
system: platform
service: platform-service
name: Create Share
binding:
  protocol: http
  method: POST
  path: /api/shares
  auth: bearer
request:
  declarations:
  - name: granteeUserId
    path: $.granteeUserId
    type: integer
    required: true
    ui_kind: number
  - name: mode
    path: $.mode
    type: string
    ui_kind: text
  - name: resourceId
    path: $.resourceId
    type: string
    required: true
    ui_kind: text
  - name: resourceType
    path: $.resourceType
    type: string
    required: true
    ui_kind: text
responses:
  "201":
    description: Successful Response
  "200":
    description: 成功
metadata:
  module: shares
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
