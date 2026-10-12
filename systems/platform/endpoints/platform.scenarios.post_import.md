---
id: platform.scenarios.post_import
type: endpoints
system: platform
service: platform-service
---

# Import Scenario

```gimbal:endpoint
review: reviewed
id: platform.scenarios.post_import
system: platform
service: platform-service
name: Import Scenario
description: "导入场景（R19）:按 meta.plate 声明的修订经 /convert 校验后\n入库;无 meta.plate 或声明的修订不存在 → 422(由导入人选修订,\n不猜测来源版本)。"
binding:
  protocol: http
  method: POST
  path: /api/scenarios/import
  auth: bearer
request:
  declarations:
  - name: definition
    path: $.definition
    type: object
    required: true
    ui_kind: json
responses:
  "201":
    description: Successful Response
  "200":
    description: 成功
metadata:
  module: scenarios
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
