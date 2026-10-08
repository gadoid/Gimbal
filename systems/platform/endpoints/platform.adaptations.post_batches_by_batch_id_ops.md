---
id: platform.adaptations.post_batches_by_batch_id_ops
type: endpoints
system: platform
service: platform-service
---

# Create Op

```gimbal:endpoint
review: reviewed
id: platform.adaptations.post_batches_by_batch_id_ops
system: platform
service: platform-service
name: Create Op
description: 人工补 op(renameVar / 数据集 op —— 自动草案之外,§5.4)。
binding:
  protocol: http
  method: POST
  path: /api/adaptations/batches/{batch_id}/ops
  auth: bearer
request:
  declarations:
  - name: datasetId
    path: $.datasetId
    type: string
    ui_kind: text
  - name: opType
    path: $.opType
    type: string
    required: true
    ui_kind: text
  - name: payload
    path: $.payload
    type: object
    ui_kind: json
  - name: scenarioId
    path: $.scenarioId
    type: string
    ui_kind: text
responses:
  "200":
    description: 成功
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
  "201":
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
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
