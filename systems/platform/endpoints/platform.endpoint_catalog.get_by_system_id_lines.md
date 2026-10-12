---
id: platform.endpoint_catalog.get_by_system_id_lines
type: endpoints
system: platform
service: platform-service
---

# List System Lines

```gimbal:endpoint
review: reviewed
id: platform.endpoint_catalog.get_by_system_id_lines
system: platform
service: platform-service
name: List System Lines
description: "版本线列表 + 修订数 + 最新修订 + scheme（编排页版本下拉数据源）。\n\n调 plate_client.list_lines → plate /api/system/{id}/lines。"
binding:
  protocol: http
  method: GET
  path: /api/endpoint-catalog/{system_id}/lines
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
