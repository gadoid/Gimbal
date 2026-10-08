---
id: platform.scenarios.get_facets
type: endpoints
system: platform
service: platform-service
---

# Scenario Facets

```gimbal:endpoint
review: reviewed
id: platform.scenarios.get_facets
system: platform
service: platform-service
name: Scenario Facets
description: "五维 facets:modules/systems/tags/authors/priorities 可选值+计数。\n\n替代前端「全量拉回 FilterPopover unique」的 M1 过渡形态。PG 走\nGROUP BY + jsonb unnest;SQLite Python 兜底(方言分派同 list)。"
binding:
  protocol: http
  method: GET
  path: /api/scenarios/facets
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
metadata:
  module: scenarios
  tags:
  - platform
  owner: gimbal-bootstrap
```
