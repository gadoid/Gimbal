---
id: platform.adaptations.get_impact_bulk
type: endpoints
system: platform
service: platform-service
---

# Impact Bulk

```gimbal:endpoint
review: reviewed
id: platform.adaptations.get_impact_bulk
system: platform
service: platform-service
name: Impact Bulk
description: '批量 impact(M5,债 12):一次请求回全部 pending 端点的受影响

  清单 —— 前端 useInterfaceChange 的「每端点一次 × 限并发 4」N+1

  消除。返回 {endpointId: [ImpactItem...]}(与单端点 /impact 同条目

  形状,未命中端点给空数组)。'
binding:
  protocol: http
  method: GET
  path: /api/adaptations/impact-bulk
  auth: bearer
  body_type: none
request: {}
responses:
  '200':
    description: Successful Response
metadata:
  module: adaptations
  tags:
  - platform
  owner: gimbal-bootstrap
```
