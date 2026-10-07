---
id: platform.generator_catalog.get_root
type: endpoints
system: platform
service: platform-service
---

# List Generator Kinds

```gimbal:endpoint
review: reviewed
id: platform.generator_catalog.get_root
system: platform
service: platform-service
name: List Generator Kinds
description: Proxy ``GET {plate}/api/generators`` and unwrap ``data.items``.
binding:
  protocol: http
  method: GET
  path: /api/generator-catalog
  auth: bearer
  body_type: none
request: {}
responses:
  '200':
    description: Successful Response
metadata:
  module: generator-catalog
  tags:
  - platform
  owner: gimbal-bootstrap
```
