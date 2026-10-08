---
id: platform.strategy_catalog.get_by_kind_full
type: endpoints
system: platform
service: platform-service
---

# Get Strategy Kind Full

```gimbal:endpoint
review: reviewed
id: platform.strategy_catalog.get_by_kind_full
system: platform
service: platform-service
name: Get Strategy Kind Full
description: Proxy ``GET {plate}/api/strategy/{kind}/full`` and unwrap ``data.item``.
binding:
  protocol: http
  method: GET
  path: /api/strategy-catalog/{kind}/full
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
metadata:
  module: strategy-catalog
  tags:
  - platform
  owner: gimbal-bootstrap
```
