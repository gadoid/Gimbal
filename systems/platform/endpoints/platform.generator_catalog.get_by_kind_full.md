---
id: platform.generator_catalog.get_by_kind_full
type: endpoints
system: platform
service: platform-service
---

# Get Generator Kind Full

```gimbal:endpoint
review: reviewed
id: platform.generator_catalog.get_by_kind_full
system: platform
service: platform-service
name: Get Generator Kind Full
description: Proxy ``GET {plate}/api/generators/{kind}/full`` and unwrap ``data.item``.
binding:
  protocol: http
  method: GET
  path: /api/generator-catalog/{kind}/full
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
metadata:
  module: generator-catalog
  tags:
  - platform
  owner: gimbal-bootstrap
```
