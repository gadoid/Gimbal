---
id: platform.adaptations.post_ops_by_op_id_skip
type: endpoints
system: platform
service: platform-service
---

# Skip Op

```gimbal:endpoint
review: reviewed
id: platform.adaptations.post_ops_by_op_id_skip
system: platform
service: platform-service
name: Skip Op
description: 跳过一条 pending op(末条跳过同样收敛 completed + 推戳)。
binding:
  protocol: http
  method: POST
  path: /api/adaptations/ops/{op_id}/skip
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
    declarations:
    - name: appliedAt
      path: $.appliedAt
      type: string
      ui_kind: text
      assertable: true
    - name: batchId
      path: $.batchId
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: datasetId
      path: $.datasetId
      type: string
      ui_kind: text
      assertable: true
    - name: datasetName
      path: $.datasetName
      type: string
      ui_kind: text
      assertable: true
    - name: id
      path: $.id
      type: integer
      required: true
      ui_kind: number
      assertable: true
    - name: note
      path: $.note
      type: string
      ui_kind: text
      assertable: true
    - name: opType
      path: $.opType
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: payload
      path: $.payload
      type: object
      ui_kind: json
      assertable: true
    - name: scenarioDisplayName
      path: $.scenarioDisplayName
      type: string
      ui_kind: text
      assertable: true
    - name: scenarioId
      path: $.scenarioId
      type: string
      ui_kind: text
      assertable: true
    - name: status
      path: $.status
      type: string
      required: true
      ui_kind: text
      assertable: true
metadata:
  module: adaptations
  tags:
  - platform
  owner: gimbal-bootstrap
```
