---
id: platform.health.get_root
type: endpoints
system: platform
service: platform-service
---

# Health

```gimbal:endpoint
review: reviewed
id: platform.health.get_root
system: platform
service: platform-service
name: Health
binding:
  protocol: http
  method: GET
  path: /api/health
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
metadata:
  module: health
  tags:
  - platform
  owner: gimbal-bootstrap
```
