---
id: platform.adaptations.get_compare
type: endpoints
system: platform
service: platform-service
---

# Compare Revisions

```gimbal:endpoint
id: platform.adaptations.get_compare
system: platform
service: platform-service
name: Compare Revisions
description: "RS4a 比较（§5.3）:场景起点修订 vs 目标修订的 plate 差异 + 三组影响。\n\nR22:读面全员(差异本身不涉编辑权)。"
binding:
  protocol: http
  method: GET
  path: /api/adaptations/compare
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
