---
id: platform.adaptations.get_unindexed_steps
type: endpoints
system: platform
service: platform-service
---

# Unindexed Steps

```gimbal:endpoint
review: reviewed
id: platform.adaptations.get_unindexed_steps
system: platform
service: platform-service
name: Unindexed Steps
description: C10:缺 endpoint_id 的步骤清单(只读警示,不产生任何写)。
binding:
  protocol: http
  method: GET
  path: /api/adaptations/unindexed-steps
  auth: bearer
  body_type: none
request: {}
responses:
  '200':
    description: Successful Response
    declarations:
    - name: reason
      path: $.reason
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: scenarioId
      path: $.scenarioId
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: stepIndex
      path: $.stepIndex
      type: integer
      required: true
      ui_kind: number
      assertable: true
metadata:
  module: adaptations
  tags:
  - platform
  owner: gimbal-bootstrap
```
