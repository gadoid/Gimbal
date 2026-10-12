---
id: platform.suites.get_by_suite_id_version_distribution
type: endpoints
system: platform
service: platform-service
---

# Get Version Distribution

```gimbal:endpoint
review: draft
id: platform.suites.get_by_suite_id_version_distribution
system: platform
service: platform-service
name: Get Version Distribution
description: Suite 编辑页版本分布（§6.6/R25）：成员场景的系统→版本线映射。
binding:
  protocol: http
  method: GET
  path: /api/suites/{suite_id}/version-distribution
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
  module: suites
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: ''
```
