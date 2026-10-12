---
id: platform.endpoint_catalog.get_by_endpoint_id_projection
type: endpoints
system: platform
service: platform-service
---

# Get Endpoint Projection

```gimbal:endpoint
review: reviewed
id: platform.endpoint_catalog.get_by_endpoint_id_projection
system: platform
service: platform-service
name: Get Endpoint Projection
description: "Proxy ``GET {plate}/api/endpoint/{id}/projection?ref=``（4.8）。\n\n编排页 binding 只读展示（method/path 模板/timeout）经此查询 ——\n场景 call 不再存 binding 派生字段（6.2），展示面由投影提供。\n结果不可变，前端会话级缓存。ref 缺省 = working（新建步骤浏览）。"
binding:
  protocol: http
  method: GET
  path: /api/endpoint-catalog/{endpoint_id}/projection
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
metadata:
  module: endpoint-catalog
  tags:
  - platform
  owner: gimbal-bootstrap
```
