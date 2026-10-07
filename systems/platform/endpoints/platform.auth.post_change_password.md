---
id: platform.auth.post_change_password
type: endpoints
system: platform
service: platform-service
---

# Change Password

```gimbal:endpoint
review: reviewed
id: platform.auth.post_change_password
system: platform
service: platform-service
name: Change Password
description: '自服务改密(P2-1):核验旧密码 → 写新哈希。改密后现有会话保留

  (JWT 不含密码指纹;审计按特权写口径不记 —— 本人常规自管)。'
binding:
  protocol: http
  method: POST
  path: /api/auth/change-password
  auth: bearer
request:
  declarations:
  - name: new_password
    path: $.new_password
    type: string
    required: true
    ui_kind: text
  - name: old_password
    path: $.old_password
    type: string
    required: true
    ui_kind: text
responses:
  '200':
    description: 成功
  '204':
    description: Successful Response
metadata:
  module: auth
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
