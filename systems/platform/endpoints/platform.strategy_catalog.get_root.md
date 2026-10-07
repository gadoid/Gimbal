---
id: platform.strategy_catalog.get_root
type: endpoints
system: platform
service: platform-service
---

# List Strategy Kinds

```gimbal:endpoint
review: reviewed
id: platform.strategy_catalog.get_root
system: platform
service: platform-service
name: List Strategy Kinds
description: Proxy ``GET {plate}/api/strategy`` and unwrap ``data.items``.
binding:
  protocol: http
  method: GET
  path: /api/strategy-catalog
  auth: bearer
  body_type: none
request: {}
responses:
  '200':
    description: Successful Response
metadata:
  module: strategy-catalog
  tags:
  - platform
  owner: gimbal-bootstrap
```
