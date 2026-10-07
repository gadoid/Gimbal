---
id: platform.data_sets.delete_by_dataset_id
type: endpoints
system: platform
service: platform-service
---

# Delete Data Set

```gimbal:endpoint
review: reviewed
id: platform.data_sets.delete_by_dataset_id
system: platform
service: platform-service
name: Delete Data Set
binding:
  protocol: http
  method: DELETE
  path: /api/data-sets/{dataset_id}
  auth: bearer
  body_type: none
request: {}
responses:
  '200':
    description: 成功
  '204':
    description: Successful Response
metadata:
  module: data-sets
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
