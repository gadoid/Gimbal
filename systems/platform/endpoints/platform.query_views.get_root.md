---
id: platform.query_views.get_root
type: endpoints
system: platform
service: platform-service
---

# List Views

```gimbal:endpoint
review: reviewed
id: platform.query_views.get_root
system: platform
service: platform-service
name: List Views
description: '索引代理(§13.3):前端参数段消费 query_params;复用 runner 的

  plate memo + 熔断,零新增状态。'
binding:
  protocol: http
  method: GET
  path: /api/query-views
  auth: bearer
  body_type: none
request: {}
responses:
  '200':
    description: Successful Response
metadata:
  module: query-views
  tags:
  - platform
  owner: gimbal-bootstrap
```
