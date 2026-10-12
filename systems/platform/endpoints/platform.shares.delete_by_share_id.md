---
id: platform.shares.delete_by_share_id
type: endpoints
system: platform
service: platform-service
---

# Delete Share

```gimbal:endpoint
id: platform.shares.delete_by_share_id
system: platform
service: platform-service
name: Delete Share
description: 撤销(属主/admin;admin 入审计)或退订(被分享人,不通知)。
binding:
  protocol: http
  method: DELETE
  path: /api/shares/{share_id}
  auth: bearer
  body_type: none
request: {}
responses:
  "204":
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
