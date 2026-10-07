---
id: platform.adaptations.patch_ops_by_op_id
type: endpoints
system: platform
service: platform-service
---

# Patch Op

```gimbal:endpoint
review: reviewed
id: platform.adaptations.patch_ops_by_op_id
system: platform
service: platform-service
name: Patch Op
description: 仅 pending 可整包替换 payload(mapValue 骨架补值 / 参数修正)。
binding:
  protocol: http
  method: PATCH
  path: /api/adaptations/ops/{op_id}
  auth: bearer
request:
  declarations:
  - name: payload
    path: $.payload
    type: object
    ui_kind: json
responses:
  '200':
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
