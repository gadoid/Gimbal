---
id: platform.adaptations.get_stale
type: endpoints
system: platform
service: platform-service
---

# Stale Scenarios

```gimbal:endpoint
id: platform.adaptations.get_stale
system: platform
service: platform-service
name: Stale Scenarios
description: RS4a 陈旧清单（§2.3）:预览/新线/已修正/已退役。scope=mine 只看自己。
binding:
  protocol: http
  method: GET
  path: /api/adaptations/stale
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
metadata:
  module: adaptations
  tags:
  - platform
  owner: gimbal-bootstrap
```
