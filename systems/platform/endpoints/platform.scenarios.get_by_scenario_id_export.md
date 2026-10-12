---
id: platform.scenarios.get_by_scenario_id_export
type: endpoints
system: platform
service: platform-service
---

# Export Scenario

```gimbal:endpoint
review: draft
id: platform.scenarios.get_by_scenario_id_export
system: platform
service: platform-service
name: Export Scenario
description: |-
  导出场景定义（含 meta.plate 精确修订）——可直接被 CLI 与其他
  平台实例使用（R19:文件自带版本声明）。
binding:
  protocol: http
  method: GET
  path: /api/scenarios/{scenario_id}/export
  timeout_seconds: 30.0
  auth: bearer
  body_type: none
request:
  declarations: []
responses:
  '200':
    description: Successful Response
    declarations: []
metadata:
  module: scenarios
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: ''
```
