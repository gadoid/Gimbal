---
id: platform.adaptations.get_refs_drift
type: endpoints
system: platform
service: platform-service
---

# Refs Drift

```gimbal:endpoint
review: reviewed
id: platform.adaptations.get_refs_drift
system: platform
service: platform-service
name: Refs Drift
description: 倒排索引 vs plate 接口目录 diff(只读):悬空引用 / 全网零引用。
binding:
  protocol: http
  method: GET
  path: /api/adaptations/refs-drift
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
    declarations:
    - name: dangling
      path: $.dangling
      type: array
      ui_kind: json
      assertable: true
    - name: plateReachable
      path: $.plateReachable
      type: boolean
      required: true
      ui_kind: boolean
      assertable: true
    - name: zeroRef
      path: $.zeroRef
      type: array
      ui_kind: json
      assertable: true
metadata:
  module: adaptations
  tags:
  - platform
  owner: gimbal-bootstrap
```
