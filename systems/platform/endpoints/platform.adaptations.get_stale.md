---
id: platform.adaptations.get_stale
type: endpoints
system: platform
service: platform-service
---

# Stale Scenarios

```gimbal:endpoint
review: draft
id: platform.adaptations.get_stale
system: platform
service: platform-service
name: Stale Scenarios
description: RS4a 陈旧清单（§2.3）:预览/新线/已修正/已退役。scope=mine 只看自己。
binding:
  protocol: http
  method: GET
  path: /api/adaptations/stale
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
  module: adaptations
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: ''
```
