---
id: platform.scenario_filter_groups.delete_by_bucket_by_group_id
type: endpoints
system: platform
service: platform-service
---

# Delete Group

```gimbal:endpoint
review: reviewed
id: platform.scenario_filter_groups.delete_by_bucket_by_group_id
system: platform
service: platform-service
name: Delete Group
binding:
  protocol: http
  method: DELETE
  path: /api/scenario-filter-groups/{bucket}/{group_id}
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
metadata:
  module: scenario-filter-groups
  tags:
  - platform
  owner: gimbal-bootstrap
```
