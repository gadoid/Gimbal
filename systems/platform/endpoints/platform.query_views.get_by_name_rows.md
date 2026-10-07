---
id: platform.query_views.get_by_name_rows
type: endpoints
system: platform
service: platform-service
---

# Get Rows

```gimbal:endpoint
review: reviewed
id: platform.query_views.get_by_name_rows
system: platform
service: platform-service
name: Get Rows
binding:
  protocol: http
  method: GET
  path: /api/query-views/{name}/rows
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
