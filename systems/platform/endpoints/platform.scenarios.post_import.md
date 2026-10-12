---
id: platform.scenarios.post_import
type: endpoints
system: platform
service: platform-service
---

# Import Scenario

```gimbal:endpoint
review: draft
id: platform.scenarios.post_import
system: platform
service: platform-service
name: Import Scenario
description: |-
  导入场景（R19）:按 meta.plate 声明的修订经 /convert 校验后
  入库;无 meta.plate 或声明的修订不存在 → 422(由导入人选修订,
  不猜测来源版本)。
binding:
  protocol: http
  method: POST
  path: /api/scenarios/import
  timeout_seconds: 30.0
  auth: bearer
  body_type: json
request:
  declarations:
  - name: definition
    path: $.definition
    type: object
    ui_kind: json
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
  module: scenarios
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
